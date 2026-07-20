from fastapi.testclient import TestClient
from trading_ai.ui.research_workstation_app import create_research_workstation_app
def main():
    c=TestClient(create_research_workstation_app())
    h=c.get("/api/research-scanner/health"); assert h.status_code==200,h.text
    assert h.json()["milestone"]=="34"
    p=c.get("/"); assert p.status_code==200 and "Institutional Research Workstation" in p.text
    assert "Run Institutional Scan" in p.text and "Ranked Trade Candidates" in p.text
    print("All Milestone 34 Phase 1 Step 5 scanner API/dashboard assertions passed.")
if __name__=="__main__": main()
