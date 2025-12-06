"""
LangChain Prompt Loader/Saver Module

YAML/JSON 기반 프롬프트 직렬화/역직렬화
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union

import yaml
from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)


class PromptLoader:
    """YAML/JSON 기반 프롬프트 로더/세이버
    
    보고서 3장 '로컬 환경에서의 프롬프트 버전 관리 및 직렬화' 구현
    """
    
    ROLE_TO_TEMPLATE = {
        "system": SystemMessagePromptTemplate,
        "human": HumanMessagePromptTemplate,
        "user": HumanMessagePromptTemplate,  # alias
        "ai": AIMessagePromptTemplate,
        "assistant": AIMessagePromptTemplate,  # alias
    }
    
    def __init__(self, 
                 templates_dir: Optional[Path] = None,
                 partial_variables_providers: Optional[Dict[str, Callable]] = None):
        """
        Args:
            templates_dir: 템플릿 파일 기본 디렉토리
            partial_variables_providers: 동적 변수 제공 함수들 (예: {"current_date": get_today})
        """
        self.templates_dir = Path(templates_dir) if templates_dir else None
        self.partial_providers = partial_variables_providers or {}
        
        # 기본 제공 함수들
        self._default_providers = {
            "current_date": lambda: datetime.now().strftime("%Y-%m-%d"),
            "current_datetime": lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.partial_providers = {**self._default_providers, **self.partial_providers}
    
    def load_from_yaml(self, path: Union[str, Path]) -> ChatPromptTemplate:
        """YAML 파일에서 ChatPromptTemplate 로드
        
        Args:
            path: YAML 파일 경로 (절대경로 또는 templates_dir 기준 상대경로)
            
        Returns:
            ChatPromptTemplate 객체
        """
        path = self._resolve_path(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return self._build_prompt_from_config(config, path.parent)
    
    def load_from_json(self, path: Union[str, Path]) -> ChatPromptTemplate:
        """JSON 파일에서 ChatPromptTemplate 로드"""
        path = self._resolve_path(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return self._build_prompt_from_config(config, path.parent)
    
    def save_to_yaml(self, 
                     prompt: ChatPromptTemplate, 
                     path: Union[str, Path],
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """ChatPromptTemplate을 YAML 파일로 저장
        
        Args:
            prompt: 저장할 프롬프트
            path: 저장 경로
            metadata: 추가 메타데이터
            
        Returns:
            저장된 파일의 콘텐츠 해시
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        config = self._prompt_to_config(prompt, metadata)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 콘텐츠 해시 반환 (버전 관리용)
        content_hash = self._compute_hash(config)
        return content_hash
    
    def save_to_json(self,
                     prompt: ChatPromptTemplate,
                     path: Union[str, Path],
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """ChatPromptTemplate을 JSON 파일로 저장"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        config = self._prompt_to_config(prompt, metadata)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return self._compute_hash(config)
    
    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """경로 해석: 절대경로 또는 templates_dir 기준 상대경로"""
        path = Path(path)
        if path.is_absolute():
            return path
        if self.templates_dir:
            return self.templates_dir / path
        return path
    
    def _build_prompt_from_config(self, 
                                   config: Dict[str, Any],
                                   base_dir: Path) -> ChatPromptTemplate:
        """설정 딕셔너리에서 ChatPromptTemplate 생성"""
        prompt_type = config.get("_type", "chat")
        
        if prompt_type != "chat":
            raise ValueError(f"Unsupported prompt type: {prompt_type}. Only 'chat' is supported.")
        
        messages = []
        for msg_config in config.get("messages", []):
            message = self._build_message(msg_config, base_dir)
            messages.append(message)
        
        prompt = ChatPromptTemplate.from_messages(messages)
        
        # Partial variables 적용
        partial_vars = self._resolve_partial_variables(config.get("partial_variables", {}))
        if partial_vars:
            prompt = prompt.partial(**partial_vars)
        
        return prompt
    
    def _build_message(self, 
                       msg_config: Dict[str, Any],
                       base_dir: Path) -> Any:
        """개별 메시지 빌드"""
        role = msg_config.get("role", "user")
        
        # MessagesPlaceholder 지원
        if role == "placeholder":
            variable_name = msg_config.get("variable_name", "chat_history")
            optional = msg_config.get("optional", True)
            return MessagesPlaceholder(variable_name=variable_name, optional=optional)
        
        # 외부 파일 참조 지원
        if "content_ref" in msg_config:
            ref_path = base_dir / msg_config["content_ref"]
            with open(ref_path, 'r', encoding='utf-8') as f:
                ref_config = yaml.safe_load(f)
            content = ref_config.get("content", "")
        else:
            content = msg_config.get("content", "")
        
        # 템플릿 포맷 결정 (f-string vs jinja2)
        template_format = msg_config.get("template_format", "f-string")
        
        # 튜플 형태로 반환 (ChatPromptTemplate.from_messages 호환)
        return (role, content)
    
    def _resolve_partial_variables(self, 
                                    partial_config: Dict[str, Any]) -> Dict[str, Any]:
        """Partial variables 해석 (동적 함수 바인딩 포함)"""
        resolved = {}
        for key, value in partial_config.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # 동적 함수 참조: "{{current_date}}"
                func_name = value[2:-2].strip()
                if func_name in self.partial_providers:
                    resolved[key] = self.partial_providers[func_name]
                else:
                    resolved[key] = value  # 함수를 찾지 못하면 문자열 그대로 사용
            else:
                resolved[key] = value
        return resolved
    
    def _prompt_to_config(self,
                          prompt: ChatPromptTemplate,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ChatPromptTemplate을 설정 딕셔너리로 변환"""
        config = {
            "_type": "chat",
            "input_variables": list(prompt.input_variables),
            "messages": [],
        }
        
        for message in prompt.messages:
            msg_config = self._message_to_config(message)
            config["messages"].append(msg_config)
        
        if metadata:
            config["metadata"] = metadata
        
        return config
    
    def _message_to_config(self, message: Any) -> Dict[str, Any]:
        """메시지 객체를 설정 딕셔너리로 변환"""
        if isinstance(message, MessagesPlaceholder):
            return {
                "role": "placeholder",
                "variable_name": message.variable_name,
                "optional": message.optional,
            }
        
        # MessagePromptTemplate 타입들
        if hasattr(message, 'prompt'):
            role = self._get_role_from_message_type(message)
            content = message.prompt.template
            return {"role": role, "content": content}
        
        # 튜플 형태 (role, content)
        if isinstance(message, tuple) and len(message) == 2:
            return {"role": message[0], "content": message[1]}
        
        return {"role": "unknown", "content": str(message)}
    
    def _get_role_from_message_type(self, message: Any) -> str:
        """메시지 타입에서 역할 추출"""
        type_name = type(message).__name__
        if "System" in type_name:
            return "system"
        elif "Human" in type_name:
            return "human"
        elif "AI" in type_name:
            return "ai"
        return "user"
    
    def _compute_hash(self, config: Dict[str, Any]) -> str:
        """설정의 콘텐츠 해시 계산"""
        content_str = json.dumps(config, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_str.encode()).hexdigest()[:12]
