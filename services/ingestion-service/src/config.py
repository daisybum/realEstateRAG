"""
Ingestion Service Configuration
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Service settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
    
    # Service
    service_name: str = "ingestion-service"
    environment: str = "development"
    debug: bool = False
    
    # API
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "postgresql://admin:admin123@localhost:5432/realestaterag"
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"
    
    # External Services
    llm_proxy_url: str = "http://localhost:8003"
    storage_service_url: str = "http://localhost:8004"
    
    # Logging
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
