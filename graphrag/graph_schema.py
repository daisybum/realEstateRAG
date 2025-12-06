"""
Wolbu Ontology Graph Schema

월급쟁이부자들 투자 기준 기반 부동산 지식 그래프 스키마
FalkorDB/Neo4j Cypher 호환

Node Types:
- Region: 지역 (시/구/동)
- ApartmentComplex: 아파트 단지
- GradeMetric: 입지 등급 (직장/교통/학군/환경)
- SupplyEvent: 공급 물량

Relationship Types:
- LOCATED_IN: 단지 → 지역
- HAS_GRADE: 지역 → 등급
- HAS_SUPPLY: 지역 → 공급물량
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class GradeCategory(Enum):
    """입지 등급 카테고리"""
    JOBS = "Jobs"          # 직장
    TRANSPORT = "Transport"  # 교통
    SCHOOL = "School"       # 학군
    ENVIRONMENT = "Environment"  # 환경


class GradeLevel(Enum):
    """등급 레벨 (S > A > B > C)"""
    S = "S"
    A = "A"
    B = "B"
    C = "C"


@dataclass
class Region:
    """지역 노드"""
    name: str  # 예: "부산진구", "용인시 수지구"
    city: Optional[str] = None  # 시/도
    district: Optional[str] = None  # 구/군
    population: Optional[int] = None  # 적정수요 기준 인구
    appropriate_demand: Optional[int] = None  # 연간 적정 수요
    supply_risk_status: Optional[str] = None  # Over-supply, Under-supply, Balanced
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        """Cypher 속성으로 변환"""
        props = {"name": self.name}
        if self.city:
            props["city"] = self.city
        if self.district:
            props["district"] = self.district
        if self.population:
            props["population"] = self.population
        if self.appropriate_demand:
            props["appropriate_demand"] = self.appropriate_demand
        if self.supply_risk_status:
            props["supply_risk_status"] = self.supply_risk_status
        return props


@dataclass
class ApartmentComplex:
    """아파트 단지 노드"""
    name: str
    sales_price: Optional[int] = None  # 매매가 (만원)
    jeonse_price: Optional[int] = None  # 전세가 (만원)
    gap_price: Optional[int] = None  # 갭 (만원)
    jeonse_rate: Optional[float] = None  # 전세가율 (%)
    is_undervalued: Optional[bool] = None  # 저평가 여부
    investment_comment: Optional[str] = None  # 투자 코멘트
    households: Optional[int] = None  # 세대수
    built_year: Optional[int] = None  # 준공년도
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        """Cypher 속성으로 변환"""
        props = {"name": self.name}
        if self.sales_price:
            props["sales_price"] = self.sales_price
        if self.jeonse_price:
            props["jeonse_price"] = self.jeonse_price
        if self.gap_price:
            props["gap_price"] = self.gap_price
        if self.jeonse_rate:
            props["jeonse_rate"] = self.jeonse_rate
        if self.is_undervalued is not None:
            props["is_undervalued"] = self.is_undervalued
        if self.investment_comment:
            props["investment_comment"] = self.investment_comment
        if self.households:
            props["households"] = self.households
        if self.built_year:
            props["built_year"] = self.built_year
        return props


@dataclass
class GradeMetric:
    """입지 등급 노드"""
    category: GradeCategory  # Jobs, Transport, School, Environment
    grade: GradeLevel  # S, A, B, C
    raw_value: Optional[Any] = None  # 실제 수치 (예: 종사자수 176113)
    evidence_text: Optional[str] = None  # 근거 텍스트
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        """Cypher 속성으로 변환"""
        props = {
            "category": self.category.value,
            "grade": self.grade.value,
        }
        if self.raw_value:
            props["raw_value"] = str(self.raw_value)
        if self.evidence_text:
            props["evidence_text"] = self.evidence_text
        return props


@dataclass
class SupplyEvent:
    """공급 물량 노드"""
    year: int
    volume: int  # 입주 물량
    complex_name: Optional[str] = None  # 알려진 경우 단지명
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        """Cypher 속성으로 변환"""
        props = {
            "year": self.year,
            "volume": self.volume,
        }
        if self.complex_name:
            props["complex_name"] = self.complex_name
        return props


class WolbuOntology:
    """월급쟁이부자들 투자 기준 온톨로지 정의"""
    
    # 노드 라벨
    NODE_REGION = "Region"
    NODE_COMPLEX = "ApartmentComplex"
    NODE_GRADE = "GradeMetric"
    NODE_SUPPLY = "SupplyEvent"
    
    # 관계 타입
    REL_LOCATED_IN = "LOCATED_IN"  # Complex → Region
    REL_HAS_GRADE = "HAS_GRADE"    # Region → GradeMetric
    REL_HAS_SUPPLY = "HAS_SUPPLY"  # Region → SupplyEvent
    
    # 인덱스 정의 (성능 최적화)
    INDEXES = [
        ("Region", "name"),
        ("ApartmentComplex", "name"),
        ("ApartmentComplex", "jeonse_rate"),
        ("ApartmentComplex", "is_undervalued"),
        ("GradeMetric", "category"),
        ("GradeMetric", "grade"),
        ("SupplyEvent", "year"),
    ]
    
    # 전세가율 기준 (월급쟁이부자들 기준)
    JEONSE_RATE_THRESHOLD = 60.0  # 60% 이상이면 투자 매력
    
    # 공급 리스크 기준
    SUPPLY_RISK_MULTIPLIER = 2.0  # 적정수요의 2배 초과시 과잉공급


class GraphSchemaManager:
    """그래프 스키마 관리자"""
    
    def __init__(self, graph):
        """
        Args:
            graph: FalkorDB Graph 객체
        """
        self.graph = graph
        self.ontology = WolbuOntology()
    
    def create_indexes(self):
        """인덱스 생성"""
        for label, prop in self.ontology.INDEXES:
            try:
                query = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
                self.graph.query(query)
                logger.info(f"Created index: {label}.{prop}")
            except Exception as e:
                # 이미 존재하는 인덱스는 무시
                if "already exists" not in str(e).lower():
                    logger.warning(f"Failed to create index {label}.{prop}: {e}")
    
    def create_constraints(self):
        """유니크 제약조건 생성 (선택적)"""
        constraints = [
            (WolbuOntology.NODE_REGION, "name"),
        ]
        for label, prop in constraints:
            try:
                query = f"CREATE CONSTRAINT FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                self.graph.query(query)
                logger.info(f"Created constraint: {label}.{prop} UNIQUE")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Failed to create constraint: {e}")
    
    def initialize_schema(self):
        """스키마 초기화 (인덱스 + 제약조건)"""
        logger.info("Initializing graph schema...")
        self.create_indexes()
        self.create_constraints()
        logger.info("Schema initialization complete.")
    
    def drop_all(self):
        """모든 노드/엣지 삭제 (주의: 데이터 손실)"""
        self.graph.query("MATCH (n) DETACH DELETE n")
        logger.warning("All nodes and relationships deleted!")
    
    def get_statistics(self) -> Dict[str, int]:
        """그래프 통계 조회"""
        stats = {}
        for label in [WolbuOntology.NODE_REGION, WolbuOntology.NODE_COMPLEX,
                      WolbuOntology.NODE_GRADE, WolbuOntology.NODE_SUPPLY]:
            result = self.graph.query(f"MATCH (n:{label}) RETURN count(n) as cnt")
            stats[label] = result.result_set[0][0] if result.result_set else 0
        return stats


# Cypher 쿼리 템플릿
CYPHER_TEMPLATES = {
    # 지역 생성/업데이트
    "merge_region": """
        MERGE (r:Region {name: $name})
        SET r += $properties
        RETURN r
    """,
    
    # 단지 생성/업데이트
    "merge_complex": """
        MERGE (c:ApartmentComplex {name: $name})
        SET c += $properties
        RETURN c
    """,
    
    # 단지-지역 관계 생성
    "link_complex_to_region": """
        MATCH (c:ApartmentComplex {name: $complex_name})
        MATCH (r:Region {name: $region_name})
        MERGE (c)-[:LOCATED_IN]->(r)
    """,
    
    # 등급 노드 생성 및 지역 연결
    "create_grade": """
        MATCH (r:Region {name: $region_name})
        CREATE (g:GradeMetric $properties)
        CREATE (r)-[:HAS_GRADE]->(g)
        RETURN g
    """,
    
    # 공급물량 노드 생성 및 지역 연결
    "create_supply": """
        MATCH (r:Region {name: $region_name})
        CREATE (s:SupplyEvent $properties)
        CREATE (r)-[:HAS_SUPPLY]->(s)
        RETURN s
    """,
    
    # 저평가 단지 조회
    "find_undervalued": """
        MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
        WHERE c.is_undervalued = true
          AND c.jeonse_rate >= $min_jeonse_rate
        RETURN c.name, c.jeonse_rate, c.gap_price, r.name as region
        ORDER BY c.jeonse_rate DESC
    """,
    
    # 특정 등급 필터 (예: 교통 S등급 지역의 저평가 단지)
    "find_by_grade": """
        MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region)
        MATCH (r)-[:HAS_GRADE]->(g:GradeMetric)
        WHERE g.category = $category AND g.grade = $grade
          AND c.is_undervalued = true
        RETURN c.name, c.jeonse_rate, r.name as region, g.grade
    """,
    
    # 공급 리스크 조회
    "find_supply_risk": """
        MATCH (r:Region)-[:HAS_SUPPLY]->(s:SupplyEvent)
        WHERE s.year >= $start_year AND s.year <= $end_year
        WITH r, sum(s.volume) as total_supply
        WHERE total_supply > r.appropriate_demand * $risk_multiplier
        RETURN r.name, total_supply, r.appropriate_demand
    """,
}


if __name__ == "__main__":
    # 스키마 정의 테스트
    print("=== Wolbu Ontology Schema ===")
    print(f"Node Types: {[WolbuOntology.NODE_REGION, WolbuOntology.NODE_COMPLEX, WolbuOntology.NODE_GRADE, WolbuOntology.NODE_SUPPLY]}")
    print(f"Relationship Types: {[WolbuOntology.REL_LOCATED_IN, WolbuOntology.REL_HAS_GRADE, WolbuOntology.REL_HAS_SUPPLY]}")
    print(f"Indexes: {WolbuOntology.INDEXES}")
    
    # 데이터클래스 테스트
    region = Region(name="부산진구", population=44035, appropriate_demand=220)
    print(f"\nRegion props: {region.to_cypher_properties()}")
    
    complex = ApartmentComplex(
        name="가야롯데캐슬골드아너",
        jeonse_rate=64.52,
        is_undervalued=True
    )
    print(f"Complex props: {complex.to_cypher_properties()}")
