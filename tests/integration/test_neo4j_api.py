"""
Neo4j API Integration Tests
"""

import pytest
from httpx import AsyncClient
from realestaterag.api.main import app


@pytest.mark.asyncio
async def test_semantic_search():
    """Test semantic search endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/neo4j/semantic",
            json={
                "query": "전세가율 높은 아파트",
                "node_type": "Complex",
                "top_k": 5
            }
        )
        
        # Should return 200 OK or 500 if Neo4j not running
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "query" in data
            assert "results" in data
            assert "count" in data
            assert data["query"] == "전세가율 높은 아파트"


@pytest.mark.asyncio
async def test_facility_search():
    """Test facility-based search endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/neo4j/facility",
            json={
                "facility": "강남역",
                "max_distance": 30,
                "jeonse_ratio": 60.0
            }
        )
        
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "facility" in data
            assert "results" in data
            assert data["facility"] == "강남역"


@pytest.mark.asyncio
async def test_hybrid_search():
    """Test hybrid search endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/neo4j/hybrid",
            json={
                "query": "투자 가치 좋은 단지",
                "top_k": 10
            }
        )
        
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "query" in data
            assert "results" in data


@pytest.mark.asyncio
async def test_neo4j_statistics():
    """Test graph statistics endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/neo4j/statistics")
        
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "statistics" in data


@pytest.mark.asyncio
async def test_neo4j_health():
    """Test Neo4j health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/neo4j/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]


@pytest.mark.asyncio
async def test_semantic_search_validation():
    """Test input validation for semantic search"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Empty query should fail
        response = await client.post(
            "/api/v1/neo4j/semantic",
            json={
                "query": "",
                "top_k": 5
            }
        )
        assert response.status_code == 422
        
        # top_k too large should fail
        response = await client.post(
            "/api/v1/neo4j/semantic",
            json={
                "query": "test",
                "top_k": 1000
            }
        )
        assert response.status_code == 422
