"""
Ingestion Service Dependencies
"""

from functools import lru_cache
from .config import get_settings
from ..domain.services import IngestionService
from ..infrastructure.messaging import MessageBroker
from ..infrastructure.storage import StorageClient
from ..infrastructure.llm import LLMProxyClient
from ..infrastructure.database import ReportRepository


@lru_cache()
def get_ingestion_service() -> IngestionService:
    """Factory for IngestionService"""
    settings = get_settings()
    
    return IngestionService(
        storage=StorageClient(settings.storage_service_url),
        llm=LLMProxyClient(settings.llm_proxy_url),
        repository=ReportRepository(),
        message_broker=MessageBroker(),
    )
