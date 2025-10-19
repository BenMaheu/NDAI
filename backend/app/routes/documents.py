from flask import Blueprint, jsonify
from app.db import SessionLocal, Document

docs_bp = Blueprint("documents", __name__, url_prefix="/documents")


@docs_bp.route("", methods=["GET"])
def list_documents():
    db = SessionLocal()
    try:
        docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
        data = [
            {
                "id": d.id,
                "filename": d.filename,
                "uploaded_at": d.uploaded_at.isoformat(),
                "compliance_score": d.compliance_score,
                "status": d.status.value if d.status else None,
                "report_url": d.report_url,
            }
            for d in docs
        ]
        return jsonify(data)
    finally:
        db.close()


@docs_bp.route("/<int:doc_id>", methods=["GET"])
def get_document(doc_id: int):
    """Return a detailed view of one document, including clauses and predictions."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"error": f"Document {doc_id} not found"}), 404

        clauses_data = []
        for clause in doc.clauses:
            prediction = clause.prediction
            rejections = [
                {
                    "id": r.id,
                    "comment": r.comment,
                    "new_status": r.new_status.value if r.new_status else None,
                    "created_at": r.created_at.isoformat(),
                }
                for r in clause.rejections
            ]

            clauses_data.append({
                "id": clause.id,
                "title": clause.title,
                "body": clause.body,
                "pages": clause.pages,
                "prediction": {
                    "best_rule": prediction.best_rule if prediction else None,
                    "severity": prediction.severity.value if prediction and prediction.severity else None,
                    "status": prediction.status.value if prediction and prediction.status else None,
                    "reason": prediction.reason if prediction else None,
                    "retrieved_rules": prediction.retrieved_rules if prediction else [],
                    "llm_evaluation": prediction.llm_evaluation if prediction else None,
                } if prediction else None,
                "rejections": rejections,
            })

        response = {
            "id": doc.id,
            "filename": doc.filename,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "total_clauses": doc.total_clauses,
            "compliance_score": doc.compliance_score,
            "status": doc.status.value if doc.status else None,
            "pdf_url": doc.pdf_url,
            "report_url": doc.report_url,
            "clauses": clauses_data,
        }

        return jsonify(response), 200
    finally:
        db.close()
