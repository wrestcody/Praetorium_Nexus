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
