# Run using 'PYTHONPATH=backend python -m app.main' in NDAI project root
from flask import Flask
import os
from app.config import Config
from app.services.storage import ensure_materials_available
from app.routes.analyze import analyze_bp
from app.routes.health import health_bp
from app.routes.documents import docs_bp
from app.db import init_db


def create_app():
    print("Starting NDAI backend application...")
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize database
    try:
        init_db()
    except Exception as e:
        print(f"Error initializing database: {e}")

    # Create default folders
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)

    # If running in Cloud Run (GCS bucket is defined)
    gcs_bucket = app.config.get("GCS_BUCKET")
    if gcs_bucket:
        print("GCS bucket detected. Ensuring materials are available locally...")
        ensure_materials_available(
            gcs_bucket,
            local_rules_path=app.config["POLICY_RULES_PATH"],
            local_vector_dir=app.config["VECTORSTORE_DIR"]
        )

    # Register blueprints
    app.register_blueprint(analyze_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(docs_bp)
    # app.register_blueprint(reports_bp)
    # app.register_blueprint(chat_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8080)
