import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "backend/uploads")
    REPORT_FOLDER = os.getenv("REPORT_FOLDER", "backend/reports")

    POLICY_RULES_PATH = os.getenv("POLICY_RULES_PATH", "backend/policyRules.json")
    VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", "backend/policy_vectorstore")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GCS_BUCKET = os.getenv("GCS_BUCKET")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


CLAUSE_LABELS = ["Mutuality", "Confidentiality", "Exceptions", "Term",
                 "Indemnity", "Non-Solicitation", "Governing Law", "IP", "Other"]

RETRIEVED_POLICIES_COUNT = 3
CLAUSE_STATUS = ["OK", "Needs Review", "Red Flag"]
POLICY_SEVERITIES = ["low", "medium", "high", "critical"]

# Compliance Score computing
SEVERITY_WEIGHTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
STATUS_PENALTIES = {"OK": 0, "Needs Review": 1, "Red Flag": 3}
