"""
Pytest Configuration and Fixtures
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator

# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_report_data() -> dict:
    """Sample report data for testing"""
    return {
        "id": "test-report-001",
        "title": "수지구 임장 보고서",
        "district": "수지구",
        "city": "용인시",
        "province": "경기도",
    }


@pytest.fixture
def sample_fact_extraction() -> dict:
    """Sample LLM fact extraction output"""
    return {
        "district": {
            "name": "수지구",
            "city": "용인시",
        },
        "grades": {
            "jobs": {"grade": "A", "evidence": "판교 테크노밸리 30분"},
            "transport": {"grade": "A", "evidence": "신분당선 접근"},
            "school": {"grade": "B", "evidence": "학군 양호"},
            "environment": {"grade": "A", "evidence": "쾌적한 환경"},
        },
        "complexes": [
            {
                "name": "래미안수지",
                "sales_price": 150000,
                "jeonse_price": 95000,
                "jeonse_rate": 63.3,
            },
            {
                "name": "자연앤힐스테이트",
                "sales_price": 120000,
                "jeonse_price": 80000,
                "jeonse_rate": 66.7,
            },
        ],
    }


@pytest.fixture
def sample_entities() -> list:
    """Sample entities for testing"""
    return [
        {"id": "DISTRICT_SUJI", "type": "District", "name": "수지구"},
        {"id": "INFRA_PANGYO_STATION", "type": "Infra", "name": "판교역"},
        {"id": "COMPLEX_RAEMIAN", "type": "Complex", "name": "래미안수지"},
    ]


@pytest.fixture
def sample_relationships() -> list:
    """Sample relationships for testing"""
    return [
        {
            "source": "COMPLEX_RAEMIAN",
            "target": "DISTRICT_SUJI",
            "type": "LOCATED_IN",
        },
        {
            "source": "DISTRICT_SUJI",
            "target": "INFRA_PANGYO_STATION",
            "type": "ACCESS_TO",
            "properties": {"time_min": 30},
        },
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing"""
    class MockChoice:
        class MockMessage:
            content = '{"verified": true, "corrections": []}'
        message = MockMessage()
    
    class MockUsage:
        total_tokens = 100
    
    class MockResponse:
        choices = [MockChoice()]
        usage = MockUsage()
    
    return MockResponse()
