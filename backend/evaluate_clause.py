from langchain_text_splitters import CharacterTextSplitter
from PIL import Image
import fitz
from pdf2image import convert_from_path
from pytesseract import image_to_string
from dataclasses import dataclass
from typing import Optional


# WARNING : Needs to install poppler for pdf2image to work
# (in docker : cf. https://stackoverflow.com/questions/78243381/how-to-include-poppler-for-docker-build
# or minidocks/poppler)

# Note that PyMuPdf did not work well with the PDFs not keeping the paragraphs architecture and line breaks,
# hence the use of pdf2image + pytesseract

def split_document(text: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Splits a document into smaller chunks for processing.
    """
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = text_splitter.split_text(text)
    return chunks


def chunk_pdf(pdf_path: str, separator: str = "\n\n") -> list[dict]:
    """
    Preprocess a PDF document to extract text.
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Extract text from each image using OCR
    chunks = []
    for page_number, image in enumerate(images):
        text = image_to_string(image)
        paragraphs = [p.strip() for p in text.split(separator) if p.strip()]
        for p in paragraphs:
            chunks.append({
                "page": page_number + 1,
                "text": p
            })
    return chunks


if __name__ == "__main__":
    import os

    ndaPath = r'../examples/investor_nda.pdf'

    chunks = chunk_pdf(ndaPath)
    print(chunks)

    # # OCR
    # doc = convert_from_path(ndaPath)
    # for page_number, page_data in enumerate(doc):
    #     txt = image_to_string(page_data)
    #     print("\n\n\n\n")
    #     print("-" * 50 + f" PAGE {page_number + 1} " + "-" * 50)
    #     print(txt)
