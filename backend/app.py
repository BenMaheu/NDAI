import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import json
import time

from policy_matcher import analyze_nda, create_vectorstore, load_vectorstore, compute_compliance_score

load_dotenv()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["REPORTS_FOLDER"] = "reports"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)


# Init vector store for policy rules
# ---- INIT VECTORSTORE ONCE ----
VECTORSTORE_DIR = "./policy_vectorstore"
RULES_PATH = "policyRules.json"

# Check if vectorstore exists
if not os.path.exists(VECTORSTORE_DIR) or not os.listdir(VECTORSTORE_DIR):
    print("Creating policy vectorstore...")
    create_vectorstore(RULES_PATH, persist_dir=VECTORSTORE_DIR)

print("Loading policy vectorstore...")
coll = load_vectorstore(VECTORSTORE_DIR)
print("\nPolicy vectorstore ready !")


# Flask routes
@app.route("/analyze", methods=["POST"])
def analyze():
    t0 = time.time()
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
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

    # Save report for audit
    report_path = os.path.join(app.config["REPORTS_FOLDER"], f"{file.filename}_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)

    return jsonify(report), 200


@app.route("/reports", methods=["GET"])
def list_reports():
    reports = [f for f in os.listdir(app.config["REPORTS_FOLDER"]) if f.endswith("_report.json")]
    return jsonify({"reports": reports}), 200


@app.route("/reports/<report_name>", methods=["GET"])
def get_report(report_name):
    report_path = os.path.join(app.config["REPORTS_FOLDER"], report_name)
    if not os.path.exists(report_path):
        return jsonify({"error": "Report not found."}), 404

    with open(report_path, "r") as f:
        report = json.load(f)

    return jsonify(report), 200


#
# def classify_clause_llm(clause_title: str, clause_body: str, model: str = "gpt-4.1-mini", rounds: int = 3) -> str:
#     """Classifies a clause into one of the predefined types using OpenAI."""
#     prompt = f"""
#     You are a legal assistant. Categorize the following NDA clause
#     into one of these types:
#     {CLAUSE_LABELS}
#
#     Clause:
#     <clause_title>{clause_title}</clause_title>
#
#     <clause_body>
#     {clause_body}
#     </clause_body>
#
#     Answer with only the clause type, no explanations.
#     """
#
#     client = OpenAI(api_key=os.getenv["OPENAI_API_KEY"])
#     response = client.responses.create(
#         model=model,
#         input=prompt,
#     )
#
#     if response.output_text not in CLAUSE_LABELS:
#         response = classify_clause_llm(clause_title, clause_body, model=model, rounds=rounds - 1)
#
#     return response.output_text
#

if __name__ == "__main__":
    app.run(debug=True, port=5000)

    # Query example :
    # In /examples folder run:
    # curl -X POST -F "file=@investor_nda.pdf" http://localhost:5000/analyze_nda