# 🧠 NDAI

**NDAI** is a Flask-based AI tool that automatically evaluates **Non-Disclosure Agreements (NDAs)** against an internal **policy checklist**, using a **semantic vector search (Chroma)** and **LLM-based legal reasoning**.

The system performs clause-level analysis, detects red flags, and outputs a structured compliance report with an overall risk score.

---

## 🚀 Features

* 📄 **Automatic NDA Analysis (PDF)**

  * OCR-based text extraction
  * Clause segmentation using section titles (e.g., “1. Purpose”, “6. Indemnity”)
* 🧩 **Semantic Rule Matching**

  * Each clause is compared to internal policy rules stored in a **Chroma vectorstore**
* ⚖️ **LLM Legal Reasoning**

  * For each clause, the LLM determines:

    * The most relevant policy rule
    * Compliance status (`OK`, `Needs Review`, or `Red Flag`)
    * Associated severity (`low` → `critical`)
    * A concise legal justification
* 📊 **Global Compliance Score**

  * Weighted risk score based on clause severities and statuses
  * Returns a normalized score (`compliance_score` out of 100)
* 🧾 **Auditable Reports**

  * Full JSON reports stored in `/reports`
  * Accessible via `/reports` and `/reports/<filename>`

---

## 🧰 Tech Stack

| Component                                    | Purpose                                     |
| -------------------------------------------- | ------------------------------------------- |
| **Flask**                                    | REST API for uploads, analysis, and reports |
| **ChromaDB**                                 | Vector database for policy rule embeddings  |
| **SentenceTransformer** (`all-MiniLM-L6-v2`) | Lightweight open-source embedding model     |
| **OpenAI GPT-4-mini**                        | Legal reasoning and clause evaluation       |
| **PyTesseract + pdf2image**                  | OCR-based PDF text extraction               |
| **dotenv**                                   | Environment variable management             |
| **Python 3.10+**                             | Recommended runtime                         |

---

## 📁 Project Structure

```
.
├── backend                        # backend
    ├── app.py                     # Flask backend
    ├── policy_matcher.py          # Core logic: LLM reasoning + vectorstore + PDF parsing
    ├── policyRules.json           # Full set of compliance policy rules
    ├── config.py                  # Config file
    ├── .env.example               # .env template (Fill in your OpenAI API key)
    ├── policy_vectorstore/        # Persistent Chroma vectorstore (auto-created)
    ├── uploads/                   # Uploaded PDF files
    └── reports/                   # JSON audit reports
├── examples                       # example NDA PDFs for testing
├── .gitignore                     
├── poetry.lock
└── pyproject.toml                 # Requirements and project metadata

```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone <your-repo>
cd ndai
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
poetry install
pip install torch
```

> ⚠️ **Dependencies**
>
> * `pdf2image` requires **Poppler**
> * `sentence-transformers` requires **torch** which is not well handled by poetry
> * Install Poppler:
>
>   * macOS → `brew install poppler`
>   * Ubuntu/Debian → `apt install poppler-utils tesseract-ocr`
>   * Docker → use `minidocks/poppler` or add it via `apt`

### 4. Add your OpenAI API key

Create a `.env` file:

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

---

## 🧱 Initializing the Vectorstore

When you run the app for the first time, it automatically:

1. Checks if `./policy_vectorstore` exists.
2. If not, creates it from `policyRules.json`.

You can also initialize it manually:

```bash
python -c "from policy_matcher import create_vectorstore; create_vectorstore('policyRules.json', persist_dir='./policy_vectorstore')"
```

---

## ⚖️ Compliance Scoring

Each clause is rated based on:

* **Status:** `OK`, `Needs Review`, `Red Flag`
* **Severity:** `low`, `medium`, `high`, `critical`

| Severity | Weight | Status       | Penalty |
| -------- | ------ | ------------ | ------- |
| low      | 1      | OK           | 0       |
| medium   | 2      | Needs Review | 1       |
| high     | 3      | Red Flag     | 3       |
| critical | 4      | —            | —       |

> **Final score formula:**
>
> ```
> compliance_score = 100 × (1 − total_penalty / max_possible_penalty)
> ```

This gives a normalized compliance score between `0` (high risk) and `100` (fully compliant).

---

## 🧠 End-to-End Flow

### 1. Start the Flask server

```bash
python app.py
```

Expected logs:

```
Creating policy vectorstore...
Loading policy vectorstore...
Policy vectorstore ready !
 * Running on http://127.0.0.1:5000
```

---

### 2. Analyze an NDA (example)

```bash
curl -X POST -F "file=@investor_nda.pdf" http://localhost:5000/analyze
```

Response example:

```json
{
  "filename": "investor_nda.pdf",
  "total_clauses": 11,
  "time_seconds": 6.76,
  "compliance": {
    "compliance_score": 82.5,
    "details": {
      "total_penalty": 24,
      "max_possible_penalty": 40,
      "clauses": 11,
      "by_severity": {
        "low": 2,
        "medium": 4,
        "high": 3,
        "critical": 2
      }
    }
  },
  "analysis": [
    {
      "clause": "6. Indemnity...",
      "retrieved_rules": [...],
      "llm_evaluation": {
        "best_rule": "Indemnities Prohibited",
        "severity": "critical",
        "status": "Red Flag",
        "reason": "Contains indemnity obligation contrary to NDA policy."
      }
    },
    ...
  ]
}
```

---

### 3. Access reports

List all reports:

```bash
curl http://localhost:5000/reports
```

Retrieve a specific report:

```bash
curl http://localhost:5000/reports/investor_nda.pdf_report.json
```

---

## 🧩 Next Steps

* UI using Streamlit
  * If NDA is not safe --> Allow for re-upload then check diff then check if clause is now valid.
* API 
  * authentication + rate limiting
  * Caching
  * For each clause give page number and line number from original PDF
* Docker containerization
* PostGreSQL integration for report storage and persistent analysed clause storage
* **Cost monitoring**
* **Add concurrency (async + semaphore)** to parallelize LLM calls safely.
* **Add a simple dashboard** (Flask + Chart.js or React) to visualize the compliance score.
* **Fine-tune the LLM prompts** to generate richer justifications and risk recommendations.

---

## 🧑‍💻 Author

**Benjamin Maheu**
Lead AI Data Scientist — specializing in Deep Learning, Legal NLP, and Explainable AI.
Built with ❤️ for practical AI compliance auditing.