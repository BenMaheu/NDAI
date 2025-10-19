from flask import Blueprint, jsonify
from app.routes.analyze import ensure_vectorstore_loaded

health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.route("", methods=["GET"])
def health():
    ensure_vectorstore_loaded()
    return jsonify({"status": "ok", "vectorstore_loaded": True}), 200
