"""
Graph Ingester v2.0

분석 결과 JSON을 v2.0 온톨로지로 변환하여 FalkorDB에 적재
추론 체인 구축 지원
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from .graph_schema import (
    WolbuOntologyV2,
    Report,
    Region,
    ApartmentComplex,
    InvestmentAnalysis,
    Indicator,
    GradeMetric,
    SupplyEvent,
    GradeCategory,
    GradeLevel,
    InvestmentVerdict,
    IndicatorType,
    CYPHER_TEMPLATES_V2,
)

logger = logging.getLogger(__name__)


class GraphIngesterV2:
    """분석 결과 JSON → FalkorDB v2.0 그래프 적재"""
    
    def __init__(self, graph, auto_init_schema: bool = True):
        self.graph = graph
        self.ontology = WolbuOntologyV2()
        
        if auto_init_schema:
            self._ensure_schema()
    
    def _ensure_schema(self):
        """스키마 초기화"""
        from .graph_schema import GraphSchemaManager
        manager = GraphSchemaManager(self.graph)
        manager.initialize_schema()
    
    def ingest_analysis_result(self, result: Dict[str, Any]) -> Dict[str, int]:
        """
        분석 결과 JSON을 v2.0 그래프에 적재
        
        Args:
            result: {
                "report_id": "...",
                "input_quality": {...},
                "facts": {...},
                "verification": {...},
                "sentiment": {...},
                "insight": "..."
            }
        
        Returns:
            적재 통계
        """
        stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "reports": 0,
            "complexes": 0,
            "analyses": 0,
            "indicators": 0,
        }
        
        # facts 파싱
        facts = self._parse_facts(result.get("facts", {}))
        if not facts:
            logger.warning(f"No facts to ingest for report {result.get('report_id')}")
            return stats
        
        # 1. Report 노드 생성 (NEW in v2.0)
        report_id = result.get("report_id")
        if report_id:
            self._create_report_node(result)
            stats["nodes_created"] += 1
            stats["reports"] += 1
        
        # 2. Region 노드 생성 (간소화)
        region_name = self._create_region(facts)
        if region_name:
            stats["nodes_created"] += 1
            
            # Report → Region 연결
            if report_id:
                self._link_report_to_region(report_id, region_name)
                stats["relationships_created"] += 1
        
        # 3. Indicator 노드들 생성 (NEW in v2.0)
        indicators = self._create_indicators(facts, region_name)
        stats["nodes_created"] += len(indicators)
        stats["relationships_created"] += len(indicators)  # HAS_INDICATOR
        stats["indicators"] += len(indicators)
        
        # 4. GradeMetric 노드들 생성 (변경 없음)
        grades = self._create_grades(facts, region_name)
        stats["nodes_created"] += len(grades)
        stats["relationships_created"] += len(grades)  # HAS_GRADE
        
        # 5. ApartmentComplex 노드들 생성 (간소화)
        complexes = self._create_complexes(facts, region_name, report_id)
        stats["nodes_created"] += len(complexes)
        stats["relationships_created"] += len(complexes)  # LOCATED_IN
        stats["complexes"] += len(complexes)
        
        # 6. InvestmentAnalysis 노드들 생성 + 추론 체인 연결 (NEW in v2.0)
        analyses = self._create_analyses(facts, region_name, grades)
        stats["nodes_created"] += analyses
        stats["relationships_created"] += analyses  # HAS_ANALYSIS
        stats["analyses"] += analyses
        
        # 추론 체인: Grade → Analysis (SUPPORTS)
        stats["relationships_created"] += analyses * len(grades)  # 근사치
        
        # 7. SupplyEvent 노드들 생성 (선택적)
        supplies = self._create_supplies(facts, region_name)
        stats["nodes_created"] += len(supplies)
        stats["relationships_created"] += len(supplies)
        
        return stats
    
    def _format_props(self, props: Dict[str, Any]) -> str:
        """딕셔너리를 Cypher 속성 문자열로 변환"""
        parts = []
        for k, v in props.items():
            if isinstance(v, str):
                safe_v = v.replace("'", "\\'")  # 이스케이프
                parts.append(f"{k}: '{safe_v}'")
            elif isinstance(v, bool):
                parts.append(f"{k}: {str(v).lower()}")
            elif v is None:
                continue
            else:
                parts.append(f"{k}: {v}")
        return "{" + ", ".join(parts) + "}"

    def _parse_facts(self, facts: Any) -> Dict[str, Any]:
        """facts 데이터 파싱"""
        if isinstance(facts, dict):
            return facts
        
        if isinstance(facts, str):
            try:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', facts, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
            
            try:
                return json.loads(facts)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse facts string")
                return {}
        
        return {}
    
    def _create_report_node(self, result: Dict) -> Optional[str]:
        """Report 노드 생성 (NEW in v2.0)"""
        report_id = result.get("report_id")
        if not report_id:
            return None
        
        # input_quality에서 메타데이터 추출
        input_quality = result.get("input_quality", {})
        
        report = Report(
            report_id=report_id,
            title=f"Report {report_id}",  # 실제로는 facts에서 추출 가능
            analysis_date=datetime.now().isoformat(),
            confidence_score=input_quality.get("confidence_score"),
            data_sources=input_quality.get("data_sources", []),
        )
        
        try:
            props_str = self._format_props(report.to_cypher_properties())
            query = f"CREATE (r:Report {props_str}) RETURN r"
            self.graph.query(query)
            logger.debug(f"Created Report: {report_id}")
            return report_id
        except Exception as e:
            logger.error(f"Failed to create Report: {e}")
            return None
    
    def _create_region(self, facts: Dict) -> Optional[str]:
        """Region 노드 생성 (간소화 - 지표 제거)"""
        region_name = None
        
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
            logger.warning("Could not extract region name")
            return None
        
        # 간단한 속성만 저장 (population 등은 Indicator로 이동)
        props = {"name": region_name}
        
        try:
            props_str = self._format_props(props)
            query = f"MERGE (r:Region {{name: '{region_name}'}}) SET r += {props_str} RETURN r"
            self.graph.query(query)
            logger.debug(f"Created/updated Region: {region_name}")
            return region_name
        except Exception as e:
            logger.error(f"Failed to create Region: {e}")
            return None
    
    def _create_indicators(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """Indicator 노드들 생성 (NEW in v2.0)"""
        created = []
        
        if not region_name:
            return created
        
        indicators_data = []
        
        # district에서 지표 추출
        if "district" in facts and isinstance(facts["district"], dict):
            district = facts["district"]
            
            if "population" in district:
                indicators_data.append(
                    Indicator(
                        type=IndicatorType.POPULATION.value,
                        value=district["population"],
                        unit="명"
                    )
                )
            
            if "appropriate_demand" in district:
                indicators_data.append(
                    Indicator(
                        type=IndicatorType.APPROPRIATE_DEMAND.value,
                        value=district["appropriate_demand"],
                        unit="세대"
                    )
                )
        
        # supply에서 지표 추출
        if "supply" in facts and isinstance(facts["supply"], dict):
            supply = facts["supply"]
            
            # 3년간 공급물량
            supply_3yr = 0
            yearly = supply.get("yearly_volume", {}) or supply.get("by_year", {})
            if isinstance(yearly, dict):
                for year_str, volume in yearly.items():
                    try:
                        year = int(year_str)
                        if 2024 <= year <= 2026:  # 최근 3년
                            supply_3yr += int(volume) if volume else 0
                    except (ValueError, TypeError):
                        continue
            
            if supply_3yr > 0:
                indicators_data.append(
                    Indicator(
                        type=IndicatorType.SUPPLY_VOLUME_3YR.value,
                        value=supply_3yr,
                        unit="세대"
                    )
                )
        
        # Indicator 노드 생성 및 Region 연결
        for indicator in indicators_data:
            try:
                props_str = self._format_props(indicator.to_cypher_properties())
                query = f"""
                MATCH (r:Region {{name: '{region_name}'}})
                CREATE (i:Indicator {props_str})
                CREATE (r)-[:HAS_INDICATOR]->(i)
                RETURN i
                """
                self.graph.query(query)
                created.append(f"{indicator.type}:{indicator.value}")
                logger.debug(f"Created Indicator: {indicator.type}={indicator.value}")
            except Exception as e:
                logger.error(f"Failed to create Indicator: {e}")
        
        return created
    
    def _create_grades(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """GradeMetric 노드들 생성 (변경 없음)"""
        created = []
        
        if not region_name:
            return created
        
        grades = facts.get("grades", {})
        if not isinstance(grades, dict):
            return created
        
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
            
            try:
                grade = GradeLevel(grade_str.upper())
            except ValueError:
                grade = GradeLevel.C
            
            props = {
                "category": category.value,
                "grade": grade.value,
            }
            if raw_value is not None:
                props["raw_value"] = str(raw_value)
            if evidence:
                props["evidence_text"] = evidence[:500]
            
            try:
                # GradeMetric 생성 쿼리 (Region 연결)
                props_str = self._format_props(props)
                query = f"""
                MATCH (r:Region {{name: '{region_name}'}})
                CREATE (g:GradeMetric {props_str})
                CREATE (r)-[:HAS_GRADE]->(g)
                RETURN g
                """
                self.graph.query(query)
                created.append(f"{category.value}:{grade.value}")
                logger.debug(f"Created Grade: {category.value}={grade.value}")
            except Exception as e:
                logger.error(f"Failed to create Grade: {e}")
        
        return created
    
    def _create_complexes(self, facts: Dict, region_name: Optional[str], report_id: Optional[str]) -> List[str]:
        """ApartmentComplex 노드들 생성 (간소화)"""
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
            
            # 가격 정보만 저장 (is_undervalued, investment_comment 제거)
            props = {"name": name}
            
            for key in ["sales_price", "jeonse_price", "gap_price"]:
                if key in complex_data:
                    props[key] = complex_data[key]
            
            if "jeonse_rate" in complex_data:
                props["jeonse_rate"] = complex_data["jeonse_rate"]
            
            try:
                # Complex 노드 생성
                props_str = self._format_props(props)
                query = f"MERGE (c:ApartmentComplex {{name: '{name}'}}) SET c += {props_str}"
                self.graph.query(query)
                
                # Region 연결
                if region_name:
                    query = f"""
                    MATCH (c:ApartmentComplex {{name: '{name}'}})
                    MATCH (r:Region {{name: '{region_name}'}})
                    MERGE (c)-[:LOCATED_IN]->(r)
                    """
                    self.graph.query(query)
                
                # Report 연결 (NEW)
                if report_id:
                    query = f"""
                    MATCH (c:ApartmentComplex {{name: '{name}'}})
                    MATCH (rep:Report {{report_id: '{report_id}'}})
                    MERGE (rep)-[:MENTIONS]->(c)
                    """
                    self.graph.query(query)
                
                created.append(name)
                logger.debug(f"Created Complex: {name}")
            except Exception as e:
                logger.error(f"Failed to create Complex {name}: {e}")
        
        return created
    
    def _create_analyses(self, facts: Dict, region_name: Optional[str], grades: List[str]) -> int:
        """InvestmentAnalysis 노드들 생성 + 추론 체인 연결 (NEW in v2.0)"""
        created_count = 0
        
        complexes = facts.get("complexes", []) or facts.get("properties", [])
        if not isinstance(complexes, list):
            return created_count
        
        for complex_data in complexes:
            if not isinstance(complex_data, dict):
                continue
            
            name = complex_data.get("name") or complex_data.get("complex_name")
            if not name:
                continue
            
            # is_undervalued, investment_comment 추출
            is_undervalued = complex_data.get("is_undervalued") or complex_data.get("undervalued")
            comment = complex_data.get("investment_comment", "")
            
            # Verdict 결정
            if is_undervalued:
                verdict = InvestmentVerdict.UNDERVALUED
            else:
                verdict = InvestmentVerdict.FAIR
            
            # 추론 체인 생성 (간단한 버전)
            reasoning = f"전세가율: {complex_data.get('jeonse_rate', 0):.2f}%"
            if is_undervalued:
                reasoning += ", 저평가 구간"
            
            analysis = InvestmentAnalysis(
                verdict=verdict,
                reasoning=reasoning,
                confidence=0.7,  # 기본값
                investment_comment=comment[:500] if comment else None,
                analysis_date=datetime.now().isoformat(),
            )
            
            try:
                # InvestmentAnalysis 생성 + Complex 연결
                props_str = self._format_props(analysis.to_cypher_properties())
                query = f"""
                MATCH (c:ApartmentComplex {{name: '{name}'}})
                CREATE (a:InvestmentAnalysis {props_str})
                CREATE (c)-[:HAS_ANALYSIS]->(a)
                RETURN a
                """
                self.graph.query(query)
                
                # 추론 체인: Grade → Analysis (SUPPORTS)
                # 모든 S/A 등급을 Analysis에 연결
                for grade_str in grades:
                    if ":S" in grade_str or ":A" in grade_str:
                        category, level = grade_str.split(":")
                        query = f"""
                        MATCH (c:ApartmentComplex {{name: '{name}'}})-[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
                        MATCH (c)-[:LOCATED_IN]->(r:Region)-[:HAS_GRADE]->(g:GradeMetric {{category: '{category}', grade: '{level}'}})
                        MERGE (g)-[:SUPPORTS]->(a)
                        """
                        try:
                            self.graph.query(query)
                        except:
                            pass  # 이미 존재하는 관계 무시
                
                created_count += 1
                logger.debug(f"Created InvestmentAnalysis for: {name}")
            except Exception as e:
                logger.error(f"Failed to create Analysis for {name}: {e}")
        
        return created_count
    
    def _create_supplies(self, facts: Dict, region_name: Optional[str]) -> List[str]:
        """SupplyEvent 노드들 생성 (선택적)"""
        created = []
        
        if not region_name:
            return created
        
        supply = facts.get("supply", {})
        if not isinstance(supply, dict):
            return created
        
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
                    props_str = self._format_props(props)
                    query = f"""
                    MATCH (r:Region {{name: '{region_name}'}})
                    CREATE (s:SupplyEvent {props_str})
                    CREATE (r)-[:HAS_SUPPLY]->(s)
                    RETURN s
                    """
                    self.graph.query(query)
                    created.append(f"{year}:{vol}")
                    logger.debug(f"Created Supply: {year}={vol}")
                except Exception as e:
                    logger.error(f"Failed to create Supply: {e}")
        
        return created
    
    def _link_report_to_region(self, report_id: str, region_name: str):
        """Report → Region 연결 (NEW)"""
        try:
            query = f"""
            MATCH (rep:Report {{report_id: '{report_id}'}})
            MATCH (r:Region {{name: '{region_name}'}})
            MERGE (rep)-[:ANALYZES]->(r)
            """
            self.graph.query(query)
        except Exception as e:
            logger.error(f"Failed to link Report to Region: {e}")
    
    def ingest_from_file(self, filepath: Path) -> Dict[str, int]:
        """파일에서 적재"""
        with open(filepath, 'r', encoding='utf-8') as f:
            result = json.load(f)
        return self.ingest_analysis_result(result)
    
    def batch_ingest(self, results_dir: Path, limit: Optional[int] = None) -> Dict[str, Any]:
        """일괄 적재"""
        results_dir = Path(results_dir)
        files = list(results_dir.glob("*_analysis.json"))
        
        if limit:
            files = files[:limit]
        
        total_stats = {
            "files_processed": 0,
            "files_failed": 0,
            "total_nodes": 0,
            "total_relationships": 0,
            "total_reports": 0,
            "total_analyses": 0,
        }
        
        for filepath in files:
            try:
                stats = self.ingest_from_file(filepath)
                total_stats["files_processed"] += 1
                total_stats["total_nodes"] += stats["nodes_created"]
                total_stats["total_relationships"] += stats["relationships_created"]
                total_stats["total_reports"] += stats.get("reports", 0)
                total_stats["total_analyses"] += stats.get("analyses", 0)
            except Exception as e:
                logger.error(f"Failed to ingest {filepath}: {e}")
                total_stats["files_failed"] += 1
        
        logger.info(f"Batch ingestion complete: {total_stats}")
        return total_stats


# Backward compatibility alias
GraphIngester = GraphIngesterV2


if __name__ == "__main__":
    print("=== Graph Ingester v2.0 ===")
    print("New features:")
    print("- Report node creation")
    print("- InvestmentAnalysis separation")
    print("- Indicator nodes")
    print("- Reasoning chain (Grade → Analysis)")
