"""
Application Settings using Pydantic Settings

환경변수 기반 설정 관리:
- .env 파일 지원
- 타입 안전성
- 기본값 관리
- 환경별 설정
"""

from typing import Optional, List
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # ============================================================
    # Application
    # ============================================================
    app_name: str = "RealEstateRAG"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # ============================================================
    # API Server
    # ============================================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = True
    
    # ============================================================
    # LLM Configuration
    # ============================================================
    llm_api_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout: int = 300  # seconds
    llm_max_retries: int = 3
    
    # ============================================================
    # FalkorDB Configuration
    # ============================================================
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: Optional[str] = None
    falkordb_graph_name: str = "wolbu_v3"
    falkordb_pool_size: int = 10
    
    @property
    def falkordb_url(self) -> str:
        """FalkorDB Redis URL"""
        if self.falkordb_password:
            return f"redis://:{self.falkordb_password}@{self.falkordb_host}:{self.falkordb_port}"
        return f"redis://{self.falkordb_host}:{self.falkordb_port}"
    
    # ============================================================
    # Storage Configuration
    # ============================================================
    data_dir: str = "/workspace/data"
    output_dir: str = "./output"
    storage_backend: str = "local"  # local, s3
    
    # S3 Configuration (when storage_backend = s3)
    s3_bucket: Optional[str] = None
    s3_region: str = "ap-northeast-2"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    
    # ============================================================
    # Monitoring & Observability
    # ============================================================
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = False
    tracing_endpoint: Optional[str] = None
    
    # LangSmith 설정
    langsmith_tracing: bool = False
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "realestaterag"
    
    # ============================================================
    # Security
    # ============================================================
    api_key_header: str = "X-API-Key"
    allowed_origins: List[str] = ["*"]
    
    # ============================================================
    # Cache Configuration
    # ============================================================
    cache_enabled: bool = True
    cache_ttl: int = 3600  # seconds
    cache_backend: str = "memory"  # memory, redis
    
    # ============================================================
    # Rate Limiting
    # ============================================================
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds


class DevelopmentSettings(Settings):
    """Development environment settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env.development",
    )
    
    environment: str = "development"
    debug: bool = True
    api_reload: bool = True
    log_level: str = "DEBUG"


class StagingSettings(Settings):
    """Staging environment settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env.staging",
    )
    
    environment: str = "staging"
    debug: bool = False
    api_reload: bool = False
    enable_tracing: bool = True


class ProductionSettings(Settings):
    """Production environment settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env.production",
    )
    
    environment: str = "production"
    debug: bool = False
    api_reload: bool = False
    api_workers: int = 8
    enable_metrics: bool = True
    enable_tracing: bool = True
    rate_limit_enabled: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance based on environment
    
    Returns:
        Settings: Application settings
    """
    import os
    env = os.environ.get("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "staging":
        return StagingSettings()
    else:
        return DevelopmentSettings()


# Convenience alias
settings = get_settings()
