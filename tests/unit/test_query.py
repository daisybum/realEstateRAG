"""
Unit Tests for Query Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from realestaterag.query.nl_to_cypher import NLToCypherTranslator
from realestaterag.query.cache import QueryCache, MemoryCache
from realestaterag.query.engine import QueryEngine


class TestNLToCypherTranslator:
    """NL to Cypher 변환 테스트"""
    
    def test_extract_facility(self):
        translator = NLToCypherTranslator()
        assert translator._extract_facility("강남역 30분") == "강남역"
        assert translator._extract_facility("판교 근처") == "판교역"
        assert translator._extract_facility("서울") is None
    
    def test_extract_complex(self):
        translator = NLToCypherTranslator()
        assert translator._extract_complex("은마아파트 가격") == "은마아파트"
        assert translator._extract_complex("래미안타운") == "래미안타운"
        assert translator._extract_complex("강남") is None
    
    def test_extract_number(self):
        translator = NLToCypherTranslator()
        assert translator._extract_number("30분 이내", r"(\d+)\s*분") == 30
        assert translator._extract_number("60% 이상", r"(\d+)\s*%") == 60
        assert translator._extract_number("없음", r"(\d+)\s*분") is None
    
    def test_match_preset_facility(self):
        translator = NLToCypherTranslator()
        query = translator._match_preset("강남역 30분 이내 접근 가능한 단지")
        assert query is not None
        assert "강남역" in query
        assert "30" in query
    
    def test_match_preset_price_trend(self):
        translator = NLToCypherTranslator()
        query = translator._match_preset("은마아파트 가격 추이")
        assert query is not None
        assert "은마아파트" in query
    
    def test_match_preset_undervalued(self):
        translator = NLToCypherTranslator()
        query = translator._match_preset("저평가 단지 60%")
        assert query is not None
        assert "60" in query
    
    def test_extract_cypher_from_code_block(self):
        translator = NLToCypherTranslator()
        text = "```cypher\nMATCH (n) RETURN n\n```"
        assert translator._extract_cypher(text) == "MATCH (n) RETURN n"
    
    def test_extract_cypher_from_plain_text(self):
        translator = NLToCypherTranslator()
        text = "Here is the query: MATCH (n) RETURN n LIMIT 10"
        assert "MATCH (n) RETURN n" in translator._extract_cypher(text)


class TestMemoryCache:
    """인메모리 캐시 테스트"""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = MemoryCache()
        await cache.set("key1", {"data": "value"}, ttl=3600)
        result = await cache.get("key1")
        assert result == {"data": "value"}
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        cache = MemoryCache()
        result = await cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete(self):
        cache = MemoryCache()
        await cache.set("key1", {"data": "value"}, ttl=3600)
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None
    
    def test_clear(self):
        cache = MemoryCache()
        cache._cache["key1"] = ({"data": "value"}, None)
        cache.clear()
        assert len(cache._cache) == 0


class TestQueryCache:
    """쿼리 캐시 테스트"""
    
    @pytest.mark.asyncio
    async def test_make_key(self):
        cache = QueryCache()
        key1 = cache._make_key("테스트 질문")
        key2 = cache._make_key("테스트 질문")
        key3 = cache._make_key("다른 질문")
        
        assert key1 == key2
        assert key1 != key3
        assert key1.startswith("query:")
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        cache = QueryCache(enabled=False)
        await cache.set("question", {"answer": "test"})
        result = await cache.get("question")
        assert result is None


class TestQueryEngine:
    """쿼리 엔진 테스트"""
    
    def test_classify_query_facility(self):
        engine = QueryEngine()
        assert engine._classify_query("강남역 30분 이내") == "facility_access"
    
    def test_classify_query_trend(self):
        engine = QueryEngine()
        assert engine._classify_query("가격 추이 분석") == "price_trend"
    
    def test_classify_query_undervalued(self):
        engine = QueryEngine()
        assert engine._classify_query("저평가 갭투자") == "undervalued"
    
    def test_classify_query_general(self):
        engine = QueryEngine()
        assert engine._classify_query("수지구 정보") == "general"
