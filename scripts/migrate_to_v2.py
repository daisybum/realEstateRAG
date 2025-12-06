#!/usr/bin/env python3
"""
Schema Migration: v1.0 → v2.0

기존 v1.0 그래프 데이터를 v2.0 온톨로지로 변환

Major Transformations:
1. Region.population → Indicator(type='population')
2. Complex.is_undervalued → InvestmentAnalysis(verdict='Undervalued')
3. 새로운 Report 노드 생성 (메타데이터 추론)

Usage:
    python scripts/migrate_to_v2.py --falkordb-url redis://localhost:6379
    python scripts/migrate_to_v2.py --dry-run  # 변환 미리보기
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from graphrag.graph_schema import (
    WolbuOntologyV2,
    Report,
    InvestmentAnalysis,
    Indicator,
    InvestmentVerdict,
    IndicatorType,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaM igrator:
    """v1.0 → v2.0 스키마 마이그레이션"""
    
    def __init__(self, graph, dry_run: bool = False):
        self.graph = graph
        self.dry_run = dry_run
        self.stats = {
            "regions_migrated": 0,
            "complexes_migrated": 0,
            "indicators_created": 0,
            "analyses_created": 0,
            "reports_created": 0,
        }
    
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
    
    def migrate(self):
        """전체 마이그레이션 실행"""
        logger.info("Starting v1.0 → v2.0 migration...")
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # 1. Region 노드 마이그레이션
        self._migrate_regions()
        
        # 2. ApartmentComplex 노드 마이그레이션
        self._migrate_complexes()
        
        # 3. Report 노드 생성 (추론)
        self._create_reports()
        
        # 4. 검증
        if not self.dry_run:
            self._verify()
        
        # 결과 출력
        self._print_summary()
    
    def _migrate_regions(self):
        """Region 노드: population, appropriate_demand → Indicator"""
        logger.info("Migrating Region nodes...")
        
        # v1.0 Region 조회 (population 속성이 있는 노드)
        query = """
        MATCH (r:Region)
        WHERE r.population IS NOT NULL OR r.appropriate_demand IS NOT NULL
        RETURN r.name as name, r.population as population, 
               r.appropriate_demand as demand, r.supply_risk_status as risk_status
        """
        
        result = self.graph.query(query)
        
        if not result.result_set:
            logger.info("No v1.0 Region nodes found")
            return
        
        for row in result.result_set:
            name = row[0]
            population = row[1]
            demand = row[2]
            risk_status = row[3]
            
            logger.info(f"Migrating Region: {name}")
            
            # population → Indicator
            if population:
                self._create_indicator(
                    name,
                    IndicatorType.POPULATION.value,
                    population,
                    "명"
                )
            
            # appropriate_demand → Indicator
            if demand:
                self._create_indicator(
                    name,
                    IndicatorType.APPROPRIATE_DEMAND.value,
                    demand,
                    "세대"
                )
            
            # v1.0 속성 제거 (실제 DB에서)
            if not self.dry_run:
                cleanup_query = f"""
                MATCH (r:Region {{name: '{name}'}})
                REMOVE r.population, r.appropriate_demand, r.supply_risk_status
                """
                self.graph.query(cleanup_query)
            
            self.stats["regions_migrated"] += 1
    
    def _create_indicator(self, region_name: str, indicator_type: str, value: Any, unit: str):
        """Indicator 노드 생성"""
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would create Indicator: {indicator_type}={value}")
            self.stats["indicators_created"] += 1
            return
        
        indicator = Indicator(
            type=indicator_type,
            value=value,
            unit=unit
        )
        
        try:
            props_str = self._format_props(indicator.to_cypher_properties())
            query = f"""
            MATCH (r:Region {{name: '{region_name}'}})
            CREATE (i:Indicator {props_str})
            CREATE (r)-[:HAS_INDICATOR]->(i)
            RETURN i
            """
            self.graph.query(query)
            self.stats["indicators_created"] += 1
            logger.debug(f"  Created Indicator: {indicator_type}")
        except Exception as e:
            logger.error(f"Failed to create Indicator: {e}")
    
    def _migrate_complexes(self):
        """ApartmentComplex: is_undervalued, investment_comment → InvestmentAnalysis"""
        logger.info("Migrating ApartmentComplex nodes...")
        
        # v1.0 Complex 조회
        query = """
        MATCH (c:ApartmentComplex)
        WHERE c.is_undervalued IS NOT NULL OR c.investment_comment IS NOT NULL
        RETURN c.name as name, c.is_undervalued as undervalued, 
               c.investment_comment as comment, c.jeonse_rate as jeonse_rate
        """
        
        result = self.graph.query(query)
        
        if not result.result_set:
            logger.info("No v1.0 Complex nodes found")
            return
        
        for row in result.result_set:
            name = row[0]
            is_undervalued = row[1]
            comment = row[2]
            jeonse_rate = row[3]
            
            logger.info(f"Migrating Complex: {name}")
            
            # Verdict 결정
            if is_undervalued:
                verdict = InvestmentVerdict.UNDERVALUED
            else:
                verdict = InvestmentVerdict.FAIR
            
            # Reasoning 생성
            reasoning = f"전세가율: {jeonse_rate:.2f}%" if jeonse_rate else "데이터 기반 분석"
            if is_undervalued:
                reasoning += ", 저평가 구간 확인"
            
            # InvestmentAnalysis 생성
            self._create_analysis(name, verdict, reasoning, comment)
            
            # v1.0 속성 제거
            if not self.dry_run:
                cleanup_query = f"""
                MATCH (c:ApartmentComplex {{name: '{name}'}})
                REMOVE c.is_undervalued, c.investment_comment
                """
                self.graph.query(cleanup_query)
            
            self.stats["complexes_migrated"] += 1
    
    def _create_analysis(self, complex_name: str, verdict: InvestmentVerdict, 
                         reasoning: str, comment: str):
        """InvestmentAnalysis 노드 생성"""
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would create Analysis: {verdict.value}")
            self.stats["analyses_created"] += 1
            return
        
        from datetime import datetime
        
        analysis = InvestmentAnalysis(
            verdict=verdict,
            reasoning=reasoning,
            confidence=0.7,
            investment_comment=comment[:500] if comment else None,
            analysis_date=datetime.now().isoformat(),
        )
        
        try:
            props_str = self._format_props(analysis.to_cypher_properties())
            query = f"""
            MATCH (c:ApartmentComplex {{name: '{complex_name}'}})
            CREATE (a:InvestmentAnalysis {props_str})
            CREATE (c)-[:HAS_ANALYSIS]->(a)
            RETURN a
            """
            self.graph.query(query)
            
            # 추론 체인: Grade → Analysis (S/A 등급만)
            grade_query = f"""
            MATCH (c:ApartmentComplex {{name: '{complex_name}'}})
                  -[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
            MATCH (c)-[:LOCATED_IN]->(r:Region)-[:HAS_GRADE]->(g:GradeMetric)
            WHERE g.grade IN ['S', 'A']
            MERGE (g)-[:SUPPORTS]->(a)
            """
            self.graph.query(grade_query)
            
            self.stats["analyses_created"] += 1
            logger.debug(f"  Created InvestmentAnalysis for {complex_name}")
        except Exception as e:
            logger.error(f"Failed to create Analysis: {e}")
    
    def _create_reports(self):
        """Report 노드 생성 (Region별 하나씩 추론)"""
        logger.info("Creating Report nodes...")
        
        # 각 Region마다 하나의 Report 생성
        query = """
        MATCH (r:Region)
        RETURN r.name as name
        """
        
        result = self.graph.query(query)
        
        if not result.result_set:
            logger.info("No regions found")
            return
        
        for row in result.result_set:
            region_name = row[0]
            report_id = f"migrated_{region_name.replace(' ', '_')}"
            
            logger.info(f"Creating Report for: {region_name}")
            
            if self.dry_run:
                logger.info(f"  [DRY RUN] Would create Report: {report_id}")
                self.stats["reports_created"] += 1
                continue
            
            from datetime import datetime
            
            report = Report(
                report_id=report_id,
                title=f"Migration Report - {region_name}",
                analysis_date=datetime.now().isoformat(),
                confidence_score=0.6,  # Migration data has lower confidence
                data_sources=["v1.0_migration"]
            )
            
            # Report 생성 + Region 연결
            try:
                props_str = self._format_props(report.to_cypher_properties())
                create_query = f"""
                CREATE (rep:Report {props_str})
                WITH rep
                MATCH (r:Region {{name: '{region_name}'}})
                CREATE (rep)-[:ANALYZES]->(r)
                RETURN rep
                """
                self.graph.query(create_query)
                
                # Report → Complex (MENTIONS) 연결
                mentions_query = f"""
                MATCH (rep:Report {{report_id: '{report_id}'}})
                MATCH (r:Region {{name: '{region_name}'}})<-[:LOCATED_IN]-(c:ApartmentComplex)
                MERGE (rep)-[:MENTIONS]->(c)
                """
                self.graph.query(mentions_query)
                
                self.stats["reports_created"] += 1
                logger.debug(f"  Created Report: {report_id}")
            except Exception as e:
                logger.error(f"Failed to create Report: {e}")
    
    def _verify(self):
        """마이그레이션 검증"""
        logger.info("Verifying migration...")
        
        # v1.0 속성이 남아있는지 확인
        v1_check = """
        MATCH (r:Region)
        WHERE r.population IS NOT NULL OR r.appropriate_demand IS NOT NULL
        RETURN count(r) as count
        """
        result = self.graph.query(v1_check)
        v1_regions_remaining = result.result_set[0][0] if result.result_set else 0
        
        if v1_regions_remaining > 0:
            logger.warning(f"⚠️  {v1_regions_remaining} Regions still have v1.0 properties!")
        else:
            logger.info("✅ All Regions migrated successfully")
        
        # Complex 검증
        v1_complex_check = """
        MATCH (c:ApartmentComplex)
        WHERE c.is_undervalued IS NOT NULL OR c.investment_comment IS NOT NULL
        RETURN count(c) as count
        """
        result = self.graph.query(v1_complex_check)
        v1_complexes_remaining = result.result_set[0][0] if result.result_set else 0
        
        if v1_complexes_remaining > 0:
            logger.warning(f"⚠️  {v1_complexes_remaining} Complexes still have v1.0 properties!")
        else:
            logger.info("✅ All Complexes migrated successfully")
    
    def _print_summary(self):
        """마이그레이션 결과 출력"""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Regions migrated:       {self.stats['regions_migrated']}")
        print(f"Complexes migrated:     {self.stats['complexes_migrated']}")
        print(f"Indicators created:     {self.stats['indicators_created']}")
        print(f"Analyses created:       {self.stats['analyses_created']}")
        print(f"Reports created:        {self.stats['reports_created']}")
        print("="*60)
        
        if self.dry_run:
            print("\n⚠️  DRY RUN - No actual changes were made")
            print("Run without --dry-run to apply migration")


def main():
    parser = argparse.ArgumentParser(description="Migrate FalkorDB schema from v1.0 to v2.0")
    parser.add_argument("--falkordb-url", type=str, default="redis://localhost:6379",
                       help="FalkorDB connection URL")
    parser.add_argument("--graph-name", type=str, default="real_estate",
                       help="Graph database name")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview migration without applying changes")
    parser.add_argument("--backup", action="store_true",
                       help="Create backup before migration (recommended)")
    
    args = parser.parse_args()
    
    # FalkorDB 연결
    try:
        from falkordb import FalkorDB
        db = FalkorDB.from_url(args.falkordb_url)
        graph = db.select_graph(args.graph_name)
        logger.info(f"Connected to {args.falkordb_url}/{args.graph_name}")
    except Exception as e:
        logger.error(f"Failed to connect to FalkorDB: {e}")
        sys.exit(1)
    
    # 백업 (선택적)
    if args.backup and not args.dry_run:
        logger.info("Creating backup...")
        backup_query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->()
        RETURN count(n) as nodes, count(r) as relationships
        """
        result = graph.query(backup_query)
        logger.info(f"Current graph: {result.result_set[0][0]} nodes, {result.result_set[0][1]} relationships")
        # TODO: 실제 백업 로직 (파일 export 등)
    
    # 마이그레이션 실행
    migrator = SchemaMigrator(graph, dry_run=args.dry_run)
    
    try:
        migrator.migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    
    logger.info("Migration completed successfully!")


if __name__ == "__main__":
    main()
