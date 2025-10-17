import os
import asyncio
import json
import chromadb
from typing import List, Any, Tuple
from chromadb.utils import embedding_functions
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pdf2image import convert_from_path
from pytesseract import image_to_string
import re
from dataclasses import dataclass

from config import RETRIEVED_POLICIES_COUNT, CLAUSE_STATUS, POLICY_SEVERITIES, SEVERITY_WEIGHTS, STATUS_PENALTIES

load_dotenv()


# WARNING : Needs to install poppler for pdf2image to work and torch for sentence_transformers
# (in docker : cf. https://stackoverflow.com/questions/78243381/how-to-include-poppler-for-docker-build
# or minidocks/poppler)

# TODO : Create also a vectorstore for clauses and use it to find similar clauses in past NDAs

@dataclass
class Clause:
    title: str
    body: str
    pages: List[int]

    def __str__(self):
        return f"{self.title}\n{self.body}"


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


def retrieve_policy_rules(clause: Clause, coll: chromadb.api.models.Collection, k: int = RETRIEVED_POLICIES_COUNT):
    res = coll.query(query_texts=[str(clause)], n_results=k)
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


async def analyze_clause_llm(clause: Clause, rules: List[dict], model="gpt-4.1-mini"):
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    policy_context = "\n\n".join(
        [f"- {r['title']} (severity: {r['severity']}): {r['content']}" for r in rules]
    )
    prompt = f"""
    You are an expert in contract law reviewing an NDA clause against internal compliance policies.

    Clause to evaluate:
    \"\"\"{str(clause)}\"\"\"

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
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        result = json.loads(text)
    except Exception as e:
        result = {"best_rule": "Parsing Error", "status": "Needs Review", "reason": str(e)}

    return result


async def evaluate_clause(clause: Clause, coll: chromadb.api.models.Collection,
                          k: int = RETRIEVED_POLICIES_COUNT) -> dict:
    retrieved_rules = retrieve_policy_rules(clause, coll, k=k)
    llm_eval = await analyze_clause_llm(clause, retrieved_rules)
    return {
        "clause": str(clause)[:400],
        "retrieved_rules": retrieved_rules,
        "llm_evaluation": llm_eval,
    }


def extract_text_from_pdf(pdf_path: str) -> List[dict]:
    """
    Preprocess a PDF document to extract text.
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Extract text from each image using OCR
    pages = []
    for page_number, image in enumerate(images):
        text = image_to_string(image)
        pages.append({
            "page_number": page_number + 1,
            "text": text.strip()
        })
    return pages


def combine_pages_with_markers(pages: List[dict]) -> str:
    combined = ""
    for page in pages:
        combined += f"[[PAGE_{page['page_number']}]]\n" + page["text"]
    return combined


def segment_clauses(pages: List[dict]) -> List[Clause]:
    """Segments text into clauses while correctly tracking page ranges."""
    combined = combine_pages_with_markers(pages)

    # Chunk by clauses titles
    # TODO: Optionally we could ask a LLM to PDF2MD and then use a simpler regex pattern to get titles
    # Note that this could be improved to ensure we capture clauses for different formats of NDA including sub-clauses
    pattern = r'(?:\n|^)(\d{1,2}\.\s+[A-Z][^\n]+)(?=\n)'
    sections = re.split(pattern, combined)

    clauses = []
    current_page_marker = 1

    for i in range(1, len(sections), 2):
        title_raw = sections[i].strip()
        body_raw = sections[i + 1].strip() if i + 1 < len(sections) else ""

        # Collect all page markers
        page_markers = [int(p) for p in re.findall(r'\[\[PAGE_(\d+)\]\]', title_raw + body_raw)]

        if page_markers:
            first_marker = page_markers[0]
            pages_for_clause = set(page_markers)

            if title_raw.startswith(f'[[PAGE_{first_marker}]]'):
                # Clause starts before the first marker (marker at title start)
                if first_marker > 1:
                    pages_for_clause.add(first_marker - 1)
            else:
                # Marker inside title or body → clause spans previous and current pages
                if first_marker > 1:
                    pages_for_clause.add(first_marker - 1)

            current_page_marker = max(pages_for_clause)
        else:
            # No marker: clause stays on the same page
            pages_for_clause = {current_page_marker}

        # Clean markers
        clean_title = re.sub(r'\[\[PAGE_\d+\]\]', '', title_raw).strip()
        clean_body = re.sub(r'\[\[PAGE_\d+\]\]', '', body_raw).strip()

        clauses.append(
            Clause(
                title=clean_title,
                body=clean_body,
                pages=sorted(pages_for_clause)
            )
        )

    return clauses


async def analyze_nda_async(pdf_path: str, coll: chromadb.api.models.Collection) -> Tuple[Any]:
    text = extract_text_from_pdf(pdf_path)
    clauses = segment_clauses(text)

    tasks = [evaluate_clause(clause, coll) for clause in clauses]
    results = await asyncio.gather(*tasks)
    return results


def analyze_nda(pdf_path: str, coll: chromadb.api.models.Collection) -> Tuple[Any]:
    """Sync wrapper for Flask."""
    print("Analyzing clauses...")
    return asyncio.run(analyze_nda_async(pdf_path, coll))


def compute_compliance_score(results: List[dict]) -> dict:
    total_penalty = 0
    max_possible_penalty = 0
    severity_summary = {s: 0 for s in POLICY_SEVERITIES}

    for r in results:
        eval = r.get("llm_evaluation", {})
        severity = eval.get("severity", "medium").lower()
        status = eval.get("status", "Needs Review")

        weight = SEVERITY_WEIGHTS.get(severity, 2)
        penalty = STATUS_PENALTIES.get(status, 1)
        total_penalty += weight * penalty
        max_possible_penalty += weight * STATUS_PENALTIES["Red Flag"]
        severity_summary[severity] += 1

    if max_possible_penalty == 0:
        score = 100.0
    else:
        score = max(0.0, 100.0 * (1 - total_penalty / max_possible_penalty))

    return {
        "compliance_score": round(score, 2),
        "details": {
            "total_penalty": total_penalty,
            "max_possible_penalty": max_possible_penalty,
            "clauses": len(results),
            "by_severity": severity_summary
        }
    }


# if __name__ == "__main__":
# create_vectorstore("policyRules.json", persist_dir="./policy_vectorstore")
#
# coll = load_vectorstore("./policy_vectorstore")
#
# # Query vectorstore
# clause = "Each Recipient shall indemnify the Discloser only in the event of willful misconduct."
# result = evaluate_clause(clause, coll)
# print(json.dumps(result, indent=2))

if __name__ == "__main__":
    pdfPath = r'../examples/investor_nda.pdf'
    pages = extract_text_from_pdf(pdfPath)
    clauses = segment_clauses(pages)
    print(clauses)
