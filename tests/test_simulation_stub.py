# 통합 테스트는 실제 키가 필요하므로 여기서는 최소 라우팅만 검증
from fastapi.testclient import TestClient
from app.main import app

def test_root():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200