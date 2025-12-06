#!/usr/bin/env python3
"""
Batch Graph Ingestion Script

기존 분석 결과 JSON 파일들을 FalkorDB에 일괄 적재

Usage:
    # 모든 분석 결과 적재
    python scripts/batch_ingest.py --results-dir analysis_results/
    
    # 최대 100개만 적재
    python scripts/batch_ingest.py --results-dir analysis_results/ --limit 100
    
    # 그래프 초기화 후 적재
    python scripts/batch_ingest.py --results-dir analysis_results/ --reset
"""

import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from graphrag import GraphIngester
from graphrag.graph_schema import GraphSchemaManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Batch ingest analysis results to FalkorDB")
    parser.add_argument("--results-dir", type=str, required=True,
                       help="Directory containing *_analysis.json files")
    parser.add_argument("--falkordb-url", type=str, default="redis://localhost:6379",
                       help="FalkorDB connection URL")
    parser.add_argument("--graph-name", type=str, default="real_estate",
                       help="Graph database name")
    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of files to process")
    parser.add_argument("--reset", action="store_true",
                       help="Reset graph before ingestion (DELETE ALL DATA)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Count files without actual ingestion")
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        logger.error(f"Results directory not found: {results_dir}")
        sys.exit(1)
    
    # 파일 카운트
    files = list(results_dir.glob("*_analysis.json"))
    logger.info(f"Found {len(files)} analysis files in {results_dir}")
    
    if args.dry_run:
        logger.info("Dry run mode - no changes will be made")
        if args.limit:
            logger.info(f"Would process {min(len(files), args.limit)} files")
        else:
            logger.info(f"Would process all {len(files)} files")
        return
    
    # FalkorDB 연결
    try:
        from falkordb import FalkorDB
        db = FalkorDB.from_url(args.falkordb_url)
        graph = db.select_graph(args.graph_name)
        logger.info(f"Connected to FalkorDB: {args.falkordb_url}/{args.graph_name}")
    except Exception as e:
        logger.error(f"Failed to connect to FalkorDB: {e}")
        logger.error("Make sure FalkorDB is running: docker compose -f docker/falkordb/docker-compose.yml up -d")
        sys.exit(1)
    
    # 그래프 초기화 (선택적)
    if args.reset:
        logger.warning("Resetting graph - ALL DATA WILL BE DELETED!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            logger.info("Cancelled.")
            return
        
        schema_manager = GraphSchemaManager(graph)
        schema_manager.drop_all()
        logger.info("Graph reset complete.")
    
    # Ingester 초기화
    ingester = GraphIngester(graph, auto_init_schema=True)
    
    # 적재 전 통계
    schema_manager = GraphSchemaManager(graph)
    before_stats = schema_manager.get_statistics()
    logger.info(f"Before ingestion: {before_stats}")
    
    # 일괄 적재
    stats = ingester.batch_ingest(results_dir, limit=args.limit)
    
    # 적재 후 통계
    after_stats = schema_manager.get_statistics()
    logger.info(f"After ingestion: {after_stats}")
    
    # 결과 출력
    print("\n" + "="*50)
    print("BATCH INGESTION COMPLETE")
    print("="*50)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Files failed:    {stats['files_failed']}")
    print(f"Nodes created:   {stats['total_nodes']}")
    print(f"Relationships:   {stats['total_relationships']}")
    print("="*50)
    
    # 노드 증가량
    for label in after_stats:
        diff = after_stats[label] - before_stats.get(label, 0)
        if diff > 0:
            print(f"  {label}: +{diff} (total: {after_stats[label]})")


if __name__ == "__main__":
    main()
