import os
from google.cloud import storage


def get_gcs_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return storage.Client.from_service_account_json(creds_path)


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
