from fastapi.testclient import TestClient
from app.main import app

def test_live():
    c = TestClient(app)
    r = c.get("/api/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"