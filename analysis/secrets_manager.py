"""
Secrets Management Module

다중 백엔드 지원 시크릿 관리자
- 환경변수 (기본)
- AWS Secrets Manager
- GCP Secret Manager
- 로컬 .env 파일
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SecretBackend(Enum):
    """시크릿 저장소 백엔드"""
    ENV = "environment"
    AWS = "aws_secrets_manager"
    GCP = "gcp_secret_manager"
    DOTENV = "dotenv_file"


@dataclass
class SecretConfig:
    """시크릿 설정"""
    backend: SecretBackend = SecretBackend.ENV
    aws_region: str = "ap-northeast-2"
    aws_secret_name: str = "realEstateAnalyzer/secrets"
    gcp_project: str = ""
    gcp_secret_name: str = "realEstateAnalyzer-secrets"
    dotenv_path: str = ".env"


class SecretsManager:
    """시크릿 관리자
    
    우선순위:
    1. 환경변수 (항상 최우선)
    2. 설정된 백엔드 (AWS/GCP/dotenv)
    3. 기본값
    
    Example:
        >>> secrets = SecretsManager()
        >>> api_key = secrets.get("LANGSMITH_API_KEY")
    """
    
    def __init__(self, config: Optional[SecretConfig] = None):
        self.config = config or SecretConfig()
        self._cache: Dict[str, str] = {}
        self._backend_loaded = False
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """시크릿 값 조회
        
        Args:
            key: 시크릿 키
            default: 기본값
            
        Returns:
            시크릿 값 또는 기본값
        """
        # 1순위: 환경변수
        if value := os.environ.get(key):
            return value
        
        # 2순위: 캐시
        if key in self._cache:
            return self._cache[key]
        
        # 3순위: 백엔드에서 로드
        if not self._backend_loaded:
            self._load_backend()
        
        return self._cache.get(key, default)
    
    def _load_backend(self) -> None:
        """백엔드에서 시크릿 로드"""
        self._backend_loaded = True
        
        try:
            if self.config.backend == SecretBackend.AWS:
                self._load_aws_secrets()
            elif self.config.backend == SecretBackend.GCP:
                self._load_gcp_secrets()
            elif self.config.backend == SecretBackend.DOTENV:
                self._load_dotenv()
        except Exception as e:
            logger.warning(f"Failed to load secrets from {self.config.backend.value}: {e}")
    
    def _load_aws_secrets(self) -> None:
        """AWS Secrets Manager에서 로드"""
        try:
            import boto3
            import json
            
            client = boto3.client(
                'secretsmanager',
                region_name=self.config.aws_region
            )
            
            response = client.get_secret_value(
                SecretId=self.config.aws_secret_name
            )
            
            secrets = json.loads(response['SecretString'])
            self._cache.update(secrets)
            logger.info(f"Loaded {len(secrets)} secrets from AWS Secrets Manager")
            
        except ImportError:
            logger.warning("boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            logger.warning(f"AWS Secrets Manager error: {e}")
    
    def _load_gcp_secrets(self) -> None:
        """GCP Secret Manager에서 로드"""
        try:
            from google.cloud import secretmanager
            import json
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.config.gcp_project}/secrets/{self.config.gcp_secret_name}/versions/latest"
            
            response = client.access_secret_version(request={"name": name})
            secrets = json.loads(response.payload.data.decode("UTF-8"))
            self._cache.update(secrets)
            logger.info(f"Loaded {len(secrets)} secrets from GCP Secret Manager")
            
        except ImportError:
            logger.warning("google-cloud-secret-manager not installed")
        except Exception as e:
            logger.warning(f"GCP Secret Manager error: {e}")
    
    def _load_dotenv(self) -> None:
        """로컬 .env 파일에서 로드"""
        env_path = Path(self.config.dotenv_path)
        
        # 여러 위치에서 .env 탐색
        search_paths = [
            env_path,
            Path.cwd() / ".env",
            Path(__file__).parent.parent.parent / ".env",  # 프로젝트 루트
        ]
        
        for path in search_paths:
            if path.exists():
                self._parse_dotenv(path)
                logger.info(f"Loaded secrets from {path}")
                return
        
        logger.debug("No .env file found")
    
    def _parse_dotenv(self, path: Path) -> None:
        """dotenv 파일 파싱"""
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        self._cache[key] = value


# 글로벌 인스턴스 (싱글톤 패턴)
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager(config: Optional[SecretConfig] = None) -> SecretsManager:
    """SecretsManager 싱글톤 인스턴스 반환"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(config)
    return _secrets_manager


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """편의 함수: 시크릿 값 조회"""
    return get_secrets_manager().get(key, default)


# LangSmith 전용 헬퍼
def get_langsmith_config() -> Dict[str, Any]:
    """LangSmith 설정 반환 (API 키가 없으면 비활성화)"""
    secrets = get_secrets_manager()
    
    api_key = secrets.get("LANGSMITH_API_KEY", "").strip()
    
    return {
        "enabled": bool(api_key),
        "api_key": api_key,
        "project": secrets.get("LANGSMITH_PROJECT", "realEstateAnalyzer"),
        "tracing": secrets.get("LANGSMITH_TRACING", "false").lower() == "true",
        "endpoint": secrets.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
    }


if __name__ == "__main__":
    # 테스트
    logging.basicConfig(level=logging.DEBUG)
    
    # 기본 테스트 (환경변수 + dotenv)
    secrets = SecretsManager(SecretConfig(backend=SecretBackend.DOTENV))
    
    print("=== Secrets Test ===")
    print(f"LANGSMITH_API_KEY: {'***' if secrets.get('LANGSMITH_API_KEY') else 'Not set'}")
    print(f"LANGSMITH_PROJECT: {secrets.get('LANGSMITH_PROJECT', 'default')}")
    
    print("\n=== LangSmith Config ===")
    config = get_langsmith_config()
    print(f"Enabled: {config['enabled']}")
    print(f"Project: {config['project']}")
