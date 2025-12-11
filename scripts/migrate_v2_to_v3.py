"""
Migration Script: v2.0 → v3.0

v2.0 그래프 데이터를 v3.0 온톨로지로 변환

주요 변환:
1. District.population → MarketSnapshot.population
2. Complex.prices → MarketSnapshot (시계열 분리)
3. GradeMetric → Infra (구체적 시설명이 있는 경우)
"""

import logging
import argparse
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from falkordb import FalkorDB

from graphrag.graph_schema import WolbuOntologyV2
from graphrag.graph_schema_v3 import WolbuOntologyV3
from graphrag.pydantic_models_v3 import Entity, Relationship, EntityType, generate_entity_id

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GraphMigrator:
    """v2.0 → v3.0 그래프 마이그레이션"""
    
    def __init__(self, source_graph, target_graph, migration_date: str = None):
        """
        Args:
            source_graph: v2.0 그래프 (읽기 전용)
            target_graph: v3.0 그래프 (쓰기)
            migration_date: MarketSnapshot 생성 시 사용할 날짜 (YYYY-MM)
        """
        self.source = source_graph
        self.target = target_graph
        self.migration_date = migration_date or datetime.now().strftime("%Y-%m")
        self.v2_ontology = WolbuOntologyV2()
        self.v3_ontology = WolbuOntologyV3()
        
        # 변환 통계
        self.stats = {
            "regions_migrated": 0,
            "complexes_migrated": 0,
            "market_snapshots_created": 0,
            "infra_created": 0,
            "relationships_created": 0,
            "skipped": 0,
        }
    
    def migrate_all(self, dry_run: bool = False) -> Dict[str, int]:
        """전체 마이그레이션 실행
        
        Args:
            dry_run: True면 실제 쓰기 없이 시뮬레이션
        """
        logger.info(f"Starting migration (dry_run={dry_run})...")
        
        # 1. Region 노드 마이그레이션
        logger.info("Migrating Regions...")
        self._migrate_regions(dry_run)
        
        # 2. Complex 노드 마이그레이션
        logger.info("Migrating ApartmentComplexes...")
        self._migrate_complexes(dry_run)
        
        # 3. GradeMetric → Infra 변환 (선택적)
        logger.info("Converting GradeMetrics to Infra (if applicable)...")
        self._convert_grades_to_infra(dry_run)
        
        logger.info(f"Migration complete! Stats: {self.stats}")
        return self.stats
    
    def _migrate_regions(self, dry_run: bool):
        """Region 노드 마이그레이션
        
        v2.0: Region {name, population, supply_volume, ...}
        v3.0: Region {name} + MarketSnapshot {population, supply_volume, date}
        """
        # v2.0 Region 조회
        query = "MATCH (r:Region) RETURN r"
        result = self.source.query(query)
        
        if not result.result_set:
            logger.warning("No regions found in source graph")
            return
        
        for row in result.result_set:
            region_node = row[0]
            region_name = region_node.properties.get("name")
            
            if not region_name:
                logger.warning("Region without name, skipping")
                self.stats["skipped"] += 1
                continue
            
            # v3.0 Region 생성 (정적 정보만)
            if not dry_run:
                create_region_query = f"""
                MERGE (r:Region {{name: '{region_name}'}})
                RETURN r
                """
                self.target.query(create_region_query)
            
            self.stats["regions_migrated"] += 1
            
            # MarketSnapshot 생성 (동적 정보)
            dynamic_props = {}
            for key in ["population", "appropriate_demand", "supply_volume_3yr"]:
                if key in region_node.properties:
                    dynamic_props[key] = region_node.properties[key]
            
            if dynamic_props and not dry_run:
                props_str = self._format_props({
                    "date": self.migration_date,
                    **dynamic_props
                })
                
                create_snapshot_query = f"""
                MATCH (r:Region {{name: '{region_name}'}})
                CREATE (m:MarketSnapshot {props_str})
                CREATE (r)-[:HAS_SNAPSHOT]->(m)
                RETURN m
                """
                self.target.query(create_snapshot_query)
                self.stats["market_snapshots_created"] += 1
                self.stats["relationships_created"] += 1
            
            logger.debug(f"Migrated Region: {region_name}")
    
    def _migrate_complexes(self, dry_run: bool):
        """ApartmentComplex 마이그레이션
        
        v2.0: Complex {name, sales_price, jeonse_price, ...}
        v3.0: Complex {name, built_year} + MarketSnapshot {sales_price, jeonse_price, date}
        """
        query = "MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(r:Region) RETURN c, r.name as region_name"
        result = self.source.query(query)
        
        if not result.result_set:
            logger.warning("No complexes found")
            return
        
        for row in result.result_set:
            complex_node = row[0]
            region_name = row[1]
            
            complex_name = complex_node.properties.get("name")
            if not complex_name:
                self.stats["skipped"] += 1
                continue
            
            # v3.0 Complex 생성 (정적 정보)
            static_props = {"name": complex_name}
            for key in ["households", "built_year", "address"]:
                if key in complex_node.properties:
                    static_props[key] = complex_node.properties[key]
            
            if not dry_run:
                props_str = self._format_props(static_props)
                create_complex_query = f"""
                MERGE (c:ApartmentComplex {{name: '{complex_name}'}})
                SET c += {props_str}
                RETURN c
                """
                self.target.query(create_complex_query)
                
                # Region 연결
                link_query = f"""
                MATCH (c:ApartmentComplex {{name: '{complex_name}'}})
                MATCH (r:Region {{name: '{region_name}'}})
                MERGE (c)-[:LOCATED_IN]->(r)
                """
                self.target.query(link_query)
                self.stats["relationships_created"] += 1
            
            self.stats["complexes_migrated"] += 1
            
            # MarketSnapshot 생성 (가격 정보)
            price_props = {}
            for key in ["sales_price", "jeonse_price", "gap_price", "jeonse_rate"]:
                if key in complex_node.properties:
                    price_props[key] = complex_node.properties[key]
            
            if price_props and not dry_run:
                props_str = self._format_props({
                    "date": self.migration_date,
                    **price_props
                })
                
                create_snapshot_query = f"""
                MATCH (c:ApartmentComplex {{name: '{complex_name}'}})
                CREATE (m:MarketSnapshot {props_str})
                CREATE (c)-[:HAS_SNAPSHOT]->(m)
                RETURN m
                """
                self.target.query(create_snapshot_query)
                self.stats["market_snapshots_created"] += 1
                self.stats["relationships_created"] += 1
            
            logger.debug(f"Migrated Complex: {complex_name}")
    
    def _convert_grades_to_infra(self, dry_run: bool):
        """GradeMetric → Infra 변환 (제한적)
        
        주의: v2.0 GradeMetric은 구체적 시설명이 없으므로
        evidence_text에서 시설명을 추출할 수 있는 경우만 Infra로 변환
        """
        query = """
        MATCH (r:Region)-[:HAS_GRADE]->(g:GradeMetric)
        WHERE g.evidence_text IS NOT NULL
        RETURN r.name as region_name, g.category, g.grade, g.evidence_text
        """
        result = self.source.query(query)
        
        if not result.result_set:
            logger.info("No grades with evidence found")
            return
        
        facility_keywords = {
            "강남역": "Subway",
            "판교역": "Subway",
            "서면역": "Subway",
            "스타필드": "DeptStore",
            "롯데백화점": "DeptStore",
            "신세계백화점": "DeptStore",
        }
        
        for row in result.result_set:
            region_name, category, grade, evidence = row[0], row[1], row[2], row[3]
            
            # evidence에서 시설명 추출 시도
            facility_name = None
            facility_category = None
            
            for keyword, cat in facility_keywords.items():
                if keyword in evidence:
                    facility_name = keyword
                    facility_category = cat
                    break
            
            if facility_name and not dry_run:
                # Infra 노드 생성
                props_str = self._format_props({
                    "name": facility_name,
                    "category": facility_category,
                    "tier": grade,
                })
                
                create_infra_query = f"""
                MERGE (i:Infra {{name: '{facility_name}'}})
                SET i += {props_str}
                RETURN i
                """
                self.target.query(create_infra_query)
                self.stats["infra_created"] += 1
                
                # Region → Infra 연결
                link_query = f"""
                MATCH (r:Region {{name: '{region_name}'}})
                MATCH (i:Infra {{name: '{facility_name}'}})
                MERGE (r)-[:CONTAINS_FACILITY]->(i)
                """
                self.target.query(link_query)
                self.stats["relationships_created"] += 1
                
                logger.debug(f"Created Infra: {facility_name} for {region_name}")
    
    def _format_props(self, props: Dict[str, Any]) -> str:
        """Cypher 속성 포맷"""
        parts = []
        for k, v in props.items():
            if isinstance(v, str):
                safe_v = v.replace("'", "\\'")
                parts.append(f"{k}: '{safe_v}'")
            elif isinstance(v, bool):
                parts.append(f"{k}: {str(v).lower()}")
            elif v is None:
                continue
            else:
                parts.append(f"{k}: {v}")
        return "{" + ", ".join(parts) + "}"
    
    def validate_migration(self) -> Dict[str, bool]:
        """마이그레이션 검증
        
        Returns:
            검증 결과 딕셔너리
        """
        validation = {
            "regions_count_match": False,
            "complexes_count_match": False,
            "market_snapshots_exist": False,
        }
        
        # Region 수 비교
        v2_regions = self.source.query("MATCH (r:Region) RETURN count(r)").result_set[0][0]
        v3_regions = self.target.query("MATCH (r:Region) RETURN count(r)").result_set[0][0]
        validation["regions_count_match"] = (v2_regions == v3_regions)
        
        # Complex 수 비교
        v2_complexes = self.source.query("MATCH (c:ApartmentComplex) RETURN count(c)").result_set[0][0]
        v3_complexes = self.target.query("MATCH (c:ApartmentComplex) RETURN count(c)").result_set[0][0]
        validation["complexes_count_match"] = (v2_complexes == v3_complexes)
        
        # MarketSnapshot 존재 확인
        v3_snapshots = self.target.query("MATCH (m:MarketSnapshot) RETURN count(m)").result_set[0][0]
        validation["market_snapshots_exist"] = (v3_snapshots > 0)
        
        logger.info(f"Validation results: {validation}")
        return validation


def main():
    parser = argparse.ArgumentParser(description="Migrate v2.0 graph to v3.0")
    parser.add_argument("--source-graph", default="wolbu_v2", help="Source graph name (v2.0)")
    parser.add_argument("--target-graph", default="wolbu_v3", help="Target graph name (v3.0)")
    parser.add_argument("--host", default="localhost", help="FalkorDB host")
    parser.add_argument("--port", type=int, default=6379, help="FalkorDB port")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--migration-date", help="Date for MarketSnapshot (YYYY-MM)")
    parser.add_argument("--validate-only", action="store_true", help="Only run validation")
    
    args = parser.parse_args()
    
    # FalkorDB 연결
    db = FalkorDB(host=args.host, port=args.port)
    source_graph = db.select_graph(args.source_graph)
    target_graph = db.select_graph(args.target_graph)
    
    migrator = GraphMigrator(source_graph, target_graph, args.migration_date)
    
    if args.validate_only:
        logger.info("Running validation only...")
        results = migrator.validate_migration()
        all_pass = all(results.values())
        print(f"\n{'✅' if all_pass else '❌'} Validation {'PASSED' if all_pass else 'FAILED'}")
        for key, value in results.items():
            print(f"  {'✅' if value else '❌'} {key}: {value}")
        return 0 if all_pass else 1
    
    # 마이그레이션 실행
    stats = migrator.migrate_all(dry_run=args.dry_run)
    
    print("\n=== Migration Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    if not args.dry_run:
        print("\nRunning validation...")
        validation = migrator.validate_migration()
        all_pass = all(validation.values())
        print(f"\n{'✅' if all_pass else '❌'} Validation {'PASSED' if all_pass else 'FAILED'}")
    
    return 0


if __name__ == "__main__":
    exit(main())
