from typing import List
from . import database

SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}

def prioritize_findings(findings: List[database.Finding]) -> List[database.Finding]:
    """
    Sorts findings based on the refined_risk_score.
    """
    return sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(f.refined_risk_score, 4)
    )
