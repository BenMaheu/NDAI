import os
from tqdm import tqdm
import json
import chromadb
from typing import List
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv
from pdf2image import convert_from_path
from pytesseract import image_to_string
import re

from config import RETRIEVED_POLICIES_COUNT, CLAUSE_STATUS, POLICY_SEVERITIES

load_dotenv()


# WARNING : Needs to install poppler for pdf2image to work and torch for sentence_transformers
# (in docker : cf. https://stackoverflow.com/questions/78243381/how-to-include-poppler-for-docker-build
# or minidocks/poppler)

# TODO : Create also a vectorstore for clauses and use it to find similar clauses in past NDAs

def create_vectorstore(rules_path: str = "policyRules.json", persist_dir: str = "./policy_vectorstore",
                       collection_name: str = "policy_rules", embedding_model: str = "all-MiniLM-L6-v2"):
    if not os.path.exists(rules_path):
        raise FileNotFoundError(f"Policy rules file not found: {rules_path}")

    with open(rules_path, 'r') as f:
        rules = json.load(f)

    os.makedirs(persist_dir, exist_ok=True)

    client = chromadb.PersistentClient(path=persist_dir)
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model)
    collection = client.get_or_create_collection(name=collection_name, embedding_function=emb_fn)

    try:
        existing = collection.get()
        if existing and "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    ids, docs, metadatas = [], [], []
    for rule in rules:
        doc_text = f"""
                Policy Rule: {rule['title']}
                Category: {rule.get('category', 'Unknown')}
                Severity: {rule.get('severity', 'Unknown')}
                Compliance: {rule.get('compliance', '')}
                Preferred: {rule.get('preferred', '')}
                Red Flags: {', '.join(rule.get('red_flags', []))}
                Detection Hints: {rule.get('detection_hints', '')}
                Examples:
                  - Compliant: {rule['examples'].get('compliant', '')}
                  - Non-Compliant: {rule['examples'].get('non_compliant', '')}
                """

        ids.append(rule['id'])
        docs.append(doc_text.strip())
        metadatas.append({
            "id": rule["id"],
            "title": rule["title"],
            "severity": rule.get("severity", "unknown"),
            "category": rule.get("category", "unknown")
        })

    collection.add(ids=ids, documents=docs, metadatas=metadatas)
    print(
        f"Indexed {len(ids)} policy rules into the vector store into '{collection_name}' (persisted at '{persist_dir}').")

    # TODO: Add sanity check ? Testing retrieval of a known rule

    return collection


def load_vectorstore(persist_directory: str, collection_name="policy_rules"):
    client = chromadb.PersistentClient(path=persist_directory)
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    coll = client.get_or_create_collection(name=collection_name, embedding_function=emb_fn)
    return coll


def retrieve_policy_rules(clause_text: str, coll: chromadb.api.models.Collection, k: int = RETRIEVED_POLICIES_COUNT):
    res = coll.query(query_texts=[clause_text], n_results=k)
    rules = []
    for i, doc in enumerate(res["documents"][0]):
        meta = res["metadatas"][0][i]
        rules.append({
            "title": meta["title"],
            "severity": meta["severity"],
            "category": meta["category"],
            "content": doc
        })
    return rules


def analyze_clause_llm(clause_text: str, rules: List[dict], model="gpt-4.1-mini"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    policy_context = "\n\n".join(
        [f"- {r['title']} (severity: {r['severity']}): {r['content']}" for r in rules]
    )
    prompt = f"""
    You are an expert in contract law reviewing an NDA clause against internal compliance policies.

    Clause to evaluate:
    \"\"\"{clause_text}\"\"\"

    Here are the most relevant internal policy rules:
    {policy_context}

    Task:
    - Determine which rule applies most directly.
    - State whether the clause is compliant, non-compliant, or ambiguous.
    - Justify your decision in one or two sentences, citing evidence from the clause.

    Respond strictly in JSON with the following fields:
    {{
      "best_rule": "string",
      "severity": "{'|'.join(POLICY_SEVERITIES)}",
      "status": "{'|'.join(CLAUSE_STATUS)}", 
      "reason": "string explanation"
    }}
    """
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    text = response.choices[0].message.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"best_rule": "Parsing Error", "status": "Needs Review", "reason": text}

    return result


def evaluate_clause(clause_text: str, coll: chromadb.api.models.Collection, k: int = RETRIEVED_POLICIES_COUNT):
    retrieved_rules = retrieve_policy_rules(clause_text, coll, k=k)
    llm_eval = analyze_clause_llm(clause_text, retrieved_rules)
    return {
        "clause": clause_text[:400],
        "retrieved_rules": retrieved_rules,
        "llm_evaluation": llm_eval,
    }


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Preprocess a PDF document to extract text.
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Extract text from each image using OCR
    out = ""
    for page_number, image in enumerate(images):
        out += image_to_string(image)
    return out


def segment_clauses(text: str) -> List[dict]:
    """Takes the text extracted from a PDF and segments it into clauses."""
    # Discard spaces and multiple newlines
    text = re.sub(r'\n+', '\n', text)

    # Chunk by clauses titles
    # TODO: Optionally we could ask a LLM to PDF2MD and then use a simpler regex pattern to get titles
    # Note that this could be improved to ensure we capture clauses for different formats of NDA including sub-clauses
    pattern = r'(?:\n|^)(\d{1,2}\.\s+[A-Z][^\n]+)(?=\n)'  # Matches titles like "1. Confidentiality" or "2.1 Non-Disclosure" followed by linebreak
    sections = re.split(pattern, text)

    # sections = [junk, title1, clause1, title2, clause2, ...]
    clauses = []
    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        body = sections[i + 1].strip() if i + 1 < len(sections) else ""
        clauses.append({"title": title, "body": body})

    return clauses


def analyze_nda(pdf_path: str, coll: chromadb.api.models.Collection) -> List[dict]:
    text = extract_text_from_pdf(pdf_path)
    clauses = segment_clauses(text)

    results = []
    print("Analyzing clauses...")
    for clause in tqdm(clauses):
        clause_text = f"{clause['title']}\n{clause['body']}"
        eval_result = evaluate_clause(clause_text, coll)
        results.append(eval_result)

    return results


# if __name__ == "__main__":
    # create_vectorstore("policyRules.json", persist_dir="./policy_vectorstore")
    #
    # coll = load_vectorstore("./policy_vectorstore")
    #
    # # Query vectorstore
    # clause = "Each Recipient shall indemnify the Discloser only in the event of willful misconduct."
    # result = evaluate_clause(clause, coll)
    # print(json.dumps(result, indent=2))
