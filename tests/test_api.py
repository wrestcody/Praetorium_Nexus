import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, SessionLocal

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()
    yield
    # You might want to add cleanup logic here if needed

def test_ingest_risk_success():
    headers = {"X-API-Key": "supersecretapikey"}
    payload = {
        "refined_risk_score": "Critical",
        "nl_summary": "This is a critical risk.",
        "remediation_playbook_ref": "playbooks/critical_risk.tf",
        "vanguard_timestamp": "2025-10-21T13:30:00Z"
    }
    response = client.post("/api/v1/ingest_risk", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["refined_risk_score"] == "Critical"
    assert data["nl_summary"] == "This is a critical risk."

def test_ingest_risk_invalid_api_key():
    headers = {"X-API-Key": "invalidkey"}
    payload = {
        "refined_risk_score": "High",
        "nl_summary": "This is a high risk.",
        "remediation_playbook_ref": "playbooks/high_risk.tf",
        "vanguard_timestamp": "2025-10-21T13:35:00Z"
    }
    response = client.post("/api/v1/ingest_risk", headers=headers, json=payload)
    assert response.status_code == 403

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Praetorium Nexus - Risk Findings" in response.text
    assert "This is a critical risk." in response.text
