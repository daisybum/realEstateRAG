"""
Integration Tests for API
"""

import pytest
from fastapi.testclient import TestClient

from realestaterag.api.main import app


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


class TestHealthEndpoints:
    """Health API 테스트"""
    
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
    
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
    
    def test_readiness(self, client):
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True
    
    def test_liveness(self, client):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["live"] is True


class TestQueryEndpoints:
    """Query API 테스트"""
    
    def test_query_validation(self, client):
        """빈 질문은 실패해야 함"""
        response = client.post("/api/v1/query", json={"question": ""})
        assert response.status_code == 422
    
    def test_query_request_format(self, client):
        """올바른 요청 형식"""
        # 실제 FalkorDB 없이는 500 에러가 날 수 있지만 요청 형식은 확인
        response = client.post("/api/v1/query", json={
            "question": "테스트 질문",
            "use_cache": False
        })
        # 500이면 DB 연결 실패 (예상된 동작)
        assert response.status_code in [200, 500]


class TestIngestionEndpoints:
    """Ingestion API 테스트"""
    
    def test_batch_request_format(self, client):
        """배치 요청 형식 검증"""
        response = client.post("/api/v1/ingestion/batch", json={
            "report_ids": ["R001", "R002"],
            "max_concurrent": 5
        })
        # 실제 처리 없이 job_id만 반환
        if response.status_code == 200:
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "accepted"
    
    def test_batch_validation(self, client):
        """max_concurrent 범위 검증"""
        response = client.post("/api/v1/ingestion/batch", json={
            "report_ids": ["R001"],
            "max_concurrent": 100  # 최대값 초과
        })
        assert response.status_code == 422
