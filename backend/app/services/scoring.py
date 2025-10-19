from typing import List
from app.config import POLICY_SEVERITIES, SEVERITY_WEIGHTS, STATUS_PENALTIES, COMPLIANT_SCORE_THRESHOLD, AMBIGUOUS_SCORE_THRESHOLD

def compute_compliance_score(results: List[dict]) -> dict:
    total_penalty = 0
    max_possible_penalty = 0
    severity_summary = {s: 0 for s in POLICY_SEVERITIES}

    for r in results:
        eval = r.get("llm_evaluation", {})
        severity = eval.get("severity", "medium").lower()
        status = eval.get("status", "Needs Review")

        weight = SEVERITY_WEIGHTS.get(severity, 2)
        penalty = STATUS_PENALTIES.get(status, 1)
        total_penalty += weight * penalty
        max_possible_penalty += weight * STATUS_PENALTIES["Red Flag"]
        severity_summary[severity] += 1

    if max_possible_penalty == 0:
        score = 100.0
    else:
        score = max(0.0, 100.0 * (1 - total_penalty / max_possible_penalty))

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
            "by_severity": severity_summary
        }
    }
