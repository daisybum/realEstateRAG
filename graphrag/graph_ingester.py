"""
Graph Ingester

분석 결과 JSON을 FalkorDB 그래프에 적재하는 ETL 모듈
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from .graph_schema import (
    WolbuOntology,
    Region,
    ApartmentComplex,
    GradeMetric,
    SupplyEvent,
    GradeCategory,
    GradeLevel,
    CYPHER_TEMPLATES,
)

logger = logging.getLogger(__name__)


class GraphIngester:
    """분석 결과 JSON → FalkorDB 그래프 적재"""
    
    def __init__(self, graph, auto_init_schema: bool = True):
        """
        Args:
            graph: FalkorDB Graph 객체
            auto_init_schema: 스키마 자동 초기화 여부
        """
        self.graph = graph
        self.ontology = WolbuOntology()
        
        if auto_init_schema:
            self._ensure_schema()
    
    def _ensure_schema(self):
        """스키마(인덱스) 초기화"""
        from .graph_schema import GraphSchemaManager
        manager = GraphSchemaManager(self.graph)
        manager.initialize_schema()
    
    def ingest_analysis_result(self, result: Dict[str, Any]) -> Dict[str, int]:
        """
        분석 결과 JSON을 그래프에 적재
        
        Args:
            result: main_analysis.py의 분석 결과
                   {
                       "report_id": "...",
                       "facts": {...},  # 또는 문자열
                       "verification": {...},
                       "sentiment": {...},
                       "insight": "..."
                   }
        
        Returns:
            적재 통계 {nodes_created, relationships_created}
        """
        stats = {"nodes_created": 0, "relationships_created": 0}
        
        # facts 파싱 (문자열이면 JSON 파싱 시도)
        facts = self._parse_facts(result.get("facts", {}))
        if not facts:
            logger.warning(f"No facts to ingest for report {result.get('report_id')}")
            return stats
        
        # 1. Region 노드 생성
        region = self._create_region(facts)
        if region:
            stats["nodes_created"] += 1
        
        # 2. ApartmentComplex 노드들 생성
        complexes = self._create_complexes(facts, region)
        stats["nodes_created"] += len(complexes)
        stats["relationships_created"] += len(complexes)  # LOCATED_IN
        
        # 3. GradeMetric 노드들 생성
        grades = self._create_grades(facts, region)
        stats["nodes_created"] += len(grades)
        stats["relationships_created"] += len(grades)  # HAS_GRADE
        
        # 4. SupplyEvent 노드들 생성
        supplies = self._create_supplies(facts, region)
        stats["nodes_created"] += len(supplies)
        stats["relationships_created"] += len(supplies)  # HAS_SUPPLY
        
        logger.info(f"Ingested report {result.get('report_id')}: {stats}")
        return stats
    
    def _parse_facts(self, facts: Any) -> Dict[str, Any]:
        """facts 데이터 파싱 (문자열 또는 Dict)"""
        if isinstance(facts, dict):
            return facts
        
        if isinstance(facts, str):
            # 청크 연결 형태인 경우 첫 번째 JSON 블록만 추출
            try:
                # JSON 블록 찾기
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', facts, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
            
            # 전체 문자열 파싱 시도
            try:
                return json.loads(facts)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse facts string: {facts[:200]}...")
                return {}
        
        return {}
    
    def _create_region(self, facts: Dict) -> Optional[str]:
        """Region 노드 생성"""
        # 지역명 추출 (여러 경로 시도)
        region_name = None
        
        # district.name 또는 location.district
        if "district" in facts:
            district = facts["district"]
            if isinstance(district, dict):
                region_name = district.get("name") or district.get("district_name")
            elif isinstance(district, str):
                region_name = district
        
        if not region_name and "location" in facts:
            location = facts["location"]
            if isinstance(location, dict):
                region_name = location.get("district") or location.get("name")
        
        if not region_name and "region" in facts:
            region_name = facts["region"]
        
        if not region_name:
            logger.warning("Could not extract region name from facts")
            return None
        
        # 속성 수집
        props = {"name": region_name}
        
        # 인구/수요 정보
        if "district" in facts and isinstance(facts["district"], dict):
            district = facts["district"]
            if "population" in district:
                props["population"] = district["population"]
            if "appropriate_demand" in district:
                props["appropriate_demand"] = district["appropriate_demand"]
        
        # 공급 리스크 상태
        if "supply" in facts and isinstance(facts["supply"], dict):
            supply = facts["supply"]
            if "risk_status" in supply:
                props["supply_risk_status"] = supply["risk_status"]
        
        # MERGE 쿼리 실행
        try:
            self.graph.query(
                CYPHER_TEMPLATES["merge_region"],
                {"name": region_name, "properties": props}
            )
            logger.debug(f"Created/updated Region: {region_name}")
            return region_name
        except Exception as e:
            logger.error(f"Failed to create Region: {e}")
            return None
    
    def _create_complexes(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """ApartmentComplex 노드들 생성"""
        created = []
        
        complexes = facts.get("complexes", []) or facts.get("properties", [])
        if not isinstance(complexes, list):
            return created
        
        for complex_data in complexes:
            if not isinstance(complex_data, dict):
                continue
            
            name = complex_data.get("name") or complex_data.get("complex_name")
            if not name:
                continue
            
            # 속성 수집
            props = {"name": name}
            
            # 가격 정보
            for key in ["sales_price", "jeonse_price", "gap_price"]:
                if key in complex_data:
                    props[key] = complex_data[key]
            
            # 전세가율
            if "jeonse_rate" in complex_data:
                props["jeonse_rate"] = complex_data["jeonse_rate"]
            
            # 저평가 여부
            if "is_undervalued" in complex_data:
                props["is_undervalued"] = complex_data["is_undervalued"]
            elif "undervalued" in complex_data:
                props["is_undervalued"] = complex_data["undervalued"]
            
            # 투자 코멘트
            if "investment_comment" in complex_data:
                props["investment_comment"] = complex_data["investment_comment"][:500]  # 길이 제한
            
            try:
                # 단지 노드 생성
                self.graph.query(
                    CYPHER_TEMPLATES["merge_complex"],
                    {"name": name, "properties": props}
                )
                
                # 지역과 연결
                if region_name:
                    self.graph.query(
                        CYPHER_TEMPLATES["link_complex_to_region"],
                        {"complex_name": name, "region_name": region_name}
                    )
                
                created.append(name)
                logger.debug(f"Created Complex: {name}")
            except Exception as e:
                logger.error(f"Failed to create Complex {name}: {e}")
        
        return created
    
    def _create_grades(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """GradeMetric 노드들 생성"""
        created = []
        
        if not region_name:
            return created
        
        grades = facts.get("grades", {})
        if not isinstance(grades, dict):
            return created
        
        # 카테고리 매핑
        category_map = {
            "jobs": GradeCategory.JOBS,
            "직장": GradeCategory.JOBS,
            "transport": GradeCategory.TRANSPORT,
            "교통": GradeCategory.TRANSPORT,
            "school": GradeCategory.SCHOOL,
            "학군": GradeCategory.SCHOOL,
            "environment": GradeCategory.ENVIRONMENT,
            "환경": GradeCategory.ENVIRONMENT,
        }
        
        for key, grade_data in grades.items():
            category = category_map.get(key.lower())
            if not category:
                continue
            
            if isinstance(grade_data, dict):
                grade_str = grade_data.get("grade", "C")
                raw_value = grade_data.get("raw_value") or grade_data.get("value")
                evidence = grade_data.get("evidence")
            elif isinstance(grade_data, str):
                grade_str = grade_data
                raw_value = None
                evidence = None
            else:
                continue
            
            # 등급 레벨 변환
            try:
                grade = GradeLevel(grade_str.upper())
            except ValueError:
                grade = GradeLevel.C
            
            props = {
                "category": category.value,
                "grade": grade.value,
            }
            if raw_value:
                props["raw_value"] = str(raw_value)
            if evidence:
                props["evidence_text"] = evidence[:500]
            
            try:
                self.graph.query(
                    CYPHER_TEMPLATES["create_grade"],
                    {"region_name": region_name, "properties": props}
                )
                created.append(f"{category.value}:{grade.value}")
                logger.debug(f"Created Grade: {category.value}={grade.value}")
            except Exception as e:
                logger.error(f"Failed to create Grade: {e}")
        
        return created
    
    def _create_supplies(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """SupplyEvent 노드들 생성"""
        created = []
        
        if not region_name:
            return created
        
        supply = facts.get("supply", {})
        if not isinstance(supply, dict):
            return created
        
        # 연도별 공급물량
        yearly = supply.get("yearly_volume", {}) or supply.get("by_year", {})
        if isinstance(yearly, dict):
            for year_str, volume in yearly.items():
                try:
                    year = int(year_str)
                    vol = int(volume) if volume else 0
                except (ValueError, TypeError):
                    continue
                
                props = {"year": year, "volume": vol}
                
                try:
                    self.graph.query(
                        CYPHER_TEMPLATES["create_supply"],
                        {"region_name": region_name, "properties": props}
                    )
                    created.append(f"{year}:{vol}")
                    logger.debug(f"Created Supply: {year}={vol}")
                except Exception as e:
                    logger.error(f"Failed to create Supply: {e}")
        
        return created
    
    def ingest_from_file(self, filepath: Path) -> Dict[str, int]:
        """분석 결과 JSON 파일에서 적재"""
        with open(filepath, 'r', encoding='utf-8') as f:
            result = json.load(f)
        return self.ingest_analysis_result(result)
    
    def batch_ingest(self, results_dir: Path, limit: Optional[int] = None) -> Dict[str, Any]:
        """디렉토리 내 모든 JSON 파일 일괄 적재"""
        results_dir = Path(results_dir)
        files = list(results_dir.glob("*_analysis.json"))
        
        if limit:
            files = files[:limit]
        
        total_stats = {
            "files_processed": 0,
            "files_failed": 0,
            "total_nodes": 0,
            "total_relationships": 0,
        }
        
        for filepath in files:
            try:
                stats = self.ingest_from_file(filepath)
                total_stats["files_processed"] += 1
                total_stats["total_nodes"] += stats["nodes_created"]
                total_stats["total_relationships"] += stats["relationships_created"]
            except Exception as e:
                logger.error(f"Failed to ingest {filepath}: {e}")
                total_stats["files_failed"] += 1
        
        logger.info(f"Batch ingestion complete: {total_stats}")
        return total_stats


if __name__ == "__main__":
    # 테스트 (실제 FalkorDB 연결 없이)
    print("=== Graph Ingester Test ===")
    
    # 샘플 분석 결과
    sample_result = {
        "report_id": "test_001",
        "facts": {
            "district": {
                "name": "부산진구",
                "population": 44035,
                "appropriate_demand": 220
            },
            "grades": {
                "jobs": {"grade": "A", "raw_value": 176113},
                "transport": {"grade": "S", "evidence": "서면역 도보 10분"},
                "school": {"grade": "B"},
                "environment": {"grade": "A"}
            },
            "complexes": [
                {
                    "name": "가야롯데캐슬골드아너",
                    "jeonse_rate": 64.52,
                    "is_undervalued": True,
                    "investment_comment": "교통 호재로 인해 향후 상승 가능성 높음"
                }
            ],
            "supply": {
                "yearly_volume": {
                    "2024": 1500,
                    "2025": 2000,
                    "2026": 656
                }
            }
        }
    }
    
    print(f"Sample result: {json.dumps(sample_result, indent=2, ensure_ascii=False)}")
