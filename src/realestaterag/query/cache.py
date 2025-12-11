"""
Query Cache

쿼리 결과 캐싱
"""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from loguru import logger

from realestaterag.config import settings


class CacheBackend(ABC):
    """캐시 백엔드 인터페이스"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Dict, ttl: int) -> bool:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass


class MemoryCache(CacheBackend):
    """인메모리 캐시"""
    
    def __init__(self):
        self._cache: Dict[str, tuple[Dict, datetime]] = {}
    
    async def get(self, key: str) -> Optional[Dict]:
        if key not in self._cache:
            return None
        
        value, expires_at = self._cache[key]
        if datetime.now() > expires_at:
            del self._cache[key]
            return None
        
        return value
    
    async def set(self, key: str, value: Dict, ttl: int) -> bool:
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = (value, expires_at)
        return True
    
    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self):
        """캐시 전체 삭제"""
        self._cache.clear()


class QueryCache:
    """쿼리 캐시 매니저"""
    
    def __init__(
        self,
        backend: CacheBackend = None,
        ttl: int = None,
        enabled: bool = None,
    ):
        self.backend = backend or MemoryCache()
        self.ttl = ttl or settings.cache_ttl
        self.enabled = enabled if enabled is not None else settings.cache_enabled
    
    async def get(self, question: str) -> Optional[Dict]:
        """캐시된 결과 조회"""
        if not self.enabled:
            return None
        
        key = self._make_key(question)
        result = await self.backend.get(key)
        
        if result:
            logger.debug(f"Cache hit: {question[:50]}...")
        
        return result
    
    async def set(self, question: str, result: Dict) -> bool:
        """결과 캐싱"""
        if not self.enabled:
            return False
        
        key = self._make_key(question)
        return await self.backend.set(key, result, self.ttl)
    
    async def invalidate(self, question: str) -> bool:
        """캐시 무효화"""
        key = self._make_key(question)
        return await self.backend.delete(key)
    
    def _make_key(self, question: str) -> str:
        """캐시 키 생성"""
        normalized = question.lower().strip()
        hash_val = hashlib.md5(normalized.encode()).hexdigest()[:16]
        return f"query:{hash_val}"
