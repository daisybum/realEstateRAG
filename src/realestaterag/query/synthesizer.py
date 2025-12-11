"""
Response Synthesizer

검색 결과 기반 자연어 응답 생성
"""

import json
from typing import List, Dict, Any, Tuple

from openai import AsyncOpenAI
from loguru import logger

from realestaterag.config import settings


SYNTHESIS_PROMPT = """You are a professional real estate investment analyst.
Based on the graph query results, provide analysis in Korean.

## Guidelines:
1. 데이터에 있는 정보만 언급 (할루시네이션 금지)
2. 구체적인 수치 인용
3. 투자 관점에서 분석
4. 리스크도 함께 언급

## Analysis Framework:
- 전세가율 60% 이상: 갭투자 유리
- 입지 독점성: 시설 접근성
- 공급 리스크: 향후 공급물량
"""


class ResponseSynthesizer:
    """응답 생성기"""
    
    def __init__(
        self,
        api_url: str = None,
        model: str = None,
    ):
        self.client = AsyncOpenAI(
            base_url=api_url or settings.llm_api_url,
            api_key=settings.llm_api_key,
            timeout=120,
        )
        self.model = model or settings.llm_model
    
    async def synthesize(
        self,
        question: str,
        context: List[Dict[str, Any]],
        sources: List[str] = None,
    ) -> Dict[str, Any]:
        """검색 결과 기반 응답 생성
        
        Returns:
            {answer, confidence, sources}
        """
        if not context:
            return {
                "answer": "검색 결과가 없습니다. 다른 조건으로 질문해보세요.",
                "confidence": 0.0,
                "sources": [],
            }
        
        answer, confidence = await self._generate(question, context)
        
        return {
            "answer": answer,
            "confidence": confidence,
            "sources": sources or self._extract_sources(context),
        }
    
    async def _generate(
        self,
        question: str,
        context: List[Dict],
    ) -> Tuple[str, float]:
        """LLM으로 응답 생성"""
        try:
            context_str = json.dumps(context[:20], ensure_ascii=False, indent=2)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYNTHESIS_PROMPT},
                    {"role": "user", "content": f"""
질문: {question}

그래프 검색 결과:
{context_str}

위 데이터를 바탕으로 투자 관점에서 분석해주세요.
"""}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            answer = response.choices[0].message.content
            confidence = min(len(context) / 10, 1.0)
            
            return answer, confidence
            
        except Exception as e:
            logger.error(f"Response synthesis failed: {e}")
            return f"응답 생성 중 오류가 발생했습니다: {e}", 0.0
    
    def _extract_sources(self, context: List[Dict]) -> List[str]:
        """소스 추출"""
        sources = set()
        for row in context:
            for key, value in row.items():
                if 'name' in key.lower() and value:
                    sources.add(str(value))
        return list(sources)[:10]
