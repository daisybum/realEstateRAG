"""
Qwen Analyzer

Qwen3-VL 기반 멀티모달 분석기
- OpenAI 호환 API 사용
- 청크 기반 처리
- 재시도 로직
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from openai import AsyncOpenAI
from loguru import logger

from realestaterag.core.exceptions import LLMError, LLMTimeoutError
from realestaterag.config import settings
from realestaterag.ingestion.loaders.multimodal_loader import MultimodalData


@dataclass
class AnalysisStageResult:
    """분석 단계 결과"""
    stage: str
    content: str
    raw_response: str
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None


class QwenAnalyzer:
    """Qwen3-VL 기반 분석기
    
    4단계 분석 파이프라인:
    1. Fact Extraction
    2. Visual Verification
    3. Sentiment Analysis
    4. Insight Generation
    """
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ):
        self.client = AsyncOpenAI(
            base_url=api_url or settings.llm_api_url,
            api_key=api_key or settings.llm_api_key,
            timeout=timeout or settings.llm_timeout,
        )
        self.model = model or settings.llm_model
        self.temperature = temperature or settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
    
    async def analyze(
        self,
        data: MultimodalData,
        stages: List[str] = None,
    ) -> Dict[str, AnalysisStageResult]:
        """전체 분석 파이프라인 실행
        
        Args:
            data: 멀티모달 입력 데이터
            stages: 실행할 단계 목록 (기본: 전체)
            
        Returns:
            단계별 결과 딕셔너리
        """
        stages = stages or ["fact_extraction", "visual_verification", "sentiment", "insight"]
        results = {}
        
        # Stage 1: Fact Extraction
        if "fact_extraction" in stages:
            results["fact_extraction"] = await self.extract_facts(data)
        
        # Stage 2: Visual Verification
        if "visual_verification" in stages and data.has_images:
            facts = results.get("fact_extraction", AnalysisStageResult("", "", ""))
            results["visual_verification"] = await self.verify_visuals(data, facts.content)
        
        # Stage 3: Sentiment Analysis
        if "sentiment" in stages:
            results["sentiment"] = await self.analyze_sentiment(data.text_content)
        
        # Stage 4: Insight Generation
        if "insight" in stages:
            results["insight"] = await self.generate_insights(results)
        
        return results
    
    async def extract_facts(self, data: MultimodalData) -> AnalysisStageResult:
        """Stage 1: 팩트 추출"""
        system_prompt = """You are a real estate investment analyst.
Extract key facts from the report in structured JSON format.

Output format:
{
  "district": {"name": "...", "city": "..."},
  "grades": {
    "jobs": {"grade": "S/A/B/C", "evidence": "..."},
    "transport": {"grade": "...", "evidence": "..."},
    "school": {"grade": "...", "evidence": "..."},
    "environment": {"grade": "...", "evidence": "..."}
  },
  "complexes": [
    {"name": "...", "sales_price": 0, "jeonse_price": 0, "jeonse_rate": 0.0}
  ]
}
Only output valid JSON."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_content(data, "Extract facts from this report:")}
        ]
        
        return await self._call_llm("fact_extraction", messages)
    
    async def verify_visuals(self, data: MultimodalData, facts: str) -> AnalysisStageResult:
        """Stage 2: 시각적 검증"""
        system_prompt = """You are verifying extracted facts against images.
Check if the facts match what you see in the images.
Output corrections or confirmations in JSON:
{
  "verified": true/false,
  "corrections": [...],
  "additional_findings": [...]
}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_content(
                data, 
                f"Verify these facts against the images:\n{facts}"
            )}
        ]
        
        return await self._call_llm("visual_verification", messages)
    
    async def analyze_sentiment(self, text: str) -> AnalysisStageResult:
        """Stage 3: 감성 분석"""
        system_prompt = """Analyze the investment sentiment of this real estate report.
Output JSON:
{
  "overall": "positive/neutral/negative",
  "confidence": 0.0-1.0,
  "factors": {
    "location": "positive/neutral/negative",
    "price": "...",
    "growth_potential": "..."
  }
}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze sentiment:\n{text[:8000]}"}
        ]
        
        return await self._call_llm("sentiment", messages)
    
    async def generate_insights(self, stage_results: Dict[str, AnalysisStageResult]) -> AnalysisStageResult:
        """Stage 4: 인사이트 생성"""
        system_prompt = """Based on the analysis, generate investment insights.
Output JSON:
{
  "summary": "...",
  "recommendations": [...],
  "risks": [...],
  "opportunities": [...]
}"""
        
        # 이전 단계 결과 요약
        context = "\n".join([
            f"[{name}]: {result.content[:2000]}"
            for name, result in stage_results.items()
            if result.success
        ])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate insights from:\n{context}"}
        ]
        
        return await self._call_llm("insight", messages)
    
    async def _call_llm(
        self,
        stage: str,
        messages: List[Dict],
        retries: int = 3,
    ) -> AnalysisStageResult:
        """LLM API 호출 (재시도 포함)"""
        for attempt in range(retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                
                content = response.choices[0].message.content
                tokens = response.usage.total_tokens if response.usage else 0
                
                return AnalysisStageResult(
                    stage=stage,
                    content=self._clean_json(content),
                    raw_response=content,
                    tokens_used=tokens,
                    success=True,
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"[{stage}] Timeout, attempt {attempt + 1}/{retries}")
                if attempt == retries - 1:
                    return AnalysisStageResult(
                        stage=stage, content="", raw_response="",
                        success=False, error="Timeout"
                    )
            except Exception as e:
                logger.error(f"[{stage}] Error: {e}")
                if attempt == retries - 1:
                    return AnalysisStageResult(
                        stage=stage, content="", raw_response="",
                        success=False, error=str(e)
                    )
                await asyncio.sleep(2 ** attempt)
        
        return AnalysisStageResult(stage=stage, content="", raw_response="", success=False)
    
    def _build_content(self, data: MultimodalData, prefix: str) -> List[Dict]:
        """멀티모달 콘텐츠 구성"""
        content = [{"type": "text", "text": f"{prefix}\n\n{data.text_content[:10000]}"}]
        
        # 이미지 추가 (최대 5장)
        import base64
        for img in data.images[:5]:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64.b64encode(img).decode()}"
                }
            })
        
        return content
    
    def _clean_json(self, text: str) -> str:
        """JSON 추출 및 정리"""
        # 코드 블록 제거
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return text.strip()
