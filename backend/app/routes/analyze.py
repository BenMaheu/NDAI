import os
import json
import time
from flask import Blueprint, request, jsonify, current_app
from app.services.scoring import compute_compliance_score
from app.services.storage import upload_to_gcs
from app.config import Config

analyze_bp = Blueprint("analyze", __name__, url_prefix="/analyze")

# Initialize vectorstore once
coll = None
vectorstore_initialized = False


def async_upload_and_cleanup(bucket, local_pdf, local_report, file_basename):
    try:
        pdf_url = upload_to_gcs(bucket, local_pdf, f"pdfs/{file_basename}")
        report_url = upload_to_gcs(bucket, local_report, f"reports/{file_basename}_report.json")
        print(f"✅ Uploaded {file_basename} to GCS")
    finally:
        for path in [local_pdf, local_report]:
            if os.path.exists(path):
                os.remove(path)
                print(f"🧹 Deleted temp: {path}")


def ensure_vectorstore_loaded():
    global coll, vectorstore_initialized
    if not vectorstore_initialized:
        from app.services.policy_matcher import create_vectorstore, load_vectorstore
        print("No vectorstore initialized.")
        if not os.path.exists(Config.VECTORSTORE_DIR) or not os.listdir(Config.VECTORSTORE_DIR):
            print("No policy vectorstore found. Creating policy vectorstore...")
            create_vectorstore(Config.POLICY_RULES_PATH, persist_dir=Config.VECTORSTORE_DIR)
        print("Loading policy vectorstore...")
        coll = load_vectorstore(Config.VECTORSTORE_DIR)
        vectorstore_initialized = True
        print("Policy vectorstore ready!")


@analyze_bp.route("", methods=["POST"])
def analyze():
    # Ensure vectorstore is loaded --> We import here to avoid loading embedding model during the app startup
    from app.services.policy_matcher import analyze_nda
    ensure_vectorstore_loaded()

    t0 = time.time()
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    # Exclude non-PDF files
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    # Create necessary folders
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    reports_folder = current_app.config["REPORT_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(reports_folder, exist_ok=True)

    # Save temporarily the uploaded file
    filepath = os.path.join(upload_folder, file.filename)
    file.save(filepath)

    try:
        results = analyze_nda(filepath, coll)
        score_summary = compute_compliance_score(results)
        print("Analysis completed.")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Save JSON report
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

    # Upload to GCS (on Cloud only)
    gcs_bucket = current_app.config.get("GCS_BUCKET")
    pdf_url, report_url = None, None

    if gcs_bucket:
        try:
            pdf_url = upload_to_gcs(gcs_bucket, filepath, f"pdfs/{file.filename}")
            report_url = upload_to_gcs(gcs_bucket, report_path, f"reports/{file.filename}_report.json")
        except Exception as e:
            print(f"⚠️ GCS upload failed: {e}")

    report["storage"] = {
        "pdf_url": pdf_url or filepath,
        "report_url": report_url or report_path
    }

    # TODO: try to store on PGSQL while analyzing
    store_doc_analysis_in_db(report)

    # TODO: delete the local files after upload if needed

    return jsonify(report), 200


def store_doc_analysis_in_db(report: dict):
    from app.db import SessionLocal, Document, Clause, Prediction

    db = SessionLocal()

    try:
        doc = Document(
            filename=report["filename"],
            total_clauses=report["total_clauses"],
            compliance_score=report["compliance"]["compliance_score"],
            compliance_details=report["compliance"]["details"],
            pdf_url=report["storage"]["pdf_url"],
            report_url=report["storage"]["report_url"],
            status=report["compliance"]["status"],
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        for clause_data in report["analysis"]:
            clause = Clause(
                document_id=doc.id,
                title=clause_data["clause"]["title"],
                body=clause_data["clause"]["body"],
                pages=clause_data["clause"]["pages"]
            )
            db.add(clause)
            db.commit()
            db.refresh(clause)

            prediction = Prediction(
                clause_id=clause.id,
                best_rule=clause_data["llm_evaluation"].get("best_rule"),
                severity=clause_data["llm_evaluation"].get("severity", "low"),
                status=clause_data["llm_evaluation"].get("status", "red_flag"),
                reason=clause_data["llm_evaluation"].get("reason", ""),
                retrieved_rules=clause_data.get("retrieved_rules", []),
                llm_evaluation=clause_data.get("llm_evaluation", {}),
            )
            db.add(prediction)
            db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error storing analysis in DB: {e}")
    finally:
        db.close()

