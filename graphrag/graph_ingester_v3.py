"""
Graph Ingester v3.0

LLM 출력(entities + relationships)을 v3.0 온톨로지로 변환하여 FalkorDB에 적재
Pydantic 검증 및 entity-centric 구조 지원
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from pydantic import ValidationError

from .graph_schema_v3 import (
    WolbuOntologyV3,
    GraphSchemaManagerV3,
    Neighborhood,
    Infra,
    MarketSnapshot,
    Region,
    ApartmentComplex,
    Report,
    InvestmentAnalysis,
    InfraCategory,
    GradeLevel,
    CYPHER_TEMPLATES_V3,
)

from .pydantic_models_v3 import (
    KnowledgeGraphOutput,
    Entity,
    Relationship,
    EntityType,
    parse_llm_output,
)

logger = logging.getLogger(__name__)


class GraphIngesterV3:
    """LLM 출력 → FalkorDB v3.0 그래프 적재
    
    v2.0과의 주요 차이점:
    - 입력: entities + relationships 리스트 (Pydantic 검증)
    - Entity-specific creation methods
    - Entity resolution (중복 방지)
    - 시계열 데이터 분리 (MarketSnapshot)
    """
    
    def __init__(self, graph, auto_init_schema: bool = True):
        self.graph = graph
        self.ontology = WolbuOntologyV3()
        self.entity_cache = {}  # Entity resolution cache
        
        if auto_init_schema:
            self._ensure_schema()
    
    def _ensure_schema(self):
        """스키마 초기화"""
        manager = GraphSchemaManagerV3(self.graph)
        manager.initialize_schema()
    
    def ingest_knowledge_graph(self, kg_output: KnowledgeGraphOutput) -> Dict[str, int]:
        """v3.0 Knowledge Graph 적재
        
        Args:
            kg_output: Pydantic-validated KnowledgeGraphOutput
            
        Returns:
            적재 통계
        """
        stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "entities_skipped": 0,
        }
        
        # Phase 1: 엔티티 생성 (타입별 순서 중요)
        entity_order = [
            EntityType.REGION,
            EntityType.DISTRICT,
            EntityType.NEIGHBORHOOD,
            EntityType.COMPLEX,
            EntityType.INFRA,
            EntityType.MARKET_SNAPSHOT,
            EntityType.REPORT,
            EntityType.INVESTMENT_ANALYSIS,
        ]
        
        for entity_type in entity_order:
            entities = kg_output.get_entities_by_type(entity_type)
            for entity in entities:
                try:
                    created = self._create_entity(entity)
                    if created:
                        stats["nodes_created"] += 1
                    else:
                        stats["entities_skipped"] += 1
                except Exception as e:
                    logger.error(f"Failed to create entity {entity.id}: {e}")
                    stats["entities_skipped"] += 1
        
        # Phase 2: 관계 생성
        for relationship in kg_output.relationships:
            try:
                created = self._create_relationship(relationship)
                if created:
                    stats["relationships_created"] += 1
            except Exception as e:
                logger.error(f"Failed to create relationship {relationship.type}: {e}")
        
        return stats
    
    def ingest_from_llm_output(self, llm_output: str) -> Dict[str, int]:
        """LLM JSON 출력 파싱 및 적재
        
        Args:
            llm_output: LLM이 생성한 JSON 문자열
            
        Returns:
            적재 통계
        """
        try:
            kg_output = parse_llm_output(llm_output)
            logger.info(f"Parsed {len(kg_output.entities)} entities, {len(kg_output.relationships)} relationships")
            return self.ingest_knowledge_graph(kg_output)
        except ValueError as e:
            logger.error(f"Failed to parse LLM output: {e}")
            raise
    
    def ingest_analysis_result(self, result: Dict[str, Any]) -> Dict[str, int]:
        """v2.0 형식 backward compatibility
        
        Args:
            result: v2.0 형식 분석 결과 (facts 포함)
            
        Returns:
            적재 통계
        """
        # facts가 v3.0 형식인지 확인
        facts = result.get("facts", "")
        
        if isinstance(facts, str):
            # JSON 문자열로 파싱 시도
            try:
                return self.ingest_from_llm_output(facts)
            except:
                logger.warning("v2.0 format detected, falling back to compatibility mode")
                # v2.0 ingester로 위임하거나 에러
                raise ValueError("v2.0 format not supported in v3 ingester. Use GraphIngesterV2 instead.")
        elif isinstance(facts, dict):
            # v3.0 형식 (entities + relationships)
            if "entities" in facts and "relationships" in facts:
                kg_output = KnowledgeGraphOutput(**facts)
                return self.ingest_knowledge_graph(kg_output)
            else:
                raise ValueError("Unknown facts format")
        else:
            raise ValueError(f"Invalid facts type: {type(facts)}")
    
    def _create_entity(self, entity: Entity) -> bool:
        """엔티티 타입별 생성 라우팅
        
        Returns:
            True if created, False if skipped
        """
        # Entity resolution: 이미 생성된 경우 스킵
        if self._entity_exists(entity):
            logger.debug(f"Entity already exists: {entity.id}")
            return False
        
        handlers = {
            EntityType.REGION: self._create_region_node,
            EntityType.DISTRICT: self._create_district_node,
            EntityType.NEIGHBORHOOD: self._create_neighborhood_node,
            EntityType.COMPLEX: self._create_complex_node,
            EntityType.INFRA: self._create_infra_node,
            EntityType.MARKET_SNAPSHOT: self._create_market_snapshot_node,
            EntityType.REPORT: self._create_report_node,
            EntityType.INVESTMENT_ANALYSIS: self._create_analysis_node,
        }
        
        handler = handlers.get(entity.type)
        if handler:
            success = handler(entity)
            if success:
                self.entity_cache[entity.id] = True
            return success
        else:
            logger.warning(f"No handler for entity type: {entity.type}")
            return False
    
    def _entity_exists(self, entity: Entity) -> bool:
        """엔티티가 이미 존재하는지 확인"""
        # Cache check
        if entity.id in self.entity_cache:
            return True
        
        # DB check (optional - 느릴 수 있음)
        # For now, rely on cache only
        return False
    
    def _create_region_node(self, entity: Entity) -> bool:
        """Region 노드 생성"""
        props = {"name": entity.name}
        props.update(entity.properties)
        
        try:
            props_str = self._format_props(props)
            query = f"MERGE (r:Region {{name: '{entity.name}'}}) SET r += {props_str} RETURN r"
            self.graph.query(query)
            logger.debug(f"Created Region: {entity.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Region: {e}")
            return False
    
    def _create_district_node(self, entity: Entity) -> bool:
        """District 노드 생성 (v3.0에서는 Region과 동일하게 처리)"""
        # District는 v3.0에서 Region의 하위 개념
        # 실제로는 hierarchy 관계로 연결되어야 함
        return self._create_region_node(entity)
    
    def _create_neighborhood_node(self, entity: Entity) -> bool:
        """Neighborhood 노드 생성"""
        if not entity.name:
            logger.warning(f"Neighborhood entity missing name: {entity.id}")
            return False
        
        props = {
            "name": entity.name,
            "district": entity.properties.get("district", ""),
        }
        if "region" in entity.properties:
            props["region"] = entity.properties["region"]
        
        try:
            props_str = self._format_props(props)
            query = f"""
            MERGE (n:Neighborhood {{name: '{entity.name}', district: '{props['district']}'}})
            SET n += {props_str}
            RETURN n
            """
            self.graph.query(query)
            logger.debug(f"Created Neighborhood: {entity.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Neighborhood: {e}")
            return False
    
    def _create_complex_node(self, entity: Entity) -> bool:
        """Complex 노드 생성 (가격 정보 제외 - MarketSnapshot으로 이동)"""
        if not entity.name:
            logger.warning(f"Complex entity missing name: {entity.id}")
            return False
        
        # v3.0에서는 정적 정보만 저장
        static_props = {"name": entity.name}
        
        for key in ["households", "built_year", "address"]:
            if key in entity.properties:
                static_props[key] = entity.properties[key]
        
        try:
            props_str = self._format_props(static_props)
            query = f"MERGE (c:ApartmentComplex {{name: '{entity.name}'}}) SET c += {props_str} RETURN c"
            self.graph.query(query)
            logger.debug(f"Created Complex: {entity.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Complex: {e}")
            return False
    
    def _create_infra_node(self, entity: Entity) -> bool:
        """Infra 노드 생성 (NEW in v3.0)"""
        if not entity.name:
            logger.warning(f"Infra entity missing name: {entity.id}")
            return False
        
        props = {
            "name": entity.name,
            "category": entity.properties.get("category"),
            "tier": entity.properties.get("tier"),
        }
        
        # Optional properties
        for key in ["address", "latitude", "longitude"]:
            if key in entity.properties:
                props[key] = entity.properties[key]
        
        try:
            props_str = self._format_props(props)
            query = f"MERGE (i:Infra {{name: '{entity.name}'}}) SET i += {props_str} RETURN i"
            self.graph.query(query)
            logger.debug(f"Created Infra: {entity.name} ({props.get('category')})")
            return True
        except Exception as e:
            logger.error(f"Failed to create Infra: {e}")
            return False
    
    def _create_market_snapshot_node(self, entity: Entity) -> bool:
        """MarketSnapshot 노드 생성 (NEW in v3.0)"""
        if not entity.date:
            logger.warning(f"MarketSnapshot entity missing date: {entity.id}")
            return False
        
        props = {"date": entity.date}
        props.update(entity.properties)
        
        try:
            props_str = self._format_props(props)
            # MarketSnapshot은 MERGE 대신 CREATE (시계열 데이터)
            query = f"CREATE (m:MarketSnapshot {props_str}) RETURN m"
            self.graph.query(query)
            logger.debug(f"Created MarketSnapshot: {entity.date}")
            return True
        except Exception as e:
            logger.error(f"Failed to create MarketSnapshot: {e}")
            return False
    
    def _create_report_node(self, entity: Entity) -> bool:
        """Report 노드 생성"""
        if not entity.name:
            logger.warning(f"Report entity missing name/id: {entity.id}")
            return False
        
        props = {"report_id": entity.name}
        props.update(entity.properties)
        
        try:
            props_str = self._format_props(props)
            query = f"MERGE (r:Report {{report_id: '{entity.name}'}}) SET r += {props_str} RETURN r"
            self.graph.query(query)
            logger.debug(f"Created Report: {entity.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Report: {e}")
            return False
    
    def _create_analysis_node(self, entity: Entity) -> bool:
        """InvestmentAnalysis 노드 생성"""
        props = entity.properties.copy()
        
        try:
            props_str = self._format_props(props)
            # Analysis는 항상 새로 생성 (CREATE)
            query = f"CREATE (a:InvestmentAnalysis {props_str}) RETURN a"
            self.graph.query(query)
            logger.debug(f"Created InvestmentAnalysis")
            return True
        except Exception as e:
            logger.error(f"Failed to create InvestmentAnalysis: {e}")
            return False
    
    def _create_relationship(self, rel: Relationship) -> bool:
        """관계 생성"""
        try:
            # Properties 포맷팅
            props_str = ""
            if rel.properties:
                props_str = "SET r += " + self._format_props(rel.properties)
            
            # Source/Target 노드 찾기 (ID 기반)
            # v3.0에서는 ID를 직접 사용하지 않고 name/date로 매칭
            query = self._build_relationship_query(rel)
            
            if query:
                self.graph.query(query)
                logger.debug(f"Created relationship: {rel.type}")
                return True
            else:
                logger.warning(f"Could not build query for relationship: {rel.type}")
                return False
        except Exception as e:
            logger.error(f"Failed to create relationship {rel.type}: {e}")
            return False
    
    def _build_relationship_query(self, rel: Relationship) -> Optional[str]:
        """관계 타입별 Cypher 쿼리 생성"""
        props_str = ""
        if rel.properties:
            props_str = self._format_props(rel.properties)
            props_str = f"SET r += {props_str}"
        
        # ID에서 entity 정보 추출 (간단한 구현)
        # 실제로는 entity_cache에서 name 정보를 가져와야 함
        
        if rel.type == "LOCATED_IN":
            query = f"""
            MATCH (a {{id: '{rel.source}'}})
            MATCH (b {{id: '{rel.target}'}})
            MERGE (a)-[r:LOCATED_IN]->(b)
            {props_str}
            """
            return query
        
        elif rel.type == "ACCESS_TO":
            query = f"""
            MATCH (d) WHERE d.id = '{rel.source}' OR d.name CONTAINS substring('{rel.source}', 0, 20)
            MATCH (i:Infra) WHERE i.id = '{rel.target}' OR i.name CONTAINS '{rel.target}'
            MERGE (d)-[r:ACCESS_TO]->(i)
            {props_str}
            """
            return query
        
        elif rel.type == "HAS_SNAPSHOT":
            query = f"""
            MATCH (e) WHERE id(e) = '{rel.source}' OR e.name = '{rel.source}'
            MATCH (m:MarketSnapshot) WHERE id(m) = '{rel.target}'
            MERGE (e)-[r:HAS_SNAPSHOT]->(m)
            """
            return query
        
        elif rel.type == "CONTAINS_FACILITY":
            query = f"""
            MATCH (d) WHERE d.id = '{rel.source}'
            MATCH (i:Infra) WHERE i.id = '{rel.target}'
            MERGE (d)-[r:CONTAINS_FACILITY]->(i)
            {props_str}
            """
            return query
        
        else:
            # Generic relationship
            query = f"""
            MATCH (a) WHERE id(a) = '{rel.source}'
            MATCH (b) WHERE id(b) = '{rel.target}'
            MERGE (a)-[r:{rel.type}]->(b)
            {props_str}
            """
            return query
    
    def _format_props(self, props: Dict[str, Any]) -> str:
        """딕셔너리를 Cypher 속성 문자열로 변환"""
        parts = []
        for k, v in props.items():
            if isinstance(v, str):
                safe_v = v.replace("'", "\\'")
                parts.append(f"{k}: '{safe_v}'")
            elif isinstance(v, bool):
                parts.append(f"{k}: {str(v).lower()}")
            elif v is None:
                continue
            elif isinstance(v, (int, float)):
                parts.append(f"{k}: {v}")
            else:
                # List, dict 등은 JSON으로 변환
                safe_v = json.dumps(v).replace("'", "\\'")
                parts.append(f"{k}: '{safe_v}'")
        return "{" + ", ".join(parts) + "}"
    
    def ingest_from_file(self, filepath: Path) -> Dict[str, int]:
        """파일에서 적재"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # v3.0 형식 check
        if "entities" in data and "relationships" in data:
            kg_output = KnowledgeGraphOutput(**data)
            return self.ingest_knowledge_graph(kg_output)
        else:
            # v2.0 형식
            return self.ingest_analysis_result(data)
    
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


# Alias for consistency
GraphIngester = GraphIngesterV3


if __name__ == "__main__":
    print("=== Graph Ingester v3.0 ===")
    print("Features:")
    print("- Pydantic-based validation")
    print("- Entity-centric ingestion")
    print("- Entity resolution")
    print("- Time-series separation (MarketSnapshot)")
