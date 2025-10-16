import os
import json
import re
from pdf2image import convert_from_path
from pytesseract import image_to_string
from typing import List
from flask import Flask, request, jsonify
from config import CLAUSE_LABELS
from openai import OpenAI
from dotenv import load_dotenv

# WARNING : Needs to install poppler for pdf2image to work and torch for sentence_transformers
# (in docker : cf. https://stackoverflow.com/questions/78243381/how-to-include-poppler-for-docker-build
# or minidocks/poppler)

load_dotenv()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Preprocess a PDF document to extract text.
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Extract text from each image using OCR
    # chunks = []
    text = ""
    for page_number, image in enumerate(images):
        text += image_to_string(image)
        # paragraphs = [p.strip() for p in text.split(separator) if p.strip()]
        # for p in paragraphs:
        #     chunks.append({
        #         "page": page_number + 1,
        #         "text": p
        #     })
    return text


def segment_clauses(text: str) -> List[dict]:
    """Takes the text extracted from a PDF and segments it into clauses."""
    # Discard spaces and multiple newlines
    text = re.sub(r'\n+', '\n', text)

    # Chunk by clauses titles
    # TODO: Optionally we could ask a LLM to PDF2MD and then use a simpler regex pattern to get titles
    pattern = r'(?:\n|^)(\d{1,2}\.\s+[A-Z][^\n]+)(?=\n)'
    sections = re.split(pattern, text)

    # sections = [junk, title1, clause1, title2, clause2, ...]
    clauses = []
    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        body = sections[i + 1].strip() if i + 1 < len(sections) else ""
        clauses.append({"title": title, "body": body})

    return clauses


def extract_and_classify_clauses(pdf_text: str) -> List[dict]:
    clauses = segment_clauses(pdf_text)
    for clause in clauses:
        clause["type"] = classify_clause_llm(clause["title"], clause["body"])
    return clauses


def classify_clause_llm(clause_title: str, clause_body: str, model: str = "gpt-4.1-mini", rounds: int = 3) -> str:
    """Classifies a clause into one of the predefined types using OpenAI."""
    prompt = f"""
    You are a legal assistant. Categorize the following NDA clause
    into one of these types:
    {CLAUSE_LABELS}

    Clause:
    <clause_title>{clause_title}</clause_title>

    <clause_body>
    {clause_body}
    </clause_body>

    Answer with only the clause type, no explanations.
    """

    client = OpenAI(api_key=os.getenv["OPENAI_API_KEY"])
    response = client.responses.create(
        model=model,
        input=prompt,
    )

    if response.output_text not in CLAUSE_LABELS:
        response = classify_clause_llm(clause_title, clause_body, model=model, rounds=rounds - 1)

    return response.output_text


if __name__ == "__main__":
    pdfPath = r"../examples/investor_nda.pdf"
    text = extract_text_from_pdf(pdfPath)

    clauses = segment_clauses(text)
    print(clauses)


