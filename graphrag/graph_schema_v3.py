"""
Wolbu Ontology Graph Schema v3.0

월급쟁이부자들 투자 기준 기반 부동산 지식 그래프 스키마
Entity-centric 설계로 전면 재구성

Major Changes from v2.0:
- Neighborhood 노드 추가 (공간 계층 강화)
- Infra 노드 추가 (구체적 시설명 저장)
- MarketSnapshot 노드 추가 (시계열 분리)
- ACCESS_TO, CONTAINS_FACILITY, HAS_SNAPSHOT 관계 추가
- Region/Complex에서 시계열 속성 제거
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


# === Enums ===

class GradeLevel(Enum):
    """등급 레벨"""
    S = "S"
    A = "A"
    B = "B"
    C = "C"


class InvestmentVerdict(Enum):
    """투자 판단"""
    UNDERVALUED = "Undervalued"
    OVERVALUED = "Overvalued"
    FAIR = "Fair"
    RISKY = "Risky"


class InfraCategory(Enum):
    """인프라 카테고리 (NEW in v3.0)"""
    SUBWAY = "Subway"
    JOB_CENTER = "JobCenter"
    DEPT_STORE = "DeptStore"
    SCHOOL = "School"
    HOSPITAL = "Hospital"
    PARK = "Park"
    GOVERNMENT = "Government"
    TRANSPORT_HUB = "TransportHub"


# === v3.0 New Node Types ===

@dataclass
class Neighborhood:
    """읍/면/동 단위 노드 (NEW in v3.0)
    
    공간 계층 강화: Region → District → Neighborhood → Complex
    """
    name: str
    district: str  # Parent district name
    region: Optional[str] = None  # Parent region name
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"name": self.name, "district": self.district}
        if self.region:
            props["region"] = self.region
        return props


@dataclass
class Infra:
    """구체적 인프라 시설 노드 (NEW in v3.0)
    
    구체적 시설명을 저장하여 그래프 탐색 가능
    
    Examples:
    - Infra(name="강남역", category=InfraCategory.SUBWAY, tier=GradeLevel.S)
    - Infra(name="Starfield Hanam", category=InfraCategory.DEPT_STORE, tier=GradeLevel.A)
    """
    name: str
    category: InfraCategory
    tier: GradeLevel
    address: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None  # {"lat": 37.xxx, "lon": 127.xxx}
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {
            "name": self.name,
            "category": self.category.value,
            "tier": self.tier.value,
        }
        if self.address:
            props["address"] = self.address
        if self.coordinates:
            props["latitude"] = self.coordinates.get("lat")
            props["longitude"] = self.coordinates.get("lon")
        return props


@dataclass
class MarketSnapshot:
    """시계열 시장 데이터 노드 (NEW in v3.0)
    
    시간에 따라 변하는 데이터를 별도 노드로 분리
    Complex 또는 District에 연결되어 시계열 분석 가능
    """
    date: str  # YYYY-MM format
    sales_price: Optional[int] = None
    jeonse_price: Optional[int] = None
    jeonse_rate: Optional[float] = None
    gap_price: Optional[int] = None
    population: Optional[int] = None
    supply_volume: Optional[int] = None
    appropriate_demand: Optional[int] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"date": self.date}
        if self.sales_price is not None:
            props["sales_price"] = self.sales_price
        if self.jeonse_price is not None:
            props["jeonse_price"] = self.jeonse_price
        if self.jeonse_rate is not None:
            props["jeonse_rate"] = self.jeonse_rate
        if self.gap_price is not None:
            props["gap_price"] = self.gap_price
        if self.population is not None:
            props["population"] = self.population
        if self.supply_volume is not None:
            props["supply_volume"] = self.supply_volume
        if self.appropriate_demand is not None:
            props["appropriate_demand"] = self.appropriate_demand
        return props


# === Modified Node Types ===

@dataclass
class Region:
    """지역 노드 (MODIFIED in v3.0)
    
    Removed: population, supply_volume, appropriate_demand
    → 이들은 이제 MarketSnapshot 노드로 이동
    """
    name: str
    city: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"name": self.name}
        if self.city:
            props["city"] = self.city
        return props


@dataclass
class ApartmentComplex:
    """아파트 단지 노드 (MODIFIED in v3.0)
    
    Removed: sales_price, jeonse_price, jeonse_rate, gap_price
    → 이들은 이제 MarketSnapshot 노드로 이동
    
    Kept: 변하지 않는 정적 정보만 유지
    """
    name: str
    households: Optional[int] = None
    built_year: Optional[int] = None
    address: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"name": self.name}
        if self.households:
            props["households"] = self.households
        if self.built_year:
            props["built_year"] = self.built_year
        if self.address:
            props["address"] = self.address
        return props


# === Unchanged Node Types (from v2.0) ===

@dataclass
class Report:
    """보고서 메타데이터 노드 (UNCHANGED)"""
    report_id: str
    title: Optional[str] = None
    analysis_date: Optional[str] = None
    confidence_score: Optional[float] = None
    data_sources: List[str] = field(default_factory=list)
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"report_id": self.report_id}
        if self.title:
            props["title"] = self.title
        if self.analysis_date:
            props["analysis_date"] = self.analysis_date
        if self.confidence_score is not None:
            props["confidence_score"] = self.confidence_score
        if self.data_sources:
            props["data_sources"] = self.data_sources
        return props


@dataclass
class InvestmentAnalysis:
    """투자 판단 노드 (UNCHANGED)"""
    verdict: InvestmentVerdict
    reasoning: str
    confidence: float
    investment_comment: Optional[str] = None
    analysis_date: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {
            "verdict": self.verdict.value,
            "reasoning": self.reasoning[:1000],
            "confidence": self.confidence,
        }
        if self.investment_comment:
            props["investment_comment"] = self.investment_comment[:500]
        if self.analysis_date:
            props["analysis_date"] = self.analysis_date
        return props


# === Ontology Definition ===

class WolbuOntologyV3:
    """월급쟁이부자들 온톨로지 v3.0"""
    
    # 노드 라벨
    NODE_REPORT = "Report"
    NODE_REGION = "Region"
    NODE_NEIGHBORHOOD = "Neighborhood"  # NEW
    NODE_COMPLEX = "ApartmentComplex"
    NODE_INFRA = "Infra"  # NEW
    NODE_MARKET_SNAPSHOT = "MarketSnapshot"  # NEW
    NODE_ANALYSIS = "InvestmentAnalysis"
    
    # 관계 타입
    # 공간 계층
    REL_LOCATED_IN = "LOCATED_IN"  # Neighborhood→District, Complex→Neighborhood
    
    # 시계열 연결
    REL_HAS_SNAPSHOT = "HAS_SNAPSHOT"  # Complex/District→MarketSnapshot (NEW)
    
    # 인프라 연결 (NEW)
    REL_ACCESS_TO = "ACCESS_TO"  # District→Infra (with time_min, transport_mode)
    REL_CONTAINS_FACILITY = "CONTAINS_FACILITY"  # District→Infra
    
    # 보고서 연결
    REL_ANALYZES = "ANALYZES"  # Report→Region/District
    REL_MENTIONS = "MENTIONS"  # Report→Complex/Infra
    
    # 투자 판단
    REL_HAS_ANALYSIS = "HAS_ANALYSIS"  # Complex→InvestmentAnalysis
    REL_SUPPORTS = "SUPPORTS"  # Infra→InvestmentAnalysis (reasoning chain)
    
    # 인덱스 정의
    INDEXES = [
        ("Report", "report_id"),
        ("Region", "name"),
        ("Neighborhood", "name"),
        ("ApartmentComplex", "name"),
        ("Infra", "name"),
        ("Infra", "category"),
        ("MarketSnapshot", "date"),
        ("InvestmentAnalysis", "verdict"),
    ]
    
    # 투자 기준
    JEONSE_RATE_THRESHOLD = 60.0
    SUPPLY_RISK_MULTIPLIER = 2.0


class GraphSchemaManagerV3:
    """그래프 스키마 관리자 v3.0"""
    
    def __init__(self, graph):
        self.graph = graph
        self.ontology = WolbuOntologyV3()
    
    def create_indexes(self):
        """인덱스 생성"""
        for label, prop in self.ontology.INDEXES:
            try:
                query = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
                self.graph.query(query)
                logger.info(f"Created index: {label}.{prop}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Failed to create index {label}.{prop}: {e}")
    
    def create_constraints(self):
        """유니크 제약 조건"""
        constraints = [
            (WolbuOntologyV3.NODE_REPORT, "report_id"),
            (WolbuOntologyV3.NODE_REGION, "name"),
        ]
        for label, prop in constraints:
            try:
                query = f"CREATE CONSTRAINT ON (n:{label}) ASSERT n.{prop} IS UNIQUE"
                self.graph.query(query)
                logger.info(f"Created constraint: {label}.{prop} UNIQUE")
            except Exception as e:
                logger.warning(f"Failed to create constraint {label}.{prop}: {e}")
    
    def initialize_schema(self):
        """스키마 초기화"""
        logger.info("Initializing graph schema v3.0...")
        self.create_indexes()
        self.create_constraints()
        logger.info("Schema v3.0 initialization complete.")
    
    def drop_all(self):
        """모든 노드/엣지 삭제"""
        self.graph.query("MATCH (n) DETACH DELETE n")
        logger.warning("All nodes and relationships deleted!")
    
    def get_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        stats = {}
        for label in [
            WolbuOntologyV3.NODE_REPORT,
            WolbuOntologyV3.NODE_REGION,
            WolbuOntologyV3.NODE_NEIGHBORHOOD,
            WolbuOntologyV3.NODE_COMPLEX,
            WolbuOntologyV3.NODE_INFRA,
            WolbuOntologyV3.NODE_MARKET_SNAPSHOT,
            WolbuOntologyV3.NODE_ANALYSIS,
        ]:
            result = self.graph.query(f"MATCH (n:{label}) RETURN count(n) as cnt")
            stats[label] = result.result_set[0][0] if result.result_set else 0
        return stats


# Cypher 쿼리 템플릿 v3.0
CYPHER_TEMPLATES_V3 = {
    # Neighborhood 생성
    "merge_neighborhood": """
        MERGE (n:Neighborhood {{name: '{name}', district: '{district}'}})
        SET n += {props_str}
        RETURN n
    """,
    
    # Infra 생성
    "merge_infra": """
        MERGE (i:Infra {{name: '{name}'}})
        SET i += {props_str}
        RETURN i
    """,
    
    # MarketSnapshot 생성
    "create_market_snapshot": """
        CREATE (m:MarketSnapshot {props_str})
        RETURN m
    """,
    
    # ACCESS_TO 관계
    "link_district_to_infra": """
        MATCH (d:District {{name: '{district_name}'}})
        MATCH (i:Infra {{name: '{infra_name}'}})
        MERGE (d)-[r:ACCESS_TO]->(i)
        SET r += {props_str}
        RETURN r
    """,
    
    # HAS_SNAPSHOT 관계
    "link_to_snapshot": """
        MATCH (e {{name: '{entity_name}'}})
        MATCH (m:MarketSnapshot {{date: '{date}'}})
        WHERE id(m) = {snapshot_id}
        MERGE (e)-[r:HAS_SNAPSHOT]->(m)
        RETURN r
    """,
    
    # 특정 시설 접근성 기반 단지 검색
    "find_by_facility_access": """
        MATCH (d:District)-[r:ACCESS_TO]->(i:Infra {{name: '{facility_name}'}})
        WHERE r.time_min <= {max_time_min}
        MATCH (c:ApartmentComplex)-[:LOCATED_IN*]->(d)
        MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
        WHERE m.date = (
            SELECT MAX(m2.date)
            FROM (c)-[:HAS_SNAPSHOT]->(m2:MarketSnapshot)
        )
        AND m.jeonse_rate >= {min_jeonse_rate}
        RETURN c.name, d.name, m.jeonse_rate, r.time_min
        ORDER BY m.jeonse_rate DESC
        LIMIT 20
    """,
    
    # 시계열 가격 추이
    "get_price_trend": """
        MATCH (c:ApartmentComplex {{name: '{complex_name}'}})-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
        RETURN m.date, m.sales_price, m.jeonse_price, m.jeonse_rate
        ORDER BY m.date ASC
    """,
    
    # 지역 내 인프라 시설 검색
    "find_facilities_in_district": """
        MATCH (d:District {{name: '{district_name}'}})-[:CONTAINS_FACILITY]->(i:Infra)
        WHERE i.category = '{category}'
        RETURN i.name, i.tier, i.address
        ORDER BY i.tier ASC
    """,
}


if __name__ == "__main__":
    print("=== Wolbu Ontology Schema v3.0 ===")
    print(f"New Nodes: Neighborhood, Infra, MarketSnapshot")
    print(f"New Relationships: ACCESS_TO, CONTAINS_FACILITY, HAS_SNAPSHOT")
    print(f"Total Node Types: 7")
    print(f"Total Relationship Types: 6")
    
    # 데이터클래스 테스트
    infra = Infra(
        name="강남역",
        category=InfraCategory.SUBWAY,
        tier=GradeLevel.S,
        coordinates={"lat": 37.497952, "lon": 127.027619}
    )
    print(f"\nInfra example: {infra.to_cypher_properties()}")
    
    snapshot = MarketSnapshot(
        date="2024-12",
        sales_price=150000,
        jeonse_price=95000,
        jeonse_rate=63.3
    )
    print(f"MarketSnapshot example: {snapshot.to_cypher_properties()}")
