"""
NL to Cypher Translator

자연어 → Cypher 변환
- LLM 기반 변환
- 프리셋 쿼리 매칭
"""

import re
from typing import Optional, List, Dict

from openai import AsyncOpenAI
from loguru import logger

from realestaterag.config import settings


# v3.0 Cypher 생성 프롬프트
CYPHER_PROMPT = """You are a Cypher query expert for a real estate knowledge graph (v3.0).

## Schema
Nodes:
- Region/District: {name}
- Neighborhood: {name, district}
- ApartmentComplex: {name, households, built_year}
- Infra: {name, category (Subway|DeptStore|School), tier (S|A|B|C)}
- MarketSnapshot: {date, sales_price, jeonse_price, jeonse_rate, gap_price}
- InvestmentAnalysis: {verdict, reasoning, confidence}

Relationships:
- (:Complex)-[:LOCATED_IN]->(:District)
- (:District)-[:ACCESS_TO {time_min}]->(:Infra)
- (:Complex)-[:HAS_SNAPSHOT]->(:MarketSnapshot)
- (:Complex)-[:HAS_ANALYSIS]->(:InvestmentAnalysis)

## Rules
1. Return ONLY Cypher query, no explanation
2. Use HAS_SNAPSHOT for price data
3. Use ACCESS_TO for facility access

## Examples
Q: 강남역 30분 이내 전세가율 60% 이상
```cypher
MATCH (d:District)-[a:ACCESS_TO]->(i:Infra {name: '강남역'})
WHERE a.time_min <= 30
MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(d)
MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
WHERE m.jeonse_rate >= 60
RETURN c.name, m.jeonse_rate, a.time_min
ORDER BY m.jeonse_rate DESC
```

Q: 은마아파트 가격 추이
```cypher
MATCH (c:ApartmentComplex {name: '은마아파트'})-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
RETURN m.date, m.sales_price, m.jeonse_price
ORDER BY m.date
```
"""


class NLToCypherTranslator:
    """자연어 → Cypher 변환기"""
    
    # 프리셋 쿼리 패턴
    PRESET_PATTERNS = {
        "facility_access": {
            "keywords": ["역", "접근", "분", "이내"],
            "template": """
MATCH (d:District)-[a:ACCESS_TO]->(i:Infra {{name: '{facility}'}})
WHERE a.time_min <= {time}
MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(d)
MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
WHERE m.jeonse_rate >= {rate}
RETURN c.name, d.name as district, m.jeonse_rate, a.time_min
ORDER BY m.jeonse_rate DESC
LIMIT 20
"""
        },
        "price_trend": {
            "keywords": ["추이", "변화", "트렌드"],
            "template": """
MATCH (c:ApartmentComplex {{name: '{complex}'}})-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
RETURN m.date, m.sales_price, m.jeonse_price, m.jeonse_rate
ORDER BY m.date
"""
        },
        "undervalued": {
            "keywords": ["저평가", "갭투자"],
            "template": """
MATCH (c:ApartmentComplex)-[:LOCATED_IN]->(d:District)
MATCH (c)-[:HAS_SNAPSHOT]->(m:MarketSnapshot)
WHERE m.jeonse_rate >= {rate}
RETURN c.name, d.name as district, m.jeonse_rate, m.gap_price
ORDER BY m.jeonse_rate DESC
LIMIT 20
"""
        },
    }
    
    def __init__(
        self,
        api_url: str = None,
        model: str = None,
    ):
        self.client = AsyncOpenAI(
            base_url=api_url or settings.llm_api_url,
            api_key=settings.llm_api_key,
            timeout=60,
        )
        self.model = model or settings.llm_model
    
    async def translate(self, question: str) -> List[str]:
        """자연어 질문을 Cypher 쿼리로 변환
        
        Returns:
            생성된 Cypher 쿼리 리스트
        """
        # 프리셋 매칭 시도
        preset = self._match_preset(question)
        if preset:
            logger.info(f"Using preset query for: {question}")
            return [preset]
        
        # LLM으로 변환
        cypher = await self._llm_translate(question)
        return [cypher] if cypher else []
    
    def _match_preset(self, question: str) -> Optional[str]:
        """프리셋 쿼리 매칭"""
        q = question.lower()
        
        # Facility access
        if any(k in q for k in self.PRESET_PATTERNS["facility_access"]["keywords"]):
            facility = self._extract_facility(question)
            time = self._extract_number(question, r"(\d+)\s*분") or 40
            rate = self._extract_number(question, r"(\d+)\s*%") or 60
            
            if facility:
                return self.PRESET_PATTERNS["facility_access"]["template"].format(
                    facility=facility, time=time, rate=rate
                )
        
        # Price trend
        if any(k in q for k in self.PRESET_PATTERNS["price_trend"]["keywords"]):
            complex_name = self._extract_complex(question)
            if complex_name:
                return self.PRESET_PATTERNS["price_trend"]["template"].format(
                    complex=complex_name
                )
        
        # Undervalued
        if any(k in q for k in self.PRESET_PATTERNS["undervalued"]["keywords"]):
            rate = self._extract_number(question, r"(\d+)\s*%") or 60
            return self.PRESET_PATTERNS["undervalued"]["template"].format(rate=rate)
        
        return None
    
    async def _llm_translate(self, question: str) -> Optional[str]:
        """LLM으로 Cypher 변환"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CYPHER_PROMPT},
                    {"role": "user", "content": f"Question: {question}\nCypher:"}
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            return self._extract_cypher(content)
            
        except Exception as e:
            logger.error(f"LLM translation failed: {e}")
            return None
    
    def _extract_cypher(self, text: str) -> str:
        """텍스트에서 Cypher 추출"""
        # 코드 블록 추출
        match = re.search(r'```(?:cypher)?\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # MATCH로 시작하는 부분
        match = re.search(r'(MATCH\s+.*)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def _extract_facility(self, text: str) -> Optional[str]:
        """시설명 추출"""
        patterns = {
            "강남역": "강남역", "판교역": "판교역", "서면역": "서면역",
            "강남": "강남역", "판교": "판교역", "서면": "서면역",
        }
        for keyword, name in patterns.items():
            if keyword in text:
                return name
        return None
    
    def _extract_complex(self, text: str) -> Optional[str]:
        """단지명 추출"""
        match = re.search(r'([가-힣]+(?:아파트|타운|빌라|맨션))', text)
        return match.group(1) if match else None
    
    def _extract_number(self, text: str, pattern: str) -> Optional[int]:
        """숫자 추출"""
        match = re.search(pattern, text)
        return int(match.group(1)) if match else None
