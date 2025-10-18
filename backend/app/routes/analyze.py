import os
import json
import time
import threading
from flask import Blueprint, request, jsonify, current_app
from app.services.policy_matcher import analyze_nda, create_vectorstore, load_vectorstore
from app.services.scoring import compute_compliance_score
from app.services.storage import upload_to_gcs
from app.config import Config

analyze_bp = Blueprint("analyze", __name__, url_prefix="/analyze")

# Initialize vectorstore once
coll = None


def init_vectorstore():
    global coll
    if not os.path.exists(Config.VECTORSTORE_DIR) or not os.listdir(Config.VECTORSTORE_DIR):
        print("Creating policy vectorstore...")
        create_vectorstore(Config.POLICY_RULES_PATH, persist_dir=Config.VECTORSTORE_DIR)
    print("Loading policy vectorstore...")
    coll = load_vectorstore(Config.VECTORSTORE_DIR)
    print("Policy vectorstore ready!")


def async_upload_and_cleanup(gcs_bucket, local_pdf, local_report, file_basename):
    """Background task to upload files to GCS and clean them up locally."""
    try:
        pdf_url = upload_to_gcs(gcs_bucket, local_pdf, f"pdfs/{file_basename}")
        report_url = upload_to_gcs(gcs_bucket, local_report, f"reports/{file_basename}_report.json")
        print(f"Uploaded to GCS: {pdf_url}, {report_url}")
    except Exception as e:
        print(f"GCS upload failed for {file_basename}: {e}")
        pdf_url, report_url = None, None
    finally:
        # Cleanup
        for path in [local_pdf, local_report]:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"Deleted temp file: {path}")
            except Exception as cleanup_err:
                print(f"Failed to delete {path}: {cleanup_err}")


@analyze_bp.route("", methods=["POST"])
def analyze():
    t0 = time.time()
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    reports_folder = current_app.config["REPORT_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(reports_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, file.filename)
    file.save(filepath)

    try:
        results = analyze_nda(filepath, coll)
        score_summary = compute_compliance_score(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    report = {
        "filename": file.filename,
        "analysis": results,
        "total_clauses": len(results),
        "compliance": score_summary,
        "time_seconds": round(time.time() - t0, 2)
    }

    report_path = os.path.join(reports_folder, f"{file.filename}_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)

    # Upload to GCS (optionally)
    gcs_bucket = current_app.config.get("GCS_BUCKET")

    if gcs_bucket:
        threading.Thread(
            target=async_upload_and_cleanup,
            args=(gcs_bucket, filepath, report_path, file.filename),
            daemon=True
        ).start()

    return jsonify(report), 200
