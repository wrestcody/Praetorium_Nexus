from pydantic import BaseModel
from datetime import datetime

class Finding(BaseModel):
    refined_risk_score: str
    nl_summary: str
    remediation_playbook_ref: str
    vanguard_timestamp: datetime
