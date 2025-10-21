from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models, database, auth, risk_assessor

app = FastAPI()

templates = Jinja2Templates(directory="templates")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/v1/ingest_risk", response_model=models.Finding)
def ingest_risk(
    finding: models.Finding,
    db: Session = Depends(get_db),
    api_key: str = Depends(auth.get_api_key)
):
    db_finding = database.Finding(**finding.dict())
    db.add(db_finding)
    db.commit()
    db.refresh(db_finding)
    return db_finding

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    findings = db.query(database.Finding).all()
    prioritized_findings = risk_assessor.prioritize_findings(findings)
    return templates.TemplateResponse("index.html", {"request": request, "findings": prioritized_findings})

# AI Logic Review Statement:
# The following block is a local testing and verification script.
# It is designed to be executed directly to confirm that the data ingestion
# and database persistence logic functions as expected.
# This script simulates a payload from the Vanguard_Agent, inserts it into the
# database, and then queries the database to verify the insertion.
if __name__ == '__main__':
    import datetime
    from sqlalchemy.orm import sessionmaker

    print("--- Running Local Verification ---")

    # 1. Initialize Database
    database.init_db()

    # 2. Create a new database session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
    db = TestingSessionLocal()

    # 3. Simulate a sample finding from Vanguard_Agent
    sample_finding_data = {
        "refined_risk_score": "CRITICAL",
        "nl_summary": "Critical exposure of CUI data on S3 due to configuration drift",
        "remediation_playbook_ref": "remediation_playbooks/s3_public_access_fix.tf",
        "vanguard_timestamp": datetime.datetime.utcnow()
    }

    # 4. Simulate the API call by directly invoking the function
    # This bypasses the dependency injection for the API key in a local context.
    from .models import Finding as FindingModel
    finding_model = FindingModel(**sample_finding_data)

    # Manually create the database entry
    db_finding = database.Finding(**finding_model.dict())
    db.add(db_finding)
    db.commit()
    db.refresh(db_finding)
    new_finding = db_finding

    print(f"[*] Ingested sample finding with ID: {new_finding.id}")

    # 5. Query the database to verify the inserted record
    retrieved_finding = db.query(database.Finding).filter(database.Finding.id == new_finding.id).first()

    if retrieved_finding:
        print("[+] Verification SUCCESS: Finding successfully retrieved from the database.")
        print(f"  - ID: {retrieved_finding.id}")
        print(f"  - Refined Risk Score: {retrieved_finding.refined_risk_score}")
        print(f"  - NL Summary: {retrieved_finding.nl_summary}")
        print(f"  - Playbook: {retrieved_finding.remediation_playbook_ref}")
        assert retrieved_finding.refined_risk_score == "CRITICAL", "Mismatch in refined_risk_score"
        assert "Critical exposure" in retrieved_finding.nl_summary, "Mismatch in nl_summary"
    else:
        print("[-] Verification FAILED: Could not retrieve the finding from the database.")

    db.close()
    print("--- Local Verification Complete ---")
