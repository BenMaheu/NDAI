import os
import json
import time
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from urllib.parse import urlparse

st.set_page_config(page_title="NDA Analyzer", layout="wide")

# ---------------------------- Config ----------------------------
API_BASE = "https://nda-analyzer-961479672047.europe-west10.run.app"

with st.sidebar:
    st.header("⚙️ Settings")
    api_base_input = st.text_input("API Base URL", API_BASE)
    if api_base_input and api_base_input != API_BASE:
        API_BASE = api_base_input.rstrip("/")
    st.caption("Your deployed Cloud Run API base (e.g., https://nda-analyze-dev-xxxxxx.run.app)")
    if st.button("🔄 Reset Session"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.experimental_rerun()

# Initialize session state
st.session_state.setdefault("analysis", None)
st.session_state.setdefault("selected_doc_id", None)
st.session_state.setdefault("chat_thread", [])
st.session_state.setdefault("selected_clause", None)


# --------------------------- Helpers ----------------------------
def sev_badge(status: str):
    colors = {
        "OK": ("#dcfce7", "#166534"),  # green
        "NEEDS_REVIEW": ("#fef9c3", "#92400e"),  # orange/yellow
        "RED_FLAG": ("#fee2e2", "#991b1b"),  # red
    }
    bg, color = colors.get(status.upper(), ("#f3f4f6", "#111827"))
    return f"<span style='background:{bg};color:{color};padding:3px 10px;border-radius:12px;font-weight:600;font-size:12px'>{status}</span>"


def compliance_gauge(score):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(score or 0),
            title={"text": "Compliance Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#10b981"},
                "steps": [
                    {"range": [0, 60], "color": "#fef2f2"},
                    {"range": [60, 80], "color": "#fffbeb"},
                    {"range": [80, 100], "color": "#ecfdf5"},
                ],
            },
        )
    )
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)


def load_documents():
    try:
        res = requests.get(f"{API_BASE}/documents", timeout=20)
        if res.ok:
            return res.json()
        st.error(f"API error: {res.text}")
    except Exception as e:
        st.error(f"Failed to load documents: {e}")
    return []


def load_document_details(doc_id):
    try:
        res = requests.get(f"{API_BASE}/documents/{doc_id}", timeout=30)
        if res.ok:
            return res.json()
        st.error(f"Error {res.status_code}: {res.text}")
    except Exception as e:
        st.error(f"Failed to fetch document details: {e}")
    return None


def call_chat(question, clause):
    body = {"question": question}
    if clause:
        body["clause"] = clause.get("body", "")
        body["pages"] = clause.get("pages", [])
    try:
        res = requests.post(f"{API_BASE}/chat", json=body, timeout=120)
        if res.ok:
            js = res.json()
            return js.get("answer") or js.get("message") or json.dumps(js)
        return f"(Chat API error {res.status_code})"
    except Exception as e:
        return f"(Chat unavailable) {e}"


def analyze_pdf(uploaded_file) -> dict:
    """POST /analyze with the uploaded PDF. Returns JSON or raises."""
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
    # Simulate progress while request is in flight
    prog = st.progress(0)
    t0 = time.time()
    try:
        # We emulate upload progress by ticking while waiting; Cloud Run won't stream progress
        for i in range(10):
            prog.progress(min(95, (i + 1) * 9))
            time.sleep(2)
        res = requests.post(f"{API_BASE}/analyze", files=files, timeout=900)
        if not res.ok:
            raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
        data = res.json()
        prog.progress(100)
        return data
    finally:
        elapsed = time.time() - t0
        st.caption(f"⏱️ Elapsed: {elapsed:.1f}s")


# --------------------------- UI Tabs ----------------------------
tabs = st.tabs(["📂 Documents", "📊 Analysis", "💬 Chat", "⚙️ Admin"])

# --------------------------- Tab 0: Documents --------------------
with tabs[0]:
    st.header("📤 Upload new NDA")

    uploaded = st.file_uploader("Upload NDA (PDF)", type=["pdf"])
    if uploaded and st.button("Analyze PDF", type="primary"):
        with st.spinner("Analyzing on Cloud Run..."):
            try:
                data = analyze_pdf(uploaded)
                st.session_state["analysis"] = data
                st.success(f"✅ Analysis complete — {data.get('total_clauses', 0)} clauses found")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    st.markdown("---")
    st.header("📂 Analyzed Documents")
    docs = load_documents()
    if not docs:
        st.info("No documents found in database yet. Try uploading one via the Flask API.")
    else:
        df = pd.DataFrame(docs)
        df_display = df[["id", "filename", "uploaded_at", "compliance_score", "status"]]
        st.dataframe(df_display, hide_index=True, use_container_width=True)

        selected_id = st.selectbox("Select a document to view", df["id"],
                                   format_func=lambda x: df.loc[df["id"] == x, "filename"].values[0])
        if selected_id:
            st.session_state["selected_doc_id"] = selected_id
            doc = load_document_details(selected_id)
            if doc:
                st.session_state["analysis"] = doc
                st.success(f"Loaded document '{doc['filename']}'")

                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**Filename:** {doc['filename']}")
                    st.markdown(f"**Uploaded:** {doc['uploaded_at']}")
                    st.markdown(f"**Clauses:** {doc['total_clauses']}")
                    st.markdown(f"**Status:** {doc['status']}")
                with c2:
                    compliance_gauge(doc.get("compliance_score", 0))

    st.markdown("### Review Decision")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Accept Document", use_container_width=True):
            st.success("Document marked as *Accepted* (endpoint coming soon)")
            res = requests.post(f"{API_BASE}/feedback/documents/{doc['id']}/accept")
            st.success("NDA marked as *Accepted*")
    with col2:
        if st.button("❌ Decline Document", use_container_width=True):
            res = requests.post(f"{API_BASE}/feedback/documents/{doc['id']}/decline")
            st.warning("NDA marked as *Declined*")

# --------------------------- Tab 1: Analysis ---------------------
with tabs[1]:
    st.header("📊 Document Analysis")

    data = st.session_state.get("analysis")
    if not data or "clauses" not in data:
        st.info("Select a document in the 'Documents' tab to view its analysis.")
        st.stop()

    clauses = data["clauses"]
    df = pd.DataFrame([
        {
            "id": c["id"],
            "title": c.get("title"),
            "pages": ", ".join(map(str, c.get("pages", []))),
            "status": (c["prediction"] or {}).get("status", "NEEDS_REVIEW"),
            "severity": (c["prediction"] or {}).get("severity", "medium"),
            "reason": (c["prediction"] or {}).get("reason", ""),
        }
        for c in clauses
    ])

    st.dataframe(df[["id", "title", "status", "severity", "pages"]], hide_index=True, use_container_width=True)

    clause_choice = st.selectbox(
        "Select clause to inspect",
        options=df["id"],
        format_func=lambda cid: df.loc[df["id"] == cid, "title"].values[0] or f"Clause {cid}"
    )
    clause = next((c for c in clauses if c["id"] == clause_choice), None)
    if clause:
        st.subheader(f"Clause {clause['id']}")
        st.markdown(f"**Pages:** {', '.join(map(str, clause['pages']))}")
        st.markdown(f"**Status:** {sev_badge((clause['prediction'] or {}).get('status', 'NEEDS_REVIEW'))}",
                    unsafe_allow_html=True)
        st.write(clause["body"])

        pred = clause.get("prediction")
        if pred:
            st.markdown("**Reason:**")
            status = (pred.get("status") or "NEEDS_REVIEW").upper()
            color_map = {
                "OK": ("#dcfce7", "#166534"),
                "NEEDS_REVIEW": ("#fef9c3", "#92400e"),
                "RED_FLAG": ("#fee2e2", "#991b1b"),
            }
            bg, color = color_map.get(status, ("#f3f4f6", "#111827"))
            reason_text = pred.get("reason") or "No reason provided."
            st.markdown(
                f"<div style='background:{bg};color:{color};padding:10px;border-radius:8px'>{reason_text}</div>",
                unsafe_allow_html=True,
            )
            if pred.get("retrieved_rules"):
                st.markdown("**Retrieved Matching Policy Rules:**")
                for r in pred["retrieved_rules"]:
                    st.markdown(f"- **{r.get('title')}** — *{r.get('severity')}*")

        # Reject clause button
        st.divider()
        st.markdown("### Feedback Actions")

        if st.button("🚫 Reject Clause", key=f"reject_{clause['id']}"):
            st.warning("Clause flagged for review (endpoint coming soon)")
            comment = st.text_area("Reason for rejection (optional):", key=f"rej_{clause['id']}")
            res = requests.post(
                f"{API_BASE}/feedback/clauses/{clause['id']}/reject",
                json={"comment": comment, "new_status": "rejected"}
            )
            if res.ok:
                st.success("Clause rejection recorded.")
            else:
                st.error(f"Error: {res.text}")

        # Chat clause
        st.markdown("---")
        st.subheader("💬 Ask about this clause")

        # Display previous chat messages (clause-specific)
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = {}

        clause_id = clause["id"]
        if clause_id not in st.session_state["chat_history"]:
            st.session_state["chat_history"][clause_id] = []

        for msg in st.session_state["chat_history"][clause_id]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # New user message input
        if prompt := st.chat_input(f"Ask a question about clause '{clause.get('title') or clause_id}'..."):
            st.session_state["chat_history"][clause_id].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    answer = call_chat(prompt, clause)
                    st.write(answer)

            st.session_state["chat_history"][clause_id].append({"role": "assistant", "content": answer})

        st.session_state["selected_clause"] = clause

# --------------------------- Tab 2: Chat -------------------------
with tabs[2]:
    st.header("💬 Clause Assistant")
    clause = st.session_state.get("selected_clause")
    if not clause:
        st.info("Select a clause from the Analysis tab to start chatting.")
        st.stop()

    st.caption(f"Context: Clause #{clause['id']} (pages {', '.join(map(str, clause['pages']))})")

    for msg in st.session_state["chat_thread"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_q = st.chat_input("Ask a question about this clause…")
    if user_q:
        st.session_state["chat_thread"].append({"role": "user", "content": user_q})
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                answer = call_chat(user_q, clause)
                st.write(answer)
        st.session_state["chat_thread"].append({"role": "assistant", "content": answer})

# --------------------------- Tab 3: Admin ---------------------
with tabs[3]:
    st.subheader("⚙️ Rule Management (Coming Soon)")
    st.caption("Connect to your JSON-based policy rules .")

    st.markdown("**Import policyRules.json**")
    st.file_uploader("Upload policyRules.json", type=["json"], disabled=True, key="rules_upload")
    st.button("Rebuild Vector Store", disabled=True)
