from typing import List
from app.config import (
    POLICY_SEVERITIES,
    SEVERITY_WEIGHTS,
    STATUS_PENALTIES,
    COMPLIANT_SCORE_THRESHOLD,
    AMBIGUOUS_SCORE_THRESHOLD,
)


def compute_compliance_score(results: List[dict]) -> dict:
    """
    Compute document-level compliance score and status based on clause-level evaluations.

    Rules:
    - Weighted score based on severity × penalty.
    - If any clause has severity ∈ {"high", "critical"} AND status == "Red Flag",
      the whole document is automatically "not_safe".
    """

    total_penalty = 0
    max_possible_penalty = 0
    severity_summary = {s: 0 for s in POLICY_SEVERITIES}
    immediate_fail = False

    for r in results:
        eval = r.get("llm_evaluation", {})
        severity = eval.get("severity", "medium").lower()
        status = eval.get("status", "Needs Review")

        # Defensive fallback
        if severity not in POLICY_SEVERITIES:
            severity = "medium"
        if status not in STATUS_PENALTIES:
            status = "Needs Review"

        # Immediate fail condition
        if severity in {"high", "critical"} and status == "Red Flag":
            immediate_fail = True

        # Weighted penalty accumulation
        weight = SEVERITY_WEIGHTS.get(severity, 2)
        penalty = STATUS_PENALTIES.get(status, 1)
        total_penalty += weight * penalty
        max_possible_penalty += weight * STATUS_PENALTIES["Red Flag"]
        severity_summary[severity] += 1

    # If no clauses, assume safe
    if not results:
        return {
            "compliance_score": 100.0,
            "status": "safe",
            "details": {"clauses": 0, "by_severity": severity_summary}
        }

    # Immediate “not_safe” condition
    if immediate_fail:
        return {
            "compliance_score": 0.0,
            "status": "not_safe",
            "details": {
                "reason": "High- or critical-severity clause flagged as Red Flag",
                "total_penalty": total_penalty,
                "clauses": len(results),
                "by_severity": severity_summary,
            },
        }

    # Otherwise compute weighted compliance score
    score = max(0.0, 100.0 * (1 - total_penalty / max_possible_penalty)) if max_possible_penalty > 0 else 100.0

    if score > COMPLIANT_SCORE_THRESHOLD:
        status = "safe"
    elif score > AMBIGUOUS_SCORE_THRESHOLD:
        status = "to_review"
    else:
        status = "not_safe"

    return {
        "compliance_score": round(score, 2),
        "status": status,
        "details": {
            "total_penalty": total_penalty,
            "max_possible_penalty": max_possible_penalty,
            "clauses": len(results),
            "by_severity": severity_summary,
        },
    }
