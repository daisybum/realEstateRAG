"""
LangSmith Hub Integration

중앙 집중형 프롬프트 레지스트리 연동 - 클라우드 기반 버전 관리
"""
import os
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

# LangSmith SDK (선택적 의존성)
try:
    from langsmith import Client as LangSmithClient
    LANGSMITH_AVAILABLE = True
except ImportError:
    LangSmithClient = None
    LANGSMITH_AVAILABLE = False


class LangSmithHub:
    """LangSmith 기반 프롬프트 허브
    
    보고서 4장 '엔터프라이즈급 생명주기 관리: LangSmith 및 LangChain Hub' 구현
    
    Features:
        - 프롬프트 Push/Pull (중앙 레지스트리)
        - 커밋 해시 기반 불변성 보장
        - 태그 기반 배포 전략 (dev/staging/prod)
        - 모델 설정 포함 저장 (RunnableSequence)
    
    Example:
        ```python
        hub = LangSmithHub(api_key="ls-...")
        
        # 업로드
        url = hub.push("my-org/my-prompt", prompt, tags=["prod"])
        
        # 다운로드 (태그 기반)
        prompt = hub.pull("my-org/my-prompt:prod")
        ```
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 api_url: Optional[str] = None):
        """
        Args:
            api_key: LangSmith API 키 (환경변수 LANGSMITH_API_KEY 사용 가능)
            api_url: LangSmith API URL (기본값: https://api.smith.langchain.com)
        
        Raises:
            ImportError: langsmith 패키지가 설치되지 않은 경우
        """
        if not LANGSMITH_AVAILABLE:
            raise ImportError(
                "LangSmith SDK가 설치되지 않았습니다. "
                "설치: pip install langsmith"
            )
        
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        self.api_url = api_url or os.environ.get(
            "LANGSMITH_ENDPOINT", 
            "https://api.smith.langchain.com"
        )
        
        if not self.api_key:
            raise ValueError(
                "LangSmith API 키가 필요합니다. "
                "환경변수 LANGSMITH_API_KEY를 설정하거나 api_key 인자를 전달하세요."
            )
        
        self._client = LangSmithClient(
            api_key=self.api_key,
            api_url=self.api_url,
        )
    
    # ==================== Push/Pull ====================
    
    def push(self,
             prompt_identifier: str,
             prompt: ChatPromptTemplate,
             description: Optional[str] = None,
             readme: Optional[str] = None,
             tags: Optional[List[str]] = None,
             is_public: bool = False,
             parent_commit_hash: str = "latest") -> str:
        """프롬프트를 LangSmith에 업로드
        
        Args:
            prompt_identifier: 프롬프트 식별자 (예: "my-org/my-prompt")
            prompt: 업로드할 ChatPromptTemplate
            description: 프롬프트 설명
            readme: README 내용 (Markdown)
            tags: 태그 목록 (예: ["prod", "v1.0"])
            is_public: 공개 여부
            parent_commit_hash: 부모 커밋 해시 (기본: "latest")
            
        Returns:
            업로드된 프롬프트의 URL
        """
        url = self._client.push_prompt(
            prompt_identifier=prompt_identifier,
            object=prompt,
            description=description,
            readme=readme,
            tags=tags,
            is_public=is_public,
            parent_commit_hash=parent_commit_hash,
        )
        return url
    
    def pull(self,
             prompt_identifier: str,
             include_model: bool = False) -> ChatPromptTemplate:
        """LangSmith에서 프롬프트 다운로드
        
        Args:
            prompt_identifier: 프롬프트 식별자
                - "my-org/my-prompt" - 최신 버전
                - "my-org/my-prompt:prod" - prod 태그
                - "my-org/my-prompt:abc123" - 특정 커밋
            include_model: 모델 정보 포함 여부
            
        Returns:
            ChatPromptTemplate 객체
        """
        prompt = self._client.pull_prompt(
            prompt_identifier=prompt_identifier,
            include_model=include_model,
        )
        return prompt
    
    def pull_commit(self, 
                    prompt_identifier: str,
                    include_model: bool = False) -> Dict[str, Any]:
        """프롬프트 커밋 정보와 함께 다운로드
        
        Args:
            prompt_identifier: 프롬프트 식별자
            include_model: 모델 정보 포함 여부
            
        Returns:
            PromptCommit 객체 (커밋 해시, 태그, 메타데이터 포함)
        """
        commit = self._client.pull_prompt_commit(
            prompt_identifier=prompt_identifier,
            include_model=include_model,
        )
        return commit
    
    # ==================== 태그 관리 ====================
    
    def update_tags(self,
                    prompt_identifier: str,
                    tags: List[str]) -> None:
        """프롬프트 태그 업데이트
        
        Args:
            prompt_identifier: 프롬프트 식별자
            tags: 새 태그 목록
        """
        # push_prompt로 메타데이터만 업데이트
        self._client.push_prompt(
            prompt_identifier=prompt_identifier,
            tags=tags,
        )
    
    def promote(self,
                prompt_identifier: str,
                from_tag: str,
                to_tag: str) -> str:
        """태그 승격 (예: staging -> prod)
        
        특정 태그의 커밋을 다른 태그로 승격합니다.
        
        Args:
            prompt_identifier: 프롬프트 기본 식별자 (태그 제외)
            from_tag: 소스 태그
            to_tag: 대상 태그
            
        Returns:
            승격된 프롬프트의 URL
        """
        # 소스 태그의 프롬프트 가져오기
        source_id = f"{prompt_identifier}:{from_tag}"
        prompt = self.pull(source_id)
        
        # 새 태그로 푸시
        url = self.push(
            prompt_identifier=prompt_identifier,
            prompt=prompt,
            tags=[to_tag],
            description=f"Promoted from {from_tag} to {to_tag}",
        )
        return url
    
    # ==================== 조회 ====================
    
    def list_prompts(self, 
                     limit: int = 100,
                     is_public: Optional[bool] = None) -> List[Dict[str, Any]]:
        """사용 가능한 프롬프트 목록 조회
        
        Args:
            limit: 최대 결과 수
            is_public: 공개 프롬프트만 조회할지 여부
            
        Returns:
            프롬프트 정보 리스트
        """
        prompts = self._client.list_prompts(
            limit=limit,
            is_public=is_public,
        )
        return list(prompts)
    
    def get_prompt_info(self, prompt_identifier: str) -> Dict[str, Any]:
        """프롬프트 메타데이터 조회
        
        Args:
            prompt_identifier: 프롬프트 식별자
            
        Returns:
            프롬프트 메타데이터 (이름, 설명, 태그, 커밋 이력 등)
        """
        commit = self.pull_commit(prompt_identifier)
        return {
            "identifier": prompt_identifier,
            "commit_hash": getattr(commit, 'commit_hash', None),
            "tags": getattr(commit, 'tags', []),
            "description": getattr(commit, 'description', ''),
            "created_at": getattr(commit, 'created_at', None),
        }
    
    # ==================== 유틸리티 ====================
    
    @staticmethod
    def is_available() -> bool:
        """LangSmith SDK 사용 가능 여부 확인"""
        return LANGSMITH_AVAILABLE
    
    @staticmethod
    def setup_tracing(project_name: Optional[str] = None) -> None:
        """LangSmith 트레이싱 활성화
        
        Args:
            project_name: 프로젝트 이름 (기본값: 환경변수 LANGSMITH_PROJECT)
        """
        os.environ["LANGSMITH_TRACING"] = "true"
        if project_name:
            os.environ["LANGSMITH_PROJECT"] = project_name


class LangSmithHubError(Exception):
    """LangSmith Hub 관련 오류"""
    pass


# ==================== 통합 인터페이스 ====================

def create_langsmith_hub(
    api_key: Optional[str] = None,
    raise_on_unavailable: bool = False,
) -> Optional[LangSmithHub]:
    """LangSmith Hub 팩토리 함수
    
    Args:
        api_key: LangSmith API 키
        raise_on_unavailable: SDK 미설치 시 예외 발생 여부
        
    Returns:
        LangSmithHub 인스턴스 또는 None
    """
    if not LANGSMITH_AVAILABLE:
        if raise_on_unavailable:
            raise ImportError("langsmith package not installed")
        return None
    
    try:
        return LangSmithHub(api_key=api_key)
    except ValueError as e:
        if raise_on_unavailable:
            raise
        return None
