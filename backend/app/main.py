# Run using 'PYTHONPATH=backend python -m app.main' in NDAI project root
from flask import Flask
import os
from app.config import Config
from app.services.storage import ensure_materials_available
from app.routes.analyze import analyze_bp, init_vectorstore


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
    #  Importing here to load policy vectorstore after having downloaded GCS materials
    app.register_blueprint(analyze_bp)
    # app.register_blueprint(reports_bp)
    # app.register_blueprint(chat_bp)
    # app.register_blueprint(health_bp)

    # init_vectorstore()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8080)
