CLAUSE_LABELS = ["Mutuality", "Confidentiality", "Exceptions", "Term",
                 "Indemnity", "Non-Solicitation", "Governing Law", "IP", "Other"]

RETRIEVED_POLICIES_COUNT = 3
CLAUSE_STATUS = ["OK", "Needs Review", "Red Flag"]
POLICY_SEVERITIES = ["low", "medium", "high", "critical"]

# Compliance Score computing
SEVERITY_WEIGHTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
STATUS_PENALTIES = {"OK": 0, "Needs Review": 1, "Red Flag": 3}