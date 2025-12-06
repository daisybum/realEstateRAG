"""
Shared Configuration Module

중앙 집중식 설정 관리 - 환경변수 + YAML 통합
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class SystemConfig:
    """시스템 설정"""
    data_dir: str = "/workspace/data"
    output_dir: str = "/workspace/app/realEstateAnalyzer/analysis_results"
    api_url: str = "http://localhost:8000/v1"
    model_name: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    api_key: str = "EMPTY"
    max_samples: int = 100000


@dataclass
class PromptsConfig:
    """프롬프트 시스템 설정"""
    templates_dir: str = "prompts/templates"
    environment: str = "prod"


@dataclass 
class LangSmithConfig:
    """LangSmith 연동 설정"""
    enabled: bool = False
    api_key: Optional[str] = None
    project: str = "realEstateAnalyzer"
    tracing: bool = False


@dataclass
class AppConfig:
    """통합 애플리케이션 설정"""
    system: SystemConfig = field(default_factory=SystemConfig)
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    langsmith: LangSmithConfig = field(default_factory=LangSmithConfig)
    
    _instance: Optional["AppConfig"] = field(default=None, repr=False, init=False)
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """설정 로드 (싱글톤 패턴)
        
        우선순위: 환경변수 > YAML 파일 > 기본값
        
        Args:
            config_path: YAML 설정 파일 경로
            
        Returns:
            AppConfig 인스턴스
        """
        if cls._instance is not None:
            return cls._instance
        
        # YAML 파일 로드
        yaml_config = cls._load_yaml(config_path)
        
        # 환경변수 우선 적용
        system_cfg = cls._build_system_config(yaml_config.get("system", {}))
        prompts_cfg = cls._build_prompts_config(yaml_config.get("prompts", {}))
        langsmith_cfg = cls._build_langsmith_config(yaml_config.get("langsmith", {}))
        
        cls._instance = cls(
            system=system_cfg,
            prompts=prompts_cfg,
            langsmith=langsmith_cfg,
        )
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """싱글톤 인스턴스 리셋 (테스트용)"""
        cls._instance = None
    
    @staticmethod
    def _load_yaml(config_path: Optional[str]) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        if config_path:
            path = Path(config_path)
        else:
            # 기본 경로들 시도
            candidates = [
                Path("analysis/config.yaml"),
                Path(__file__).parent / "config.yaml",
            ]
            path = None
            for candidate in candidates:
                if candidate.exists():
                    path = candidate
                    break
        
        if path and path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    @staticmethod
    def _build_system_config(yaml_section: Dict[str, Any]) -> SystemConfig:
        """시스템 설정 빌드 (환경변수 우선)"""
        return SystemConfig(
            data_dir=os.environ.get("DATA_DIR", yaml_section.get("data_dir", "/workspace/data")),
            output_dir=os.environ.get("OUTPUT_DIR", yaml_section.get("output_dir", "/workspace/app/realEstateAnalyzer/analysis_results")),
            api_url=os.environ.get("VLLM_API_URL", yaml_section.get("api_url", "http://localhost:8000/v1")),
            model_name=os.environ.get("MODEL_NAME", yaml_section.get("model_name", "Qwen/Qwen3-VL-30B-A3B-Instruct")),
            api_key=os.environ.get("VLLM_API_KEY", yaml_section.get("api_key", "EMPTY")),
            max_samples=int(os.environ.get("MAX_SAMPLES", yaml_section.get("max_samples", 100000))),
        )
    
    @staticmethod
    def _build_prompts_config(yaml_section: Dict[str, Any]) -> PromptsConfig:
        """프롬프트 설정 빌드"""
        return PromptsConfig(
            templates_dir=yaml_section.get("templates_dir", "prompts/templates"),
            environment=os.environ.get("PROMPT_ENVIRONMENT", yaml_section.get("environment", "prod")),
        )
    
    @staticmethod
    def _build_langsmith_config(yaml_section: Dict[str, Any]) -> LangSmithConfig:
        """LangSmith 설정 빌드 (환경변수 우선)"""
        api_key = os.environ.get("LANGSMITH_API_KEY", yaml_section.get("api_key"))
        tracing_env = os.environ.get("LANGSMITH_TRACING", "").lower()
        
        return LangSmithConfig(
            enabled=yaml_section.get("enabled", False) or bool(api_key),
            api_key=api_key,
            project=os.environ.get("LANGSMITH_PROJECT", yaml_section.get("project", "realEstateAnalyzer")),
            tracing=tracing_env == "true" or yaml_section.get("tracing", False),
        )


# 편의 함수
def get_config(config_path: Optional[str] = None) -> AppConfig:
    """전역 설정 가져오기"""
    return AppConfig.load(config_path)
