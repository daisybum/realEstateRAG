"""
Ingestion Pipeline

멀티모달 분석 파이프라인 오케스트레이션
- 로더 → 분석기 → 결과
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from loguru import logger

from realestaterag.core.models import AnalysisResult
from realestaterag.core.exceptions import IngestionError
from realestaterag.ingestion.loaders.multimodal_loader import MultimodalLoader, MultimodalData
from realestaterag.ingestion.analyzers.qwen_analyzer import QwenAnalyzer


class IngestionPipeline:
    """분석 파이프라인 오케스트레이터"""
    
    def __init__(
        self,
        loader: MultimodalLoader = None,
        analyzer: QwenAnalyzer = None,
    ):
        self.loader = loader or MultimodalLoader()
        self.analyzer = analyzer or QwenAnalyzer()
    
    async def process_report(self, report_id: str) -> AnalysisResult:
        """단일 리포트 처리
        
        Args:
            report_id: 리포트 식별자
            
        Returns:
            AnalysisResult: 분석 결과
        """
        start_time = datetime.now()
        stages_completed = []
        
        try:
            # Stage 1: Load data
            logger.info(f"[{report_id}] Loading multimodal data...")
            data = await self.loader.load(report_id)
            stages_completed.append("load")
            
            # Stage 2-5: Analyze
            logger.info(f"[{report_id}] Running analysis pipeline...")
            results = await self.analyzer.analyze(data)
            
            # 결과 수집
            facts = self._extract_json(results.get("fact_extraction"))
            entities = []
            relationships = []
            
            if facts:
                entities = self._extract_entities(facts)
                relationships = self._extract_relationships(facts)
            
            for stage, result in results.items():
                if result.success:
                    stages_completed.append(stage)
            
            # 처리 시간 계산
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return AnalysisResult(
                report_id=report_id,
                facts=[str(facts)] if facts else [],
                entities=entities,
                relationships=relationships,
                sentiments=self._extract_json(results.get("sentiment")) or {},
                insights=self._extract_list(results.get("insight"), "recommendations"),
                confidence_score=self._calculate_confidence(results),
                processing_time=processing_time,
                stages_completed=stages_completed,
            )
            
        except Exception as e:
            logger.error(f"[{report_id}] Pipeline failed: {e}")
            raise IngestionError(f"Pipeline failed for {report_id}: {e}")
    
    async def batch_process(
        self,
        report_ids: List[str],
        max_concurrent: int = 5,
    ) -> List[AnalysisResult]:
        """배치 처리
        
        Args:
            report_ids: 리포트 ID 목록
            max_concurrent: 최대 동시 처리 수
            
        Returns:
            분석 결과 목록
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_process(report_id: str) -> Optional[AnalysisResult]:
            async with semaphore:
                try:
                    return await self.process_report(report_id)
                except Exception as e:
                    logger.error(f"Failed to process {report_id}: {e}")
                    return None
        
        tasks = [bounded_process(rid) for rid in report_ids]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]
    
    def _extract_json(self, result) -> Optional[Dict]:
        """결과에서 JSON 추출"""
        if not result or not result.success:
            return None
        
        try:
            import json
            return json.loads(result.content)
        except:
            return None
    
    def _extract_entities(self, facts: Dict) -> List[Dict[str, Any]]:
        """팩트에서 엔티티 추출"""
        entities = []
        
        # District 추출
        if "district" in facts:
            district = facts["district"]
            entities.append({
                "id": f"DISTRICT_{district.get('name', 'UNKNOWN')}",
                "type": "District",
                "name": district.get("name"),
                "properties": district,
            })
        
        # Complex 추출
        for complex_data in facts.get("complexes", []):
            if "name" in complex_data:
                entities.append({
                    "id": f"COMPLEX_{complex_data['name']}",
                    "type": "Complex",
                    "name": complex_data["name"],
                    "properties": complex_data,
                })
        
        return entities
    
    def _extract_relationships(self, facts: Dict) -> List[Dict[str, Any]]:
        """팩트에서 관계 추출"""
        relationships = []
        
        district_name = facts.get("district", {}).get("name")
        if not district_name:
            return relationships
        
        # Complex → District 관계
        for complex_data in facts.get("complexes", []):
            if "name" in complex_data:
                relationships.append({
                    "source": f"COMPLEX_{complex_data['name']}",
                    "target": f"DISTRICT_{district_name}",
                    "type": "LOCATED_IN",
                    "properties": {},
                })
        
        return relationships
    
    def _extract_list(self, result, key: str) -> List[str]:
        """결과에서 리스트 추출"""
        data = self._extract_json(result)
        if data and key in data:
            return data[key]
        return []
    
    def _calculate_confidence(self, results: Dict) -> float:
        """신뢰도 계산"""
        successful = sum(1 for r in results.values() if r.success)
        total = len(results)
        return successful / total if total > 0 else 0.0


# Factory function
def create_pipeline() -> IngestionPipeline:
    """파이프라인 생성 팩토리"""
    return IngestionPipeline(
        loader=MultimodalLoader(),
        analyzer=QwenAnalyzer(),
    )
