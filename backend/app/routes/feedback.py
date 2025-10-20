from flask import Blueprint, jsonify, request
from app.db import SessionLocal, Document, Clause, Rejection, DocumentStatus
from app.services.rejections_vectorstore import add_rejection_to_vectorstore
from datetime import datetime

feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")


@feedback_bp.route("/documents/<int:doc_id>/accept", methods=["POST"])
def accept_document(doc_id):
    """Mark a document as accepted after legal review."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"error": f"Document {doc_id} not found"}), 404

        doc.status = DocumentStatus.accepted
        db.commit()
        return jsonify({"message": f"Document {doc.filename} marked as accepted"}), 200
    finally:
        db.close()


@feedback_bp.route("/documents/<int:doc_id>/decline", methods=["POST"])
def decline_document(doc_id):
    """Mark a document as declined after legal review."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"error": f"Document {doc_id} not found"}), 404

        doc.status = DocumentStatus.declined
        db.commit()
        return jsonify({"message": f"Document {doc.filename} marked as declined"}), 200
    finally:
        db.close()


@feedback_bp.route("/clauses/<int:clause_id>/reject", methods=["POST"])
def reject_clause(clause_id):
    """Store manual rejection feedback for a clause."""
    db = SessionLocal()
    try:
        clause = db.query(Clause).filter(Clause.id == clause_id).first()
        if not clause:
            return jsonify({"error": f"Clause {clause_id} not found"}), 404

        data = request.get_json() or {}
        comment = data.get("comment", "")
        new_status = data.get("new_status", "review")

        rejection = Rejection(
            clause_id=clause.id,
            comment=comment,
            new_status=new_status,
            created_at=datetime.utcnow(),
        )
        db.add(rejection)
        db.commit()

        # Add to persistent vectorstore
        add_rejection_to_vectorstore(rejection.id, clause.id, clause.body, comment, clause.document_id)

        return jsonify({
            "message": f"Clause {clause_id} rejected",
            "rejection_id": rejection.id,
            "timestamp": rejection.created_at.isoformat(),
        }), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()