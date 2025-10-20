from flask import Blueprint, request, jsonify
from app.services.llm import call_llm
from app.services.rejections_vectorstore import load_rejections_vectorstore
from app.config import Config

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("", methods=["POST"])
def chat_with_clause():
    """
    Interactive explanation/chat endpoint.
    Input:
        {
            "question": "Why is this clause risky?",
            "clause": "Full text of the clause",
            "reason": "LLM's justification text (optional)",
            "pages": [2, 3]
        }
    """
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        clause_text = data.get("clause", "").strip()
        reason = data.get("reason", "").strip() if data.get("reason") else ""
        status = data.get("status", "").strip() if data.get("status") else ""

        if not question:
            return jsonify({"error": "Missing 'question'"}), 400
        if not clause_text:
            return jsonify({"error": "Missing 'clause'"}), 400

        # --- Construct contextual prompt ---
        context_parts = [
            f"Clause text:\n{clause_text}",
            f"User question:\n{question}",
        ]
        if reason:
            context_parts.append(f"LLM original reasoning:\n{reason}")
        if status:
            context_parts.append(f"Clause flagged status:\n{status}")

        full_prompt = "\n\n".join(context_parts)

        # --- Call LLM ---
        answer = call_llm(
            prompt=full_prompt,
            model="gpt-4o-mini",
            temperature=0.4,
        )

        return jsonify({
            "answer": answer,
        })

    except Exception as e:
        print(f"❌ Error in /chat: {e}")
        return jsonify({"error": str(e)}), 500
