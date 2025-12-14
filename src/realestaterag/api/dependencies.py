"""
API Dependencies

FastAPI 의존성 주입
"""

from typing import Generator
from functools import lru_cache

from realestaterag.config import settings, get_settings
from realestaterag.config.settings import Settings
from realestaterag.query import QueryEngine, create_query_engine
from realestaterag.ingestion import IngestionPipeline, create_pipeline


def get_settings_dependency() -> Settings:
    """설정 의존성"""
    return get_settings()


@lru_cache()
def get_query_engine() -> QueryEngine:
    """쿼리 엔진 의존성 (캐시됨)"""
    return create_query_engine()


@lru_cache()
def get_ingestion_pipeline() -> IngestionPipeline:
    """인제스천 파이프라인 의존성 (캐시됨)"""
    return create_pipeline()


# Cleanup function for testing
def reset_dependencies():
    """의존성 캐시 리셋 (테스트용)"""
    get_query_engine.cache_clear()
    get_ingestion_pipeline.cache_clear()
