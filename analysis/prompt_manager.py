"""
Prompt Manager

YAML 템플릿 기반 프롬프트 관리자
"""
import logging
from pathlib import Path
from typing import List, Dict

from langchain_core.prompts import ChatPromptTemplate

from prompts.manager import PromptManager as CorePromptManager

logger = logging.getLogger(__name__)


class PromptManager:
    """프롬프트 관리자
    
    YAML 템플릿에서 LangChain ChatPromptTemplate을 로드하고 관리
    """
    
    def __init__(self, templates_dir: str = None):
        """
        Args:
            templates_dir: 템플릿 디렉토리 (None이면 기본 경로)
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "prompts" / "templates"
        
        self._core = CorePromptManager(
            templates_dir=templates_dir,
            environment="prod",
        )
        logger.debug(f"PromptManager initialized: {templates_dir}")
    
    # ==================== 분석 프롬프트 ====================
    
    def get_fact_extraction_prompt(self) -> ChatPromptTemplate:
        """팩트 추출 프롬프트"""
        return self._core.get_prompt("fact_extraction")
    
    def get_visual_verification_prompt(self) -> ChatPromptTemplate:
        """시각적 검증 프롬프트"""
        return self._core.get_prompt("visual_verification")
    
    def get_sentiment_analysis_prompt(self) -> ChatPromptTemplate:
        """감성 분석 프롬프트"""
        return self._core.get_prompt("sentiment_analysis")
    
    def get_insight_generation_prompt(self) -> ChatPromptTemplate:
        """인사이트 생성 프롬프트"""
        return self._core.get_prompt("insight_generation")
    
    # ==================== 고급 기능 ====================
    
    @property
    def core(self) -> CorePromptManager:
        """코어 매니저 접근"""
        return self._core
    
    def get_prompt(self, name: str, version: str = "latest") -> ChatPromptTemplate:
        """프롬프트 로드"""
        return self._core.get_prompt(name, version)
    
    def list_prompts(self) -> List[str]:
        """프롬프트 목록"""
        return self._core.list_prompts()
    
    def with_few_shot(self, name: str, examples: List[Dict[str, str]]) -> ChatPromptTemplate:
        """Few-shot 예시 적용"""
        return self._core.with_few_shot(name, examples)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    pm = PromptManager()
    print("Prompts:", pm.list_prompts())
