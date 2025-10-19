import os
from google.cloud import storage


def get_gcs_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        # Local behavior
        return storage.Client.from_service_account_json(creds_path)
    else:
        # On Cloud Run
        return storage.Client()


def ensure_materials_available(bucket_name: str, local_rules_path: str, local_vector_dir: str):
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)

    # Download policyRules.json
    if not os.path.exists(local_rules_path):
        os.makedirs(os.path.dirname(local_rules_path), exist_ok=True)

        blob = bucket.blob("materials/policyRules.json")
        blob.download_to_filename(local_rules_path)
        print("\tDownloaded policyRules.json from GCS.")

    # Download vectorstore directory
    if not os.path.exists(local_vector_dir) or not os.listdir(local_vector_dir):
        os.makedirs(local_vector_dir, exist_ok=True)
        vector_blob_prefix = "materials/policy_vectorstore/"
        blobs = client.list_blobs(bucket_name, prefix=vector_blob_prefix)
        for blob in blobs:
            relative_path = blob.name.replace(vector_blob_prefix, "")
            if relative_path:
                dest_path = os.path.join(local_vector_dir, relative_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                blob.download_to_filename(dest_path)

        print("\tDownloaded vectorstore from GCS.")


def upload_to_gcs(bucket_name: str, local_path: str, blob_name: str):
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url


def download_from_gcs(bucket_name: str, blob_name: str, local_path: str):
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_path)
    return local_path
