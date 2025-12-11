"""
Fast DB Construction Pipeline

DB 구축에 최적화된 경량 파이프라인
- 단일 프롬프트 호출 (db_construction)
- Visual/Sentiment/Insight 단계 스킵
- 직접 그래프 DB 스트리밍 적재
"""
import os
import logging
import argparse
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from data_loader import DataLoader, ReportData
from prompt_manager import PromptManager
from qwen_analyzer import QwenAnalyzer
from config_loader import get_config

# GraphRAG 연동
try:
    from graphrag import GraphIngester
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FastDBPipeline:
    """DB 구축 전용 경량 파이프라인
    
    특징:
    - 단일 프롬프트 (db_construction.yaml)
    - 중간 출력 파일 저장 생략 (선택적)
    - 바로 그래프 DB 적재
    - 처리 시간 약 70% 단축
    """
    
    def __init__(self, 
                 analyzer: QwenAnalyzer,
                 prompt_manager: PromptManager,
                 graph_ingester: 'GraphIngester',
                 save_intermediate: bool = False,
                 output_dir: Optional[Path] = None):
        self.analyzer = analyzer
        self.pm = prompt_manager
        self.graph_ingester = graph_ingester
        self.save_intermediate = save_intermediate
        self.output_dir = output_dir
        
        if save_intermediate and output_dir:
            self.output_dir.mkdir(exist_ok=True)
    
    def process(self, data: ReportData) -> Optional[dict]:
        """단일 보고서 DB 적재
        
        Args:
            data: ReportData 객체
            
        Returns:
            적재 통계 또는 None (실패 시)
        """
        # 입력 품질 검증
        if data.is_empty or len(data.images) == 0:
            logger.warning(f"Skipping empty report {data.id}")
            return None
        
        logger.info(f"Processing report {data.id} (fast mode)...")
        
        try:
            # 이미지 선별 (선택적 - 성능 최적화)
            selected_images = self._select_key_images(data.images, max_count=8)
            logger.info(f"  - Selected {len(selected_images)}/{len(data.images)} key images")
            
            # DB 구축용 데이터 추출 (간소화 프롬프트)
            prompt = self.pm.get_prompt("db_construction", version="prod")
            facts_json = self.analyzer.analyze(data.text, selected_images, prompt)
            
            # 결과 구성
            result = {
                "report_id": data.id,
                "facts": facts_json,
                # input_quality는 그래프 적재에 불필요하므로 생략
            }
            
            # 중간 파일 저장 (선택적)
            if self.save_intermediate:
                self._save_intermediate(data.id, result)
            
            # 그래프 DB 적재
            stats = self.graph_ingester.ingest_analysis_result(result)
            logger.info(
                f"  - Graph: {stats['nodes_created']} nodes, "
                f"{stats['relationships_created']} rels"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to process report {data.id}: {e}")
            return None
    
    def _select_key_images(self, images: list, max_count: int) -> list:
        """핵심 이미지 선택 (차트, 지도, 가격표 우선)
        
        Args:
            images: 전체 이미지 경로 리스트
            max_count: 최대 선택 개수
            
        Returns:
            선택된 이미지 경로 리스트
        """
        if len(images) <= max_count:
            return images
        
        # 파일명 기반 우선순위
        priority_keywords = [
            'chart', 'map', 'price', 'table', 'graph',
            '차트', '지도', '가격', '표', '그래프'
        ]
        
        priority_images = [
            img for img in images 
            if any(kw in Path(img).stem.lower() for kw in priority_keywords)
        ]
        other_images = [img for img in images if img not in priority_images]
        
        # 우선순위 이미지부터 채우고, 부족하면 나머지에서 순서대로
        selected = priority_images[:max_count]
        if len(selected) < max_count:
            selected += other_images[:max_count - len(selected)]
        
        return selected
    
    def _save_intermediate(self, report_id: str, result: dict) -> None:
        """중간 결과 저장 (디버깅용)"""
        import json
        
        output_file = self.output_dir / f"{report_id}_db_data.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.debug(f"  - Saved intermediate data to {output_file}")


def parse_args() -> argparse.Namespace:
    """커맨드라인 인자 파싱"""
    config = get_config()
    system = config.system
    
    parser = argparse.ArgumentParser(
        description="Fast DB Construction Pipeline with Qwen3-VL"
    )
    parser.add_argument("--data_dir", type=str, default=system.data_dir)
    parser.add_argument("--output_dir", type=str, default=system.output_dir)
    parser.add_argument("--report_id", type=str, help="특정 보고서 ID만 처리")
    parser.add_argument("--api_url", type=str, default=system.api_url)
    parser.add_argument("--model", type=str, default=system.model_name)
    parser.add_argument("--api_key", type=str, default=system.api_key)
    parser.add_argument("--max_samples", type=int, default=system.max_samples)
    parser.add_argument("--save-intermediate", action="store_true",
                       help="중간 JSON 파일 저장 (디버깅용)")
    parser.add_argument("--falkordb-url", type=str, default="redis://localhost:6379",
                       help="FalkorDB connection URL")
    
    return parser.parse_args()


def main():
    """메인 진입점"""
    args = parse_args()
    
    # 컴포넌트 초기화
    loader = DataLoader(args.data_dir)
    prompt_manager = PromptManager()
    analyzer = QwenAnalyzer(
        api_key=args.api_key,
        base_url=args.api_url,
        model_name=args.model,
    )
    
    # GraphRAG 연동
    if not GRAPHRAG_AVAILABLE:
        logger.error("GraphRAG package not available. Install falkordb: pip install falkordb")
        return
    
    try:
        from falkordb import FalkorDB
        db = FalkorDB.from_url(args.falkordb_url)
        graph = db.select_graph("real_estate")
        graph_ingester = GraphIngester(graph)
        logger.info(f"Connected to FalkorDB: {args.falkordb_url}")
    except Exception as e:
        logger.error(f"Failed to connect to FalkorDB: {e}")
        return
    
    # Fast Pipeline 초기화
    pipeline = FastDBPipeline(
        analyzer=analyzer,
        prompt_manager=prompt_manager,
        graph_ingester=graph_ingester,
        save_intermediate=args.save_intermediate,
        output_dir=Path(args.output_dir) if args.save_intermediate else None,
    )
    
    # 보고서 목록 결정
    if args.report_id:
        report_ids = [args.report_id]
    else:
        report_ids = loader.get_report_ids()
    
    logger.info(f"Found {len(report_ids)} reports to process")
    logger.info(f"Using model: {analyzer.model_name}")
    logger.info("Mode: FAST DB CONSTRUCTION (optimized)")
    
    # 처리 실행
    success_count = 0
    total_stats = {
        "nodes_created": 0,
        "relationships_created": 0,
        "reports": 0,
        "complexes": 0,
    }
    
    for rid in tqdm(report_ids[:args.max_samples], desc="Processing"):
        try:
            data = loader.load_report(rid)
            stats = pipeline.process(data)
            if stats:
                success_count += 1
                total_stats["nodes_created"] += stats.get("nodes_created", 0)
                total_stats["relationships_created"] += stats.get("relationships_created", 0)
                total_stats["reports"] += stats.get("reports", 0)
                total_stats["complexes"] += stats.get("complexes", 0)
        except FileNotFoundError as e:
            logger.error(f"Report not found: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {rid}: {e}")
    
    # 최종 통계
    logger.info("=" * 60)
    logger.info(f"Completed: {success_count}/{len(report_ids[:args.max_samples])} reports processed")
    logger.info(f"Total nodes created: {total_stats['nodes_created']}")
    logger.info(f"Total relationships: {total_stats['relationships_created']}")
    logger.info(f"Total reports: {total_stats['reports']}")
    logger.info(f"Total complexes: {total_stats['complexes']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
