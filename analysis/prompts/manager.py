"""
Enterprise Prompt Manager

LangChain 기반 엔터프라이즈급 프롬프트 관리 시스템의 핵심 모듈
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Callable

from langchain_core.prompts import ChatPromptTemplate

from .loaders import PromptLoader
from .templates import RealEstatePromptTemplate
from .registry import PromptRegistry


class PromptManager:
    """엔터프라이즈급 프롬프트 관리자
    
    보고서 권장사항 종합 구현:
    - 구조화된 템플릿 사용 (ChatPromptTemplate)
    - 중앙 집중식 관리 지원
    - 시맨틱 태깅 기반 버전 관리 (dev/staging/prod)
    - Few-shot 및 대화 기록 지원
    """
    
    VALID_ENVIRONMENTS = ["dev", "staging", "prod"]
    
    def __init__(self,
                 templates_dir: Union[str, Path],
                 registry_dir: Optional[Union[str, Path]] = None,
                 environment: str = "dev",
                 author: str = "system",
                 partial_variables_providers: Optional[Dict[str, Callable]] = None):
        """
        Args:
            templates_dir: YAML 템플릿 파일 디렉토리
            registry_dir: 레지스트리 데이터 디렉토리 (None이면 templates_dir/.registry)
            environment: 실행 환경 (dev/staging/prod)
            author: 커밋 작성자명
            partial_variables_providers: 동적 변수 제공 함수들
        """
        self.templates_dir = Path(templates_dir)
        self.environment = environment
        
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid environment: {environment}. Must be one of {self.VALID_ENVIRONMENTS}")
        
        # 레지스트리 디렉토리 설정
        if registry_dir is None:
            registry_dir = self.templates_dir / ".registry"
        
        # 컴포넌트 초기화
        self._loader = PromptLoader(
            templates_dir=self.templates_dir,
            partial_variables_providers=partial_variables_providers,
        )
        self._registry = PromptRegistry(
            registry_dir=registry_dir,
            author=author,
        )
        
        # 캐시
        self._cache: Dict[str, ChatPromptTemplate] = {}
    
    # ==================== 프롬프트 로딩 ====================
    
    def get_prompt(self,
                   name: str,
                   version: str = "latest",
                   use_cache: bool = True) -> ChatPromptTemplate:
        """프롬프트 로드
        
        우선순위:
        1. 해시 또는 태그로 레지스트리에서 로드
        2. 파일 시스템에서 직접 로드
        
        Args:
            name: 프롬프트 이름 (확장자 제외)
            version: "latest", 태그명(dev/staging/prod), 또는 커밋 해시
            use_cache: 캐시 사용 여부
            
        Returns:
            ChatPromptTemplate 객체
        """
        cache_key = f"{name}:{version}"
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        prompt = None
        
        # 레지스트리에서 시도
        if version == "latest":
            content = self._registry.get_latest(name)
        elif version in self.VALID_ENVIRONMENTS:
            content = self._registry.get_by_tag(name, version)
        elif len(version) >= 8:  # 해시로 간주
            content = self._registry.get_by_hash(version)
        else:
            content = None
        
        if content:
            prompt = self._loader._build_prompt_from_config(content, self.templates_dir)
        else:
            # 파일에서 직접 로드 시도
            yaml_path = self.templates_dir / f"{name}.yaml"
            json_path = self.templates_dir / f"{name}.json"
            
            if yaml_path.exists():
                prompt = self._loader.load_from_yaml(yaml_path)
            elif json_path.exists():
                prompt = self._loader.load_from_json(json_path)
            else:
                raise FileNotFoundError(f"Prompt '{name}' not found in registry or file system")
        
        if use_cache:
            self._cache[cache_key] = prompt
        
        return prompt
    
    def get_prompt_by_env(self, name: str) -> ChatPromptTemplate:
        """현재 환경에 맞는 프롬프트 로드
        
        Args:
            name: 프롬프트 이름
            
        Returns:
            현재 환경 태그에 해당하는 프롬프트
        """
        return self.get_prompt(name, version=self.environment)
    
    # ==================== 프롬프트 등록/업데이트 ====================
    
    def register_prompt(self,
                        name: str,
                        prompt: ChatPromptTemplate,
                        message: str = "Register prompt",
                        tags: Optional[List[str]] = None,
                        save_to_file: bool = True) -> str:
        """프롬프트 등록
        
        Args:
            name: 프롬프트 이름
            prompt: ChatPromptTemplate 객체
            message: 커밋 메시지
            tags: 초기 태그 목록
            save_to_file: YAML 파일로도 저장할지 여부
            
        Returns:
            커밋 해시
        """
        # 프롬프트를 설정으로 변환
        content = self._loader._prompt_to_config(prompt)
        
        # 레지스트리에 커밋
        commit_hash = self._registry.commit(
            name=name,
            content=content,
            message=message,
            tags=tags,
        )
        
        # 파일로 저장 (선택적)
        if save_to_file:
            yaml_path = self.templates_dir / f"{name}.yaml"
            self._loader.save_to_yaml(prompt, yaml_path)
        
        # 캐시 무효화
        self._invalidate_cache(name)
        
        return commit_hash
    
    def update_prompt(self,
                      name: str,
                      prompt: ChatPromptTemplate,
                      message: str = "Update prompt") -> str:
        """기존 프롬프트 업데이트
        
        Args:
            name: 프롬프트 이름
            prompt: 새 ChatPromptTemplate 객체
            message: 커밋 메시지
            
        Returns:
            새 커밋 해시
        """
        return self.register_prompt(name, prompt, message)
    
    # ==================== 태그 관리 ====================
    
    def tag_prompt(self, name: str, commit_hash: str, tag: str) -> None:
        """프롬프트에 태그 부여
        
        Args:
            name: 프롬프트 이름
            commit_hash: 커밋 해시
            tag: 태그명
        """
        self._registry.tag(name, commit_hash, tag)
        self._invalidate_cache(name)
    
    def promote_prompt(self, name: str, from_env: str, to_env: str) -> Optional[str]:
        """프롬프트 환경 승격 (예: staging -> prod)
        
        Args:
            name: 프롬프트 이름
            from_env: 소스 환경
            to_env: 대상 환경
            
        Returns:
            승격된 커밋 해시
        """
        result = self._registry.promote(name, from_env, to_env)
        self._invalidate_cache(name)
        return result
    
    def rollback_prompt(self, name: str, target: str) -> Optional[str]:
        """프롬프트 롤백
        
        Args:
            name: 프롬프트 이름
            target: 커밋 해시 또는 태그
            
        Returns:
            새 커밋 해시
        """
        content = self._registry.rollback(name, target)
        self._invalidate_cache(name)
        
        if content:
            # 새로 생성된 커밋 해시 반환
            prompt_info = self._registry.index.get("prompts", {}).get(name, {})
            return prompt_info.get("latest")
        return None
    
    # ==================== 고급 템플릿 패턴 ====================
    
    def with_few_shot(self,
                      name: str,
                      examples: List[Dict[str, str]],
                      version: str = "latest") -> ChatPromptTemplate:
        """Few-shot 예시가 적용된 프롬프트 반환
        
        Args:
            name: 프롬프트 이름
            examples: 예시 데이터 리스트
            version: 프롬프트 버전
            
        Returns:
            Few-shot이 적용된 ChatPromptTemplate
        """
        base_prompt = self.get_prompt(name, version)
        return RealEstatePromptTemplate.with_few_shot(base_prompt, examples)
    
    def with_history(self,
                     name: str,
                     history_variable: str = "chat_history",
                     version: str = "latest") -> ChatPromptTemplate:
        """대화 기록 슬롯이 추가된 프롬프트 반환
        
        Args:
            name: 프롬프트 이름
            history_variable: 대화 기록 변수명
            version: 프롬프트 버전
            
        Returns:
            대화 기록 슬롯이 추가된 ChatPromptTemplate
        """
        base_prompt = self.get_prompt(name, version)
        return RealEstatePromptTemplate.with_history(base_prompt, history_variable)
    
    # ==================== 조회 ====================
    
    def list_prompts(self) -> List[str]:
        """등록된 모든 프롬프트 이름 목록"""
        # 레지스트리 + 파일 시스템 통합
        registry_prompts = set(self._registry.list_prompts())
        
        file_prompts = set()
        for ext in ["yaml", "json"]:
            for f in self.templates_dir.glob(f"*.{ext}"):
                file_prompts.add(f.stem)
        
        return sorted(registry_prompts | file_prompts)
    
    def get_prompt_history(self, name: str) -> List[Dict[str, Any]]:
        """프롬프트 변경 이력 조회"""
        commits = self._registry.list_commits(name)
        return [
            {
                "hash": c.commit_hash,
                "version": c.version,
                "message": c.message,
                "created_at": c.created_at,
                "author": c.author,
                "tags": c.tags,
            }
            for c in commits
        ]
    
    def get_prompt_tags(self, name: str) -> Dict[str, str]:
        """프롬프트의 태그 목록 조회"""
        return self._registry.list_tags(name)
    
    # ==================== 유틸리티 ====================
    
    def _invalidate_cache(self, name: str) -> None:
        """특정 프롬프트의 캐시 무효화"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{name}:")]
        for key in keys_to_remove:
            del self._cache[key]
    
    def clear_cache(self) -> None:
        """전체 캐시 초기화"""
        self._cache.clear()
    
    def sync_from_files(self) -> Dict[str, str]:
        """파일 시스템의 프롬프트를 레지스트리에 동기화
        
        Returns:
            {프롬프트명: 커밋해시} 매핑
        """
        synced = {}
        
        for yaml_file in self.templates_dir.glob("*.yaml"):
            name = yaml_file.stem
            if name.startswith("_"):  # _로 시작하는 파일은 건너뛰기 (부분 템플릿 등)
                continue
            
            try:
                prompt = self._loader.load_from_yaml(yaml_file)
                content = self._loader._prompt_to_config(prompt)
                commit_hash = self._registry.commit(
                    name=name,
                    content=content,
                    message=f"Sync from file: {yaml_file.name}",
                    tags=[self.environment],  # 현재 환경에 태그
                )
                synced[name] = commit_hash
            except Exception as e:
                print(f"Warning: Failed to sync {name}: {e}")
        
        return synced

    # ==================== LangSmith Hub 통합 ====================
    
    def connect_langsmith(self, 
                          api_key: Optional[str] = None) -> "LangSmithHub":
        """LangSmith Hub에 연결
        
        Args:
            api_key: LangSmith API 키 (환경변수 LANGSMITH_API_KEY 사용 가능)
            
        Returns:
            LangSmithHub 인스턴스
        """
        from .langsmith_hub import LangSmithHub
        self._langsmith = LangSmithHub(api_key=api_key)
        return self._langsmith
    
    def push_to_hub(self,
                    name: str,
                    hub_identifier: str,
                    version: str = "latest",
                    description: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    is_public: bool = False) -> str:
        """로컬 프롬프트를 LangSmith Hub에 업로드
        
        Args:
            name: 로컬 프롬프트 이름
            hub_identifier: Hub 식별자 (예: "my-org/my-prompt")
            version: 로컬 버전 (태그 또는 해시)
            description: 프롬프트 설명
            tags: Hub 태그 목록
            is_public: 공개 여부
            
        Returns:
            Hub URL
            
        Example:
            >>> pm.push_to_hub("fact_extraction", "myorg/re-fact-extract", tags=["prod"])
        """
        if not hasattr(self, '_langsmith') or self._langsmith is None:
            raise RuntimeError("LangSmith에 연결되지 않았습니다. connect_langsmith()를 먼저 호출하세요.")
        
        prompt = self.get_prompt(name, version)
        url = self._langsmith.push(
            prompt_identifier=hub_identifier,
            prompt=prompt,
            description=description or f"Prompt: {name}",
            tags=tags,
            is_public=is_public,
        )
        return url
    
    def pull_from_hub(self,
                      hub_identifier: str,
                      local_name: Optional[str] = None,
                      save_to_registry: bool = True,
                      tags: Optional[List[str]] = None) -> ChatPromptTemplate:
        """LangSmith Hub에서 프롬프트 다운로드
        
        Args:
            hub_identifier: Hub 식별자 (예: "my-org/my-prompt:prod")
            local_name: 로컬 저장 이름 (기본: 식별자에서 추출)
            save_to_registry: 로컬 레지스트리에 저장할지 여부
            tags: 로컬 레지스트리 태그
            
        Returns:
            ChatPromptTemplate 객체
            
        Example:
            >>> prompt = pm.pull_from_hub("langchain-ai/rag-prompt:prod", local_name="rag")
        """
        if not hasattr(self, '_langsmith') or self._langsmith is None:
            raise RuntimeError("LangSmith에 연결되지 않았습니다. connect_langsmith()를 먼저 호출하세요.")
        
        prompt = self._langsmith.pull(hub_identifier)
        
        if save_to_registry:
            # 로컬 이름 결정
            if local_name is None:
                # "org/name:tag" -> "name"
                local_name = hub_identifier.split("/")[-1].split(":")[0]
            
            self.register_prompt(
                name=local_name,
                prompt=prompt,
                message=f"Pulled from LangSmith: {hub_identifier}",
                tags=tags or [self.environment],
            )
        
        return prompt
    
    @staticmethod
    def langsmith_available() -> bool:
        """LangSmith SDK 사용 가능 여부 확인"""
        from .langsmith_hub import LANGSMITH_AVAILABLE
        return LANGSMITH_AVAILABLE


# ==================== 호환성 함수 ====================

def create_prompt_manager(
    templates_dir: str = "analysis/prompts/templates",
    environment: str = "prod",
) -> PromptManager:
    """팩토리 함수로 PromptManager 생성
    
    Args:
        templates_dir: 템플릿 디렉토리
        environment: 실행 환경
        
    Returns:
        설정된 PromptManager 인스턴스
    """
    return PromptManager(
        templates_dir=templates_dir,
        environment=environment,
    )
