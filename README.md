# 🧠 NDA Analyzer

**NDA Analyzer** is an AI-powered legal assistant that automates the review of Non-Disclosure Agreements (NDAs).  
It extracts and analyzes contractual clauses using LLMs, evaluates compliance against internal policies, and enables legal teams to validate, reject, and comment on individual clauses through a user-friendly interface.

---

## 🚀 Overview

### ✳️ Core Features
- **Automated clause extraction** from uploaded NDA PDFs.  
- **Policy rule matching** using dense vector similarity (ChromaDB).  
- **LLM-based reasoning** for compliance, severity, and risk detection.  
- **Interactive human feedback** — reject or accept clauses.  
- **Chat assistant** providing detailed justifications for LLM evaluations.  
- **Persistent data** in a PostgreSQL database.  
- **Continuous improvement loop** through rejected clause embeddings.

---

## 🧱 Technology Stack

| Layer | Technology | Role |
|-------|-------------|------|
| **Frontend** | 🖥️ **Streamlit** | Interactive dashboard for uploads, analysis visualization, and feedback |
| **Backend** | ⚙️ **Flask** | REST API serving endpoints `/analyze`, `/documents`, `/chat`, `/feedback` |
| **Database** | 🐘 **PostgreSQL (Cloud SQL)** | Stores documents, clauses, predictions, and rejections |
| **Vectorstore** | 🧩 **ChromaDB** | Stores embeddings of rules and rejected clauses for similarity search |
| **LLM** | 🧠 **OpenAI GPT-4o / Mistral** | Analyzes clause meaning and provides compliance reasoning |
| **Storage** | ☁️ **Google Cloud Storage** | Stores uploaded PDFs, JSON reports, and ChromaDB snapshots |
| **Infrastructure** | 🚀 **Cloud Run + Cloud Build** | Serverless deployment of the Flask backend via CI/CD |
| **CI/CD** | 🤖 **GitHub Actions** | Automated build and deployment pipeline |

---

## ⚙️ End-to-End Workflow

### 1️⃣ Upload & Analysis
1. User uploads a PDF via `/analyze` or through the Streamlit interface.
2. The backend extracts textual clauses using PDF parsing.
3. Each clause is embedded and compared against internal compliance rules stored in a **policy vectorstore**.
4. The top-k matching rules are provided to an **LLM prompt** that classifies the clause:
   - **Status** → `OK`, `Needs Review`, `Red Flag`
   - **Severity** → `low`, `medium`, `high`, `critical`
   - **Reason** → LLM-generated textual explanation
5. The results are stored in the **PostgreSQL database** and exported as a JSON report.

### 2️⃣ Storage
- The original PDF and the generated report JSON are uploaded to **Google Cloud Storage**.
- Database relations are created:
  - A `Document` entry summarizing the file and compliance score.
  - `Clause` entries for each extracted segment.
  - `Prediction` entries containing the LLM analysis for each clause.

### 3️⃣ Human Review
- Legal counsel views the document in the **Streamlit UI**:
  - The dashboard shows compliance scores, clause-by-clause results, and reasoning.
  - Each clause can be **rejected** (manual feedback) or **approved**.
  - The entire NDA can be **accepted** or **declined** after review.

### 4️⃣ Feedback Loop
- Rejected clauses are:
  - Saved in the `rejections` table (with comment + timestamp).
  - Embedded and persisted in a **rejections ChromaDB collection**.
- On the next analysis, similar rejections are retrieved and injected into the LLM prompt — enabling continual improvement.

### 5️⃣ Chat & Explanations
- The `/chat` endpoint allows clause-specific Q&A:
  - User question + clause text + LLM reasoning + similar rejections.
  - The LLM returns contextual, explainable answers.

---

## 🧠 Backend Logic & Data Flow

```text
   ┌────────────┐       ┌──────────────┐       ┌───────────────┐       ┌──────────────┐
   │  PDF Upload│──────▶│ Flask /analyze│────▶ │ Policy Matcher │────▶ │  LLM Reasoner │
   └────────────┘       └──────────────┘       └───────────────┘       └──────────────┘
         │                                                     │
         ▼                                                     ▼
   Google Cloud Storage                                  PostgreSQL (Documents, Clauses, Predictions)
         │
         ▼
   Streamlit Dashboard  ◀───►  /documents  ◀───►  /chat  ◀───►  /feedback
```

⸻

## 🧩 Database Schema

---

### 🗃️ Table: `documents`

| **Column** | **Type** | **Description** |
|-------------|-----------|------------------|
| `id` | `INTEGER` | Primary key |
| `filename` | `VARCHAR` | Original filename of the uploaded NDA |
| `uploaded_at` | `TIMESTAMP` | Timestamp of the upload |
| `total_clauses` | `INTEGER` | Number of clauses extracted from the PDF |
| `compliance_score` | `FLOAT` | Global compliance score computed from clause-level evaluations |
| `compliance_details` | `JSON` | Detailed breakdown of clause statuses (OK, Needs Review, Red Flag) |
| `pdf_url` | `VARCHAR` | URL of the PDF stored in Google Cloud Storage |
| `report_url` | `VARCHAR` | URL of the generated JSON report |
| `status` | `ENUM(DocumentStatus)` | Document status: `to_review`, `safe`, `not_safe`, `accepted`, or `declined` |

**Purpose:**  
Stores metadata and overall compliance summary for each uploaded NDA.

---

### 📄 Table: `clauses`

| **Column** | **Type** | **Description** |
|-------------|-----------|------------------|
| `id` | `INTEGER` | Primary key |
| `document_id` | `INTEGER (FK → documents.id)` | Foreign key reference to the parent document |
| `title` | `VARCHAR` | Clause title or section header |
| `body` | `TEXT` | Full text of the clause |
| `pages` | `ARRAY[INTEGER]` | List of page numbers where the clause appears |
| `created_at` | `TIMESTAMP` | Timestamp of extraction |

**Purpose:**  
Represents individual clauses extracted from each document.

---

### 🤖 Table: `predictions`

| **Column** | **Type** | **Description** |
|-------------|-----------|------------------|
| `id` | `INTEGER` | Primary key |
| `clause_id` | `INTEGER (FK → clauses.id)` | Foreign key reference to the clause |
| `best_rule` | `VARCHAR` | Most relevant policy rule matched from vectorstore |
| `severity` | `VARCHAR` | Severity level: `low`, `medium`, `high`, `critical` |
| `status` | `VARCHAR` | Compliance classification: `OK`, `Needs Review`, or `Red Flag` |
| `reason` | `TEXT` | Explanation generated by the LLM |
| `retrieved_rules` | `JSON` | List of policy rules retrieved during semantic search |
| `llm_evaluation` | `JSON` | Full LLM response for traceability |
| `created_at` | `TIMESTAMP` | Timestamp of prediction |

**Purpose:**  
Contains LLM-generated analysis for each clause.

---

### ❌ Table: `rejections`

| **Column** | **Type** | **Description** |
|-------------|-----------|------------------|
| `id` | `INTEGER` | Primary key |
| `clause_id` | `INTEGER (FK → clauses.id)` | Foreign key reference to the rejected clause |
| `comment` | `TEXT` | Human feedback explaining the reason for rejection |
| `new_status` | `VARCHAR` | Updated clause status after review (`rejected`, `amended`, etc.) |
| `created_at` | `TIMESTAMP` | Timestamp of the rejection event |

**Purpose:**  
Logs human corrections and feedback from legal counsels.  
Used to populate the **rejections vectorstore**, improving future analyses.

---

## 🧬 Table Relationships (Summary)

| **From** | **To** | **Relationship** | **Cardinality** |
|-----------|---------|------------------|-----------------|
| `documents.id` | `clauses.document_id` | Document → Clauses | 1 → N |
| `clauses.id` | `predictions.clause_id` | Clause → Prediction | 1 → 1 |
| `clauses.id` | `rejections.clause_id` | Clause → Rejections | 1 → N |

---

**Schema Summary:**
- **4 core tables**: `documents`, `clauses`, `predictions`, `rejections`
- **1→N and 1→1 relationships** enable traceability from NDA → Clause → LLM Evaluation → Human Feedback  
- Optimized for **compliance auditing**, **explainability**, and **continuous learning** from feedback.

---
⸻

## 🧩 Vectorstores

|**Collection**|**Description**|**Location**|
|--------------|---------------|------------|
|`policy_vectorstore`|	Embeddings of internal compliance rules	Config.VECTORSTORE_DIR|
|`rejections_vectorstore`	|Embeddings of user-rejected clauses	Config.REJECTIONS_VECTORSTORE_DIR|

Both are persisted locally via ChromaDB and synced to GCS to survive Cloud Run restarts.

---



---

### 💬 Chat Endpoint Logic

When `/chat` is called:
1.	Retrieve clause text, reasoning, and user question.
2.	Query rejections_vectorstore for similar rejected clauses.
3.	Build a structured prompt:
```
Clause:
[clause text]

Original Reasoning:
[reason]

User question:
[question]

Similar Rejected Clauses:
[text + comments]
```

4.	Call the LLM (e.g. gpt-4o-mini) with temperature 0.4.
5.	Return an explanation like:

```
{
  "answer": "This clause is risky because it allows unilateral disclosure...",
  "retrieved_rejections": [...]
}
```


⸻
## 🖥️ Streamlit Interface

The **Streamlit dashboard** provides a complete visual and interactive layer on top of the Flask API and database.  
It’s designed for **legal counsels and compliance officers** to quickly assess NDA risk, approve or reject clauses, and understand LLM reasoning.

---

### 📂 Documents Tab

**Purpose:** Manage and review analyzed NDAs.

**Features:**
- Upload new NDA PDFs (triggers `/analyze` endpoint).
- View the list of all analyzed NDAs stored in PostgreSQL.
- Inspect metadata (filename, upload date, compliance score, status).
- **Accept** or **Decline** a document after review.
- Direct access to the associated report (JSON) and source PDF.

**Statuses:**
| Status | Meaning |
|--------|----------|
| 🟡 `to_review` | Waiting for legal review |
| 🟢 `safe` / `accepted` | No issues detected or validated |
| 🔴 `not_safe` / `declined` | Non-compliant NDA or rejected by counsel |

---

### 📊 Analysis Tab

**Purpose:** Deep-dive into a specific NDA’s clauses.

Each clause includes:
- **Clause text** with page reference and title  
- **LLM prediction** (status, severity, and reasoning)  
- **Policy rules** retrieved from the vectorstore  
- **Rejection button** (to trigger manual feedback)


#### Clause Rejection
When a user clicks **“Reject Clause”**, a comment can be entered explaining the reason for rejection.  
The system:
1. Saves the rejection in PostgreSQL (`rejections` table).
2. Embeds the clause text and stores it in **ChromaDB (`rejections_vectorstore`)**.
3. Syncs the updated vectorstore with GCS for persistence.
4. Future analyses will retrieve similar rejected clauses to refine the model’s behavior.

---

### 💬 Chat Tab

**Purpose:** Explain and explore clause reasoning interactively.

The chat interface allows users to ask follow-up questions about a clause.  
Example questions:
- “Why did the model consider this clause risky?”
- “Suggest safer wording aligned with company policy.”
- “Which rule triggered this red flag?”

**Backend logic:**
- Sends the question, clause text, and reasoning to the `/chat` endpoint.
- The backend retrieves similar rejected clauses from the vectorstore.
- Builds a structured LLM prompt combining:
  - The clause text  
  - The LLM’s original reasoning  
  - The user’s question  
  - Any retrieved rejected clauses
- Returns a contextual, human-readable explanation.

**Example response:**
> _“This clause is flagged because it limits confidentiality to only six months.  
> Similar clauses were previously rejected for the same reason. Consider extending to 24 months.”_

---

### ⚙️ Admin Tab (Coming Soon)

**Purpose:** Manage internal rule sets and model retraining.

Planned features:
- Upload a new `policyRules.json` file defining compliance policies.
- Rebuild the **policy vectorstore** from the uploaded rules.
- Trigger retraining or reindexing jobs.
- Manage user feedback integration (audit trail of clause decisions).

**Example UI components:**
- JSON file uploader (for `policyRules.json`)
- “Rebuild Vectorstore” button
- Feedback database overview

---

## 🧩 Feedback Loop Summary

| Step | Component | Description |
|------|------------|-------------|
| 1️⃣ | Clause rejected in UI | User provides comment (manual correction) |
| 2️⃣ | `/feedback` API | Records rejection in database |
| 3️⃣ | Vectorstore update | Clause text embedded into `rejections_vectorstore` |
| 4️⃣ | Cloud sync | Local Chroma index synced to GCS |
| 5️⃣ | LLM prompt | Similar rejected clauses retrieved in next analysis |
| ✅ | Continuous learning | The system improves at spotting unwanted clauses |

---

## ☁️ Deployment Summary

| Component | Platform | Description |
|------------|-----------|-------------|
| **Flask Backend** | Google Cloud Run | Serverless REST API |
| **PostgreSQL DB** | Cloud SQL | Persistent relational storage |
| **Vectorstores** | ChromaDB + GCS | Embedding databases (policy + rejections) |
| **Frontend UI** | Streamlit | Hosted app for human interaction |
| **CI/CD** | GitHub Actions + Cloud Build | Continuous deployment pipeline |

The Streamlit app can be deployed either:
- As a **Cloud Run service**, containerized alongside the backend, or
- As a **static frontend** hosted on **Google Cloud Storage** (with backend API calls routed to Cloud Run).

---

## 🔮 Future Directions

- ❌**Fix**: if red flag alert on critical severity policies are present
- 🧠 Incorporate rejected clause embeddings directly in the policy matcher  
- 🧾 Generate full compliance reports (PDF summaries)  
- 🔐 Add authentication and role-based access (multi-user support)  
- 🧱 Introduce versioning of `policyRules.json` for auditing  
- 📊 Add analytics dashboard (model accuracy, review time, etc.)  
- 🧬 Experiment with fine-tuning on internal NDA datasets  

---

## 📜 License

MIT © 2025 — Developed by **Benjamin Maheu**

Built with ❤️ using:
> **Flask**, **Streamlit**, **PostgreSQL**, **ChromaDB**, **OpenAI GPT-4o**, and **Google Cloud Platform**
