"""
Wolbu Ontology Graph Schema v2.0

월급쟁이부자들 투자 기준 기반 부동산 지식 그래프 스키마
추론 가능한(Inference-ready) 설계로 전면 재구성

Major Changes from v1.0:
- Report 노드 추가 (메타데이터 추적)
- InvestmentAnalysis 노드 추가 (판단 근거 분리)
- Indicator 노드 추가 (정량 지표 통합)
- 명시적 추론 체인 지원
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class GradeCategory(Enum):
    """입지 등급 카테고리"""
    JOBS = "Jobs"
    TRANSPORT = "Transport"
    SCHOOL = "School"
    ENVIRONMENT = "Environment"


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


class IndicatorType(Enum):
    """지표 타입"""
    POPULATION = "population"
    APPROPRIATE_DEMAND = "appropriate_demand"
    SUPPLY_VOLUME_3YR = "supply_volume_3yr"
    INCOME_MEDIAN = "income_median"


# === 새로운 노드 타입 (v2.0) ===

@dataclass
class Report:
    """보고서 메타데이터 노드 (NEW)"""
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
    """투자 판단 노드 (NEW)
    
    Complex의 is_undervalued, investment_comment를 분리하여
    명시적인 추론 노드로 구성
    """
    verdict: InvestmentVerdict
    reasoning: str  # LLM이 생성한 추론 체인
    confidence: float
    investment_comment: Optional[str] = None
    analysis_date: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {
            "verdict": self.verdict.value,
            "reasoning": self.reasoning[:1000],  # 길이 제한
            "confidence": self.confidence,
        }
        if self.investment_comment:
            props["investment_comment"] = self.investment_comment[:500]
        if self.analysis_date:
            props["analysis_date"] = self.analysis_date
        return props


@dataclass
class Indicator:
    """정량 지표 노드 (NEW)
    
    Region의 population, appropriate_demand 등을 분리하여
    통합 관리. 추론 체인에서 근거로 활용
    """
    type: str  # IndicatorType enum value
    value: Any
    unit: Optional[str] = None
    source: Optional[str] = None
    measured_date: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {
            "type": self.type,
            "value": str(self.value),  # 다양한 타입 처리
        }
        if self.unit:
            props["unit"] = self.unit
        if self.source:
            props["source"] = self.source
        if self.measured_date:
            props["measured_date"] = self.measured_date
        return props


# === 수정된 기존 노드 (v2.0) ===

@dataclass
class Region:
    """지역 노드 (MODIFIED)
    
    제거된 속성: population, appropriate_demand, supply_risk_status
    → Indicator 노드로 이동
    """
    name: str
    city: Optional[str] = None
    district: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"name": self.name}
        if self.city:
            props["city"] = self.city
        if self.district:
            props["district"] = self.district
        return props


@dataclass
class ApartmentComplex:
    """아파트 단지 노드 (MODIFIED)
    
    제거된 속성: is_undervalued, investment_comment
    → InvestmentAnalysis 노드로 이동
    """
    name: str
    sales_price: Optional[int] = None
    jeonse_price: Optional[int] = None
    gap_price: Optional[int] = None
    jeonse_rate: Optional[float] = None
    households: Optional[int] = None
    built_year: Optional[int] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"name": self.name}
        if self.sales_price:
            props["sales_price"] = self.sales_price
        if self.jeonse_price:
            props["jeonse_price"] = self.jeonse_price
        if self.gap_price:
            props["gap_price"] = self.gap_price
        if self.jeonse_rate is not None:
            props["jeonse_rate"] = self.jeonse_rate
        if self.households:
            props["households"] = self.households
        if self.built_year:
            props["built_year"] = self.built_year
        return props


@dataclass
class GradeMetric:
    """입지 등급 노드 (UNCHANGED)"""
    category: GradeCategory
    grade: GradeLevel
    raw_value: Optional[Any] = None
    evidence_text: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {
            "category": self.category.value,
            "grade": self.grade.value,
        }
        if self.raw_value is not None:
            props["raw_value"] = str(self.raw_value)
        if self.evidence_text:
            props["evidence_text"] = self.evidence_text[:500]
        return props


@dataclass
class SupplyEvent:
    """공급 물량 노드 (UNCHANGED)
    
    Note: v2.0에서는 Indicator로 통합 가능하지만
    기존 호환성 유지를 위해 보존
    """
    year: int
    volume: int
    complex_name: Optional[str] = None
    
    def to_cypher_properties(self) -> Dict[str, Any]:
        props = {"year": self.year, "volume": self.volume}
        if self.complex_name:
            props["complex_name"] = self.complex_name
        return props


class WolbuOntologyV2:
    """월급쟁이부자들 온톨로지 v2.0"""
    
    # 노드 라벨
    NODE_REPORT = "Report"  # NEW
    NODE_REGION = "Region"
    NODE_COMPLEX = "ApartmentComplex"
    NODE_GRADE = "GradeMetric"
    NODE_ANALYSIS = "InvestmentAnalysis"  # NEW
    NODE_INDICATOR = "Indicator"  # NEW
    NODE_SUPPLY = "SupplyEvent"
    
    # 관계 타입
    # 보고서 연결
    REL_ANALYZES = "ANALYZES"  # Report → Region (NEW)
    REL_MENTIONS = "MENTIONS"  # Report → Complex (NEW)
    
    # 기존 관계
    REL_LOCATED_IN = "LOCATED_IN"  # Complex → Region
    REL_HAS_GRADE = "HAS_GRADE"    # Region → GradeMetric
    REL_HAS_SUPPLY = "HAS_SUPPLY"  # Region → SupplyEvent
    
    # 투자 판단 (NEW)
    REL_HAS_ANALYSIS = "HAS_ANALYSIS"  # Complex → InvestmentAnalysis
    
    # 지표 연결 (NEW)
    REL_HAS_INDICATOR = "HAS_INDICATOR"  # Region → Indicator
    
    # 추론 체인 (NEW)
    REL_SUPPORTS = "SUPPORTS"  # Grade → InvestmentAnalysis
    REL_BASED_ON = "BASED_ON"  # InvestmentAnalysis → Indicator
    
    # 인덱스 정의
    INDEXES = [
        ("Report", "report_id"),
        ("Region", "name"),
        ("ApartmentComplex", "name"),
        ("ApartmentComplex", "jeonse_rate"),
        ("GradeMetric", "category"),
        ("GradeMetric", "grade"),
        ("InvestmentAnalysis", "verdict"),
        ("Indicator", "type"),
        ("SupplyEvent", "year"),
    ]
    
    # 투자 기준
    JEONSE_RATE_THRESHOLD = 60.0
    SUPPLY_RISK_MULTIPLIER = 2.0


class GraphSchemaManager:
    """그래프 스키마 관리자 v2.0"""
    
    def __init__(self, graph):
        self.graph = graph
        self.ontology = WolbuOntologyV2()
    
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
            (WolbuOntologyV2.NODE_REPORT, "report_id"),
            (WolbuOntologyV2.NODE_REGION, "name"),
        ]
        for label, prop in constraints:
            try:
                # Try standard Cypher syntax
                query = f"CREATE CONSTRAINT ON (n:{label}) ASSERT n.{prop} IS UNIQUE"
                self.graph.query(query)
                logger.info(f"Created constraint: {label}.{prop} UNIQUE")
            except Exception as e:
                # FalkorDB might not support constraints fully yet, or syntax differs
                # Just log and continue, as indexes should be enough for performance
                logger.warning(f"Failed to create constraint {label}.{prop}: {e}")
    
    def initialize_schema(self):
        """스키마 초기화"""
        logger.info("Initializing graph schema v2.0...")
        self.create_indexes()
        self.create_constraints()
        logger.info("Schema v2.0 initialization complete.")
    
    def drop_all(self):
        """모든 노드/엣지 삭제"""
        self.graph.query("MATCH (n) DETACH DELETE n")
        logger.warning("All nodes and relationships deleted!")
    
    def get_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        stats = {}
        for label in [
            WolbuOntologyV2.NODE_REPORT,
            WolbuOntologyV2.NODE_REGION,
            WolbuOntologyV2.NODE_COMPLEX,
            WolbuOntologyV2.NODE_GRADE,
            WolbuOntologyV2.NODE_ANALYSIS,
            WolbuOntologyV2.NODE_INDICATOR,
            WolbuOntologyV2.NODE_SUPPLY,
        ]:
            result = self.graph.query(f"MATCH (n:{label}) RETURN count(n) as cnt")
            stats[label] = result.result_set[0][0] if result.result_set else 0
        return stats


# Cypher 쿼리 템플릿 v2.0
CYPHER_TEMPLATES_V2 = {
    # Report 생성
    "create_report": """
        CREATE (r:Report $properties)
        RETURN r
    """,
    
    # Region 생성 (간소화)
    "merge_region": """
        MERGE (r:Region {name: $name})
        SET r += $properties
        RETURN r
    """,
    
    # Complex 생성 (간소화)
    "merge_complex": """
        MERGE (c:ApartmentComplex {name: $name})
        SET c += $properties
        RETURN c
    """,
    
    # InvestmentAnalysis 생성 + Complex 연결
    "create_analysis": """
        MATCH (c:ApartmentComplex {name: $complex_name})
        CREATE (a:InvestmentAnalysis $properties)
        CREATE (c)-[:HAS_ANALYSIS]->(a)
        RETURN a
    """,
    
    # Indicator 생성 + Region 연결
    "create_indicator": """
        MATCH (r:Region {name: $region_name})
        CREATE (i:Indicator $properties)
        CREATE (r)-[:HAS_INDICATOR]->(i)
        RETURN i
    """,
    
    # 추론 체인 연결: Grade → Analysis
    "link_grade_to_analysis": """
        MATCH (g:GradeMetric {category: $category, grade: $grade})
        MATCH (a:InvestmentAnalysis)
        WHERE id(a) = $analysis_id
        CREATE (g)-[:SUPPORTS]->(a)
    """,
    
    # 추론 체인 조회
    "get_reasoning_chain": """
        MATCH path = (c:ApartmentComplex {name: $complex_name})
                     -[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
                     <-[:SUPPORTS]-(g:GradeMetric)
        RETURN c.name, a.verdict, a.reasoning, 
               collect({category: g.category, grade: g.grade}) as supporting_grades
    """,
    
    # 저평가 단지 조회 (v2.0)
    "find_undervalued_v2": """
        MATCH (c:ApartmentComplex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis {verdict: 'Undervalued'})
        MATCH (c)-[:LOCATED_IN]->(r:Region)
        WHERE c.jeonse_rate >= $min_jeonse_rate
        RETURN c.name, c.jeonse_rate, c.gap_price, r.name as region, a.reasoning
        ORDER BY c.jeonse_rate DESC
        LIMIT 20
    """,
    
    # 등급별 투자 단지 (v2.0)
    "find_by_grade_v2": """
        MATCH (c:ApartmentComplex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
        MATCH (c)-[:LOCATED_IN]->(r:Region)-[:HAS_GRADE]->(g:GradeMetric)
        WHERE g.category = $category AND g.grade = $grade
          AND a.verdict IN ['Undervalued', 'Fair']
        RETURN c.name, c.jeonse_rate, r.name as region, g.grade, a.reasoning
        LIMIT 20
    """,
    
    # 지표 기반 공급 리스크 분석
    "find_supply_risk_v2": """
        MATCH (r:Region)-[:HAS_INDICATOR]->(i1:Indicator {type: 'supply_volume_3yr'})
        MATCH (r)-[:HAS_INDICATOR]->(i2:Indicator {type: 'appropriate_demand'})
        WHERE toFloat(i1.value) > toFloat(i2.value) * $risk_multiplier
        RETURN r.name, i1.value as supply, i2.value as demand,
               toFloat(i1.value) / toFloat(i2.value) as risk_ratio
        ORDER BY risk_ratio DESC
    """,
}


if __name__ == "__main__":
    print("=== Wolbu Ontology Schema v2.0 ===")
    print(f"Nodes: {[WolbuOntologyV2.NODE_REPORT, WolbuOntologyV2.NODE_REGION, WolbuOntologyV2.NODE_COMPLEX, WolbuOntologyV2.NODE_ANALYSIS, WolbuOntologyV2.NODE_INDICATOR]}")
    print(f"New Relationships: {[WolbuOntologyV2.REL_ANALYZES, WolbuOntologyV2.REL_HAS_ANALYSIS, WolbuOntologyV2.REL_HAS_INDICATOR, WolbuOntologyV2.REL_SUPPORTS]}")
    
    # 데이터클래스 테스트
    report = Report(report_id="3667403", confidence_score=0.85)
    print(f"\nReport props: {report.to_cypher_properties()}")
    
    analysis = InvestmentAnalysis(
        verdict=InvestmentVerdict.UNDERVALUED,
        reasoning="전고점 대비 하락폭 0.93%, 소득 대비 저평가 확인",
        confidence=0.82
    )
    print(f"Analysis props: {analysis.to_cypher_properties()}")
    
    indicator = Indicator(type="population", value=44035, unit="명")
    print(f"Indicator props: {indicator.to_cypher_properties()}")
