"""
Real Estate Analysis Pipeline

부동산 임장 보고서 분석 파이프라인 메인 진입점
Ontology-based Knowledge Graph 구축을 위한 정보 추출
"""
import os
import json
import logging
import argparse
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from data_loader import DataLoader, ReportData
from prompt_manager import PromptManager
from qwen_analyzer import QwenAnalyzer
from config_loader import get_config

# GraphRAG 연동 (선택적)
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


def setup_langsmith():
    """LangSmith 트레이싱 초기화 (SecretsManager 사용)"""
    from secrets_manager import get_langsmith_config
    
    config = get_langsmith_config()
    
    if config["enabled"]:
        os.environ["LANGSMITH_TRACING"] = "true" if config["tracing"] else "false"
        os.environ["LANGSMITH_PROJECT"] = config["project"]
        os.environ["LANGSMITH_API_KEY"] = config["api_key"]
        os.environ["LANGSMITH_ENDPOINT"] = config["endpoint"]
        
        logger.info(f"LangSmith tracing enabled for project: {config['project']}")
        return True
    else:
        logger.info("LangSmith disabled (no API key found)")
        return False


class AnalysisPipeline:
    """부동산 분석 파이프라인
    
    단계:
    1. Fact Extraction - 팩트 추출
    2. Visual Verification - 시각적 검증
    3. Sentiment Analysis - 감성 분석
    4. Insight Generation - 인사이트 생성
    """
    
    def __init__(self, 
                 analyzer: QwenAnalyzer, 
                 prompt_manager: PromptManager,
                 output_dir: Path,
                 graph_ingester: 'GraphIngester' = None):
        self.analyzer = analyzer
        self.pm = prompt_manager
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.graph_ingester = graph_ingester
    
    def process(self, data: ReportData) -> Optional[dict]:
        """단일 보고서 분석
        
        Args:
            data: ReportData 객체
            
        Returns:
            분석 결과 딕셔너리 또는 None (실패 시)
        """
        # 입력 품질 검증
        if data.is_empty:
            logger.warning(f"Skipping empty report {data.id}")
            return None
        
        # 입력 품질 검증: 이미지 또는 문서가 없으면 스킵
        has_images = len(data.images) > 0
        if not has_images:
            logger.warning(
                f"Skipping {data.id}: No images found"
            )
            return None
        
        logger.info(f"Processing report {data.id}...")
        
        # 입력 품질 메트릭 계산
        input_quality = self._calculate_input_quality(data)
        
        try:
            # 1. 팩트 추출
            facts_json = self._extract_facts(data)
            
            # 2. 시각적 검증
            verification = self._verify_visuals(data)
            
            # 3. 감성 분석
            sentiment = self._analyze_sentiment(data)
            
            # 4. 인사이트 생성
            region_name = self._extract_region_name(facts_json)
            insight_raw = self._generate_insight(
                region_name, facts_json, verification, sentiment
            )
            
            # 5. 인사이트 후처리 (반복 패턴 제거)
            insight = self._remove_repetition(insight_raw)
            
            # 결과 저장 (신뢰도 점수 포함)
            result = {
                "report_id": data.id,
                "input_quality": input_quality,
                "facts": facts_json,
                "verification": verification,
                "sentiment": sentiment,
                "insight": insight,
            }
            
            self._save_result(data.id, result)
            
            # Graph 적재 (활성화된 경우)
            if self.graph_ingester:
                try:
                    stats = self.graph_ingester.ingest_analysis_result(result)
                    logger.info(f"  - Graph: {stats['nodes_created']} nodes, {stats['relationships_created']} rels")
                except Exception as ge:
                    logger.warning(f"  - Graph ingestion failed: {ge}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process report {data.id}: {e}")
            return None
    
    def _calculate_input_quality(self, data: ReportData) -> dict:
        """입력 데이터 품질 메트릭 계산"""
        text_length = len(data.text)
        image_count = len(data.images)
        
        # 신뢰도 점수 계산 (0.0 ~ 1.0)
        text_score = min(text_length / 1000, 1.0)  # 1000자 이상이면 만점
        image_score = min(image_count / 5, 1.0)   # 5개 이상이면 만점
        confidence_score = round((text_score * 0.7) + (image_score * 0.3), 2)
        
        # 데이터 소스 식별
        data_sources = []
        if text_length > 500:
            data_sources.append("full_text")
        elif text_length > 100:
            data_sources.append("partial_text")
        else:
            data_sources.append("title_only")
        
        if image_count > 0:
            data_sources.append(f"images_{image_count}")
        
        # 할루시네이션 경고
        warnings = []
        if text_length < 300:
            warnings.append("Low text content - higher hallucination risk")
        if image_count == 0:
            warnings.append("No images - visual claims may be fabricated")
        if text_length < 500 and image_count < 3:
            warnings.append("Insufficient data - results may be unreliable")
        
        return {
            "confidence_score": confidence_score,
            "text_length": text_length,
            "image_count": image_count,
            "data_sources": data_sources,
            "hallucination_warnings": warnings,
        }
    
    def _extract_facts(self, data: ReportData) -> str:
        """팩트 추출"""
        logger.info("  - Extracting facts...")
        prompt = self.pm.get_fact_extraction_prompt()
        return self.analyzer.analyze(data.text, data.images, prompt)
    
    def _verify_visuals(self, data: ReportData) -> str:
        """시각적 검증"""
        logger.info("  - Verifying visuals...")
        prompt = self.pm.get_visual_verification_prompt()
        return self.analyzer.analyze(data.text, data.images, prompt)
    
    def _analyze_sentiment(self, data: ReportData) -> str:
        """감성 분석"""
        logger.info("  - Analyzing sentiment...")
        prompt = self.pm.get_sentiment_analysis_prompt()
        return self.analyzer.analyze(data.text, [], prompt)
    
    def _generate_insight(self, 
                          region_name: str, 
                          facts: str, 
                          verification: str, 
                          sentiment: str) -> str:
        """인사이트 생성 (입력 크기 제한 적용)"""
        logger.info("  - Generating insights...")
        
        # 토큰 제한을 위해 입력 데이터 크기 제한 (총 ~20K 문자)
        MAX_CHARS = 6000
        facts_truncated = self._truncate_smart(facts, MAX_CHARS)
        verification_truncated = self._truncate_smart(verification, MAX_CHARS)
        sentiment_truncated = self._truncate_smart(sentiment, MAX_CHARS)
        
        prompt = self.pm.get_insight_generation_prompt()
        return self.analyzer.analyze(
            "", [], prompt,
            region_name=region_name,
            fact_data=facts_truncated,
            verification_result=verification_truncated,
            risk_analysis=sentiment_truncated,
        )
    
    def _truncate_smart(self, text: str, max_chars: int) -> str:
        """스마트 텍스트 잘라내기 (JSON 구조 보존 시도)"""
        if len(text) <= max_chars:
            return text
        
        # 청크 연결된 텍스트에서 JSON 추출 시도
        # "=== Chunk X ===" 패턴 감지
        if "=== Chunk" in text:
            return self._extract_summary_from_chunks(text, max_chars)
        
        # JSON인 경우 핵심 필드만 추출 시도
        try:
            clean = text.replace("```json", "").replace("```", "").strip()
            
            # JSON 시작/끝 찾기
            start_idx = clean.find("{")
            end_idx = clean.rfind("}")
            if start_idx != -1 and end_idx != -1:
                clean = clean[start_idx:end_idx + 1]
            
            data = json.loads(clean)
            
            # 간소화된 요약 생성
            if isinstance(data, dict):
                summary = self._summarize_json(data, max_chars)
                return json.dumps(summary, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # 일반 텍스트는 잘라내기
        return text[:max_chars] + "\n... [truncated]"
    
    def _extract_summary_from_chunks(self, text: str, max_chars: int) -> str:
        """청크 연결 텍스트에서 핵심 데이터 요약 추출"""
        import re
        
        # 각 청크에서 JSON 추출
        chunk_pattern = r"=== Chunk \d+ \(\d+ images\) ===\s*([\s\S]*?)(?==== Chunk|\Z)"
        matches = re.findall(chunk_pattern, text)
        
        parsed_jsons = []
        for match in matches:
            try:
                clean = match.replace("```json", "").replace("```", "").strip()
                start_idx = clean.find("{")
                end_idx = clean.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = clean[start_idx:end_idx + 1]
                    parsed = json.loads(json_str)
                    parsed_jsons.append(parsed)
            except (json.JSONDecodeError, ValueError):
                continue
        
        if not parsed_jsons:
            return text[:max_chars] + "\n... [truncated]"
        
        # 첫 번째 청크의 district 정보 + 모든 complexes 수집
        summary = {
            "district": parsed_jsons[0].get("district", {}),
            "grades": parsed_jsons[0].get("grades", {}),
            "complexes_summary": {
                "total_extracted": sum(len(p.get("complexes", [])) for p in parsed_jsons),
                "sample": []
            }
        }
        
        # 최대 5개 단지 샘플
        for p in parsed_jsons:
            for c in p.get("complexes", [])[:2]:
                if len(summary["complexes_summary"]["sample"]) < 5:
                    summary["complexes_summary"]["sample"].append({
                        "name": c.get("name"),
                        "jeonse_rate": c.get("properties", {}).get("jeonse_rate"),
                        "is_undervalued": c.get("properties", {}).get("is_undervalued")
                    })
        
        return json.dumps(summary, ensure_ascii=False, indent=2)
    
    def _summarize_json(self, data: dict, max_chars: int) -> dict:
        """JSON 데이터 핵심만 추출"""
        result = {}
        
        # 핵심 필드 우선순위
        priority_keys = ["district", "entity_type", "name", "grades", "properties", 
                        "investment_comment", "sentiment_score", "risk_signals"]
        
        for key in priority_keys:
            if key in data:
                value = data[key]
                # 긴 문자열 필드 잘라내기
                if isinstance(value, str) and len(value) > 500:
                    value = value[:500] + "..."
                result[key] = value
        
        # complexes는 최대 5개만
        if "complexes" in data and isinstance(data["complexes"], list):
            result["complexes"] = data["complexes"][:5]
            if len(data["complexes"]) > 5:
                result["_complexes_note"] = f"Showing 5 of {len(data['complexes'])}"
        
        # 나머지 필드는 간소화
        for key, value in data.items():
            if key not in result and key not in ["complexes", "reasoning_chain"]:
                if isinstance(value, list) and len(value) > 3:
                    result[key] = value[:3]
                elif isinstance(value, dict):
                    result[key] = {k: v for k, v in list(value.items())[:5]}
                elif isinstance(value, str) and len(value) > 300:
                    result[key] = value[:300] + "..."
                else:
                    result[key] = value
        
        return result
    
    def _extract_region_name(self, facts_json: str) -> str:
        """팩트 JSON에서 지역명 추출 (청크 텍스트 포맷 지원)"""
        import re
        
        # 청크 연결 텍스트인 경우 첫 번째 청크에서 추출
        if "=== Chunk" in facts_json:
            # 첫 번째 JSON 블록에서 지역명 추출
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', facts_json)
            if name_match:
                return name_match.group(1)
            
            # parent_city도 시도
            city_match = re.search(r'"parent_city"\s*:\s*"([^"]+)"', facts_json)
            if city_match:
                return city_match.group(1)
            
            return "Unknown Region"
        
        # 일반 JSON 파싱
        try:
            clean = facts_json.replace("```json", "").replace("```", "").strip()
            
            # JSON 시작/끝 찾기
            start_idx = clean.find("{")
            end_idx = clean.rfind("}")
            if start_idx != -1 and end_idx != -1:
                clean = clean[start_idx:end_idx + 1]
            
            facts_dict = json.loads(clean)
            
            # 새 온톨로지 구조: district.name
            if "district" in facts_dict and isinstance(facts_dict["district"], dict):
                name = facts_dict["district"].get("name")
                parent = facts_dict["district"].get("parent_city", "")
                if name:
                    return f"{name}, {parent}" if parent else name
            
            # 레거시 구조 폴백
            return facts_dict.get("region_name", 
                                  facts_dict.get("complex_name", "Unknown Region"))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"Region name extraction failed: {e}")
            
            # 정규식으로 지역명 추출 시도
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', facts_json)
            if name_match:
                return name_match.group(1)
            
            return "Unknown Region"
    
    def _remove_repetition(self, text: str, min_pattern_len: int = 50) -> str:
        """인사이트 텍스트에서 반복 패턴 감지 및 제거
        
        Args:
            text: 원본 인사이트 텍스트
            min_pattern_len: 최소 반복 패턴 길이
            
        Returns:
            반복이 제거된 텍스트
        """
        import re
        
        if len(text) < min_pattern_len * 3:
            return text
        
        # 방법 1: 동일 문장 3회 이상 반복 감지
        # "→ **하지만**" 같은 패턴이 반복되는지 확인
        sentences = re.split(r'(?<=[.!?→])\s+', text)
        
        seen = {}
        first_repeat_idx = -1
        
        for i, sentence in enumerate(sentences):
            # 짧은 문장은 무시
            if len(sentence) < 20:
                continue
            
            key = sentence.strip()[:50]  # 첫 50자로 비교
            if key in seen:
                seen[key] += 1
                if seen[key] >= 3 and first_repeat_idx == -1:
                    first_repeat_idx = i - 2  # 첫 반복 위치
            else:
                seen[key] = 1
        
        if first_repeat_idx > 0:
            # 반복 시작 전까지만 유지
            truncated = ' '.join(sentences[:first_repeat_idx])
            logger.warning(f"Repetition detected and removed at position {first_repeat_idx}")
            return truncated + "\n\n> ⚠️ **경고**: 반복 패턴 감지로 인해 내용이 잘렸습니다."
        
        # 방법 2: 긴 청크 반복 감지 (100자 단위)
        chunk_size = 100
        if len(text) > chunk_size * 5:
            chunks = [text[i:i+chunk_size] for i in range(0, len(text) - chunk_size, chunk_size)]
            
            for i, chunk in enumerate(chunks):
                # 같은 청크가 3번 이상 나타나면 반복
                count = sum(1 for c in chunks[i:] if c == chunk)
                if count >= 3:
                    # 첫 번째 반복 위치까지만 유지
                    truncate_pos = i * chunk_size
                    logger.warning(f"Long repetition detected, truncating at {truncate_pos}")
                    return text[:truncate_pos] + "\n\n> ⚠️ **경고**: 반복 패턴 감지로 인해 내용이 잘렸습니다."
        
        return text
    
    def _save_result(self, report_id: str, result: dict) -> None:
        """결과 저장"""
        output_file = self.output_dir / f"{report_id}_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"  - Saved analysis to {output_file}")


def parse_args() -> argparse.Namespace:
    """커맨드라인 인자 파싱"""
    config = get_config()
    system = config.system
    
    parser = argparse.ArgumentParser(
        description="Real Estate Analysis Pipeline with Qwen3-VL"
    )
    parser.add_argument("--data_dir", type=str, default=system.data_dir)
    parser.add_argument("--output_dir", type=str, default=system.output_dir)
    parser.add_argument("--report_id", type=str, help="특정 보고서 ID만 분석")
    parser.add_argument("--api_url", type=str, default=system.api_url)
    parser.add_argument("--model", type=str, default=system.model_name)
    parser.add_argument("--api_key", type=str, default=system.api_key)
    parser.add_argument("--max_samples", type=int, default=system.max_samples)
    parser.add_argument("--enable-graph", action="store_true",
                       help="Enable FalkorDB graph ingestion")
    parser.add_argument("--falkordb-url", type=str, default="redis://localhost:6379",
                       help="FalkorDB connection URL")
    
    return parser.parse_args()


def main():
    """메인 진입점"""
    args = parse_args()
    
    # LangSmith 트레이싱 초기화
    setup_langsmith()
    
    # 컴포넌트 초기화
    loader = DataLoader(args.data_dir)
    prompt_manager = PromptManager()
    analyzer = QwenAnalyzer(
        api_key=args.api_key,
        base_url=args.api_url,
        model_name=args.model,
    )
    
    # GraphRAG 연동 (선택적)
    graph_ingester = None
    if args.enable_graph:
        if GRAPHRAG_AVAILABLE:
            try:
                from falkordb import FalkorDB
                db = FalkorDB.from_url(args.falkordb_url)
                graph = db.select_graph("real_estate")
                graph_ingester = GraphIngester(graph)
                logger.info(f"GraphRAG enabled: {args.falkordb_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to FalkorDB: {e}")
        else:
            logger.warning("GraphRAG not available (falkordb package not installed)")
    
    pipeline = AnalysisPipeline(
        analyzer=analyzer,
        prompt_manager=prompt_manager,
        output_dir=Path(args.output_dir),
        graph_ingester=graph_ingester,
    )
    
    # 보고서 목록 결정
    if args.report_id:
        report_ids = [args.report_id]
    else:
        report_ids = loader.get_report_ids()
    
    logger.info(f"Found {len(report_ids)} reports to process")
    logger.info(f"Using model: {analyzer.model_name}")
    
    # 분석 실행
    success_count = 0
    for rid in tqdm(report_ids[:args.max_samples], desc="Processing"):
        try:
            data = loader.load_report(rid)
            result = pipeline.process(data)
            if result:
                success_count += 1
        except FileNotFoundError as e:
            logger.error(f"Report not found: {e}")
    
    logger.info(f"Completed: {success_count}/{len(report_ids)} reports processed")


if __name__ == "__main__":
    main()
