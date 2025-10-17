# Run using 'PYTHONPATH=backend python -m app.main' in NDAI project root
from flask import Flask
import os
from app.routes.analyze import analyze_bp
from app.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Create default folders
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)

    # Register blueprints
    app.register_blueprint(analyze_bp)
    # app.register_blueprint(reports_bp)
    # app.register_blueprint(chat_bp)
    # app.register_blueprint(health_bp)
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
