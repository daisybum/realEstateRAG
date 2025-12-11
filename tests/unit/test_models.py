"""
Unit Tests for Core Models
"""

import pytest
from datetime import datetime

from realestaterag.core.models import (
    Location,
    GradeMetric,
    District,
    Infra,
    MarketSnapshot,
    PropertyComplex,
    Report,
    AnalysisResult,
    QueryRequest,
    QueryResult,
)
from realestaterag.core.enums import GradeLevel, InfraCategory


class TestLocation:
    """Location 모델 테스트"""
    
    def test_create_location(self):
        loc = Location(district="수지구", city="용인시", province="경기도")
        assert loc.district == "수지구"
        assert loc.city == "용인시"
    
    def test_full_address(self):
        loc = Location(
            district="수지구",
            city="용인시",
            province="경기도",
            neighborhood="풍덕천동"
        )
        assert loc.full_address == "경기도 용인시 수지구 풍덕천동"
    
    def test_optional_fields(self):
        loc = Location(district="강남구")
        assert loc.city == ""
        assert loc.coordinates is None


class TestGradeMetric:
    """GradeMetric 모델 테스트"""
    
    def test_create_grade(self):
        grade = GradeMetric(category="Transport", grade=GradeLevel.S)
        assert grade.grade == GradeLevel.S
    
    def test_grade_with_evidence(self):
        grade = GradeMetric(
            category="Jobs",
            grade=GradeLevel.A,
            evidence="판교 테크노밸리 30분 거리"
        )
        assert grade.evidence is not None


class TestInfra:
    """Infra 모델 테스트"""
    
    def test_create_infra(self):
        infra = Infra(
            id="INFRA_GANGNAM",
            name="강남역",
            category=InfraCategory.SUBWAY,
            tier=GradeLevel.S
        )
        assert infra.name == "강남역"
        assert infra.category == InfraCategory.SUBWAY
    
    def test_id_prefix_validation(self):
        """ID에 INFRA_ prefix가 없으면 자동 추가"""
        infra = Infra(
            id="GANGNAM",
            name="강남역",
            category=InfraCategory.SUBWAY
        )
        assert infra.id == "INFRA_GANGNAM"
    
    def test_id_prefix_preserved(self):
        """이미 INFRA_ prefix가 있으면 유지"""
        infra = Infra(
            id="INFRA_PANGYO",
            name="판교역",
            category=InfraCategory.SUBWAY
        )
        assert infra.id == "INFRA_PANGYO"


class TestMarketSnapshot:
    """MarketSnapshot 모델 테스트"""
    
    def test_create_snapshot(self):
        snapshot = MarketSnapshot(
            id="MARKET_001",
            date="2024-12",
            sales_price=150000,
            jeonse_price=95000,
            jeonse_rate=63.3
        )
        assert snapshot.sales_price == 150000
    
    def test_date_validation_valid(self):
        """올바른 날짜 형식"""
        snapshot = MarketSnapshot(id="M1", date="2024-12")
        assert snapshot.date == "2024-12"
    
    def test_date_validation_invalid(self):
        """잘못된 날짜 형식"""
        with pytest.raises(ValueError):
            MarketSnapshot(id="M1", date="2024/12/01")


class TestPropertyComplex:
    """PropertyComplex 모델 테스트"""
    
    def test_create_complex(self):
        complex_ = PropertyComplex(
            id="COMPLEX_001",
            name="래미안수지",
            total_units=1000,
            year_built=2010
        )
        assert complex_.name == "래미안수지"
    
    def test_latest_snapshot(self):
        """최신 스냅샷 조회"""
        complex_ = PropertyComplex(
            id="C1",
            name="테스트",
            snapshots=[
                MarketSnapshot(id="M1", date="2024-10", sales_price=100000),
                MarketSnapshot(id="M2", date="2024-12", sales_price=120000),
                MarketSnapshot(id="M3", date="2024-11", sales_price=110000),
            ]
        )
        assert complex_.latest_snapshot.date == "2024-12"
        assert complex_.latest_snapshot.sales_price == 120000


class TestReport:
    """Report 모델 테스트"""
    
    def test_create_report(self):
        report = Report(id="R001", title="수지구 임장")
        assert report.id == "R001"
        assert isinstance(report.date, datetime)
    
    def test_report_with_images(self):
        report = Report(
            id="R002",
            title="테스트",
            image_paths=["/path/img1.png", "/path/img2.jpg"]
        )
        assert len(report.image_paths) == 2


class TestQueryModels:
    """Query 모델 테스트"""
    
    def test_query_request(self):
        req = QueryRequest(question="강남역 30분 이내 단지")
        assert req.use_cache is True
    
    def test_query_request_min_length(self):
        with pytest.raises(ValueError):
            QueryRequest(question="")
    
    def test_query_result(self):
        result = QueryResult(
            query="테스트",
            cypher="MATCH (n) RETURN n",
            results=[{"name": "test"}],
            answer="답변",
            confidence=0.85,
            sources=["source1"],
        )
        assert result.confidence == 0.85


class TestAnalysisResult:
    """AnalysisResult 모델 테스트"""
    
    def test_create_analysis_result(self):
        result = AnalysisResult(
            report_id="R001",
            facts=["fact1", "fact2"],
            entities=[{"id": "E1", "type": "District"}],
            confidence_score=0.8,
            processing_time=5.5,
        )
        assert len(result.facts) == 2
        assert result.confidence_score == 0.8
