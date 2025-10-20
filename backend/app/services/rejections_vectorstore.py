import os
from chromadb import PersistentClient
import chromadb.api.models.Collection as Collection
from chromadb.utils import embedding_functions
from app.config import Config
from app.services.storage import download_from_gcs, upload_to_gcs, get_gcs_client

REJ_COLLECTION_NAME = "rejected_clauses"


def load_rejections_vectorstore():
    """Return the persistent collection for rejected clauses."""
    REJECTIONS_DIR = Config.REJECTIONS_VECTORSTORE_DIR
    os.makedirs(REJECTIONS_DIR, exist_ok=True)
    client = PersistentClient(path=REJECTIONS_DIR)

    GCS_BUCKET = Config.GCS_BUCKET

    if GCS_BUCKET:
        try:
            print(f"Syncing rejections vectorstore from GCS bucket {GCS_BUCKET}...")
            vector_blob_prefix = "materials/rejections_vectorstore/"
            gcs_client = get_gcs_client()
            blobs = gcs_client.list_blobs(GCS_BUCKET, prefix=vector_blob_prefix)
            for blob in blobs:
                relative_path = blob.name.replace(vector_blob_prefix, "")
                if relative_path:
                    dest_path = os.path.join(REJECTIONS_DIR, relative_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    blob.download_to_filename(dest_path)
        except Exception as e:
            print(f"Warning could not sync vectorstore from GCS: {e}")

    # Embedding function using SentenceTransformer model
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    coll = client.get_or_create_collection(name=REJ_COLLECTION_NAME, embedding_function=embedding_fn)
    return coll


def persist_rejections_vectorstore():
    """Upload all local Chroma files to GCS for persistence."""
    GCS_BUCKET = Config.GCS_BUCKET
    REJECTIONS_DIR = Config.REJECTIONS_VECTORSTORE_DIR

    if not os.path.exists(REJECTIONS_DIR):
        print(f"Rejections vectorstore dir not found: {REJECTIONS_DIR}")
        return

    if GCS_BUCKET:
        print(f"Uploading rejection vectorstore to gs://{GCS_BUCKET}/rejections_vectorstore/ ...")
        try:
            for root, _, files in os.walk(REJECTIONS_DIR):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    # Compute relative path to preserve folder structure
                    rel_path = os.path.relpath(local_file_path, REJECTIONS_DIR)
                    blob_name = f"materials/rejections_vectorstore/{rel_path}"
                    upload_to_gcs(GCS_BUCKET, local_file_path, blob_name)
            print("Vectorstore upload complete.")
        except Exception as e:
            print(f"Could not upload vectorstore to GCS: {e}")


def add_rejection_to_vectorstore(rejection_id: int, clause_id: int, clause_text: str, comment: str,
                                 doc_id: int | None = None):
    """Store a rejected clause embedding for future retrieval."""
    coll = load_rejections_vectorstore()
    metadata = {
        "clause_id": clause_id,
        "doc_id": doc_id,
        "comment": comment,
    }
    coll.add(
        ids=[f"{rejection_id}"],
        documents=[clause_text],
        metadatas=[metadata],
    )
    persist_rejections_vectorstore()
    print(f"Added rejected clause {clause_id} to vectorstore.")


def search_similar_rejections(coll: Collection, query: str, n_results: int = 3):
    """Retrieve most similar rejected clauses for context injection."""
    return coll.query(query_texts=[query], n_results=n_results)
