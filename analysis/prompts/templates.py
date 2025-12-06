"""
Advanced Prompt Template Patterns

Few-shot, MessagesPlaceholder, Jinja2 조건부 렌더링 지원
"""
from typing import List, Dict, Any, Optional, Callable

from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)
from langchain_core.example_selectors.base import BaseExampleSelector


class RealEstatePromptTemplate:
    """부동산 분석 특화 템플릿 빌더
    
    보고서 2.3장 '고급 패턴: 퓨샷 템플릿 설계' 구현
    """
    
    @staticmethod
    def with_few_shot(
        base_prompt: ChatPromptTemplate,
        examples: List[Dict[str, str]],
        example_input_key: str = "input",
        example_output_key: str = "output",
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> ChatPromptTemplate:
        """Few-shot 예시를 동적으로 주입하는 템플릿 생성
        
        Args:
            base_prompt: 기본 프롬프트 템플릿
            examples: 예시 데이터 리스트 [{"input": "...", "output": "..."}, ...]
            example_input_key: 예시 입력 키
            example_output_key: 예시 출력 키
            prefix: 예시 앞에 붙을 텍스트
            suffix: 예시 뒤에 붙을 텍스트
            
        Returns:
            Few-shot이 적용된 ChatPromptTemplate
        """
        # 개별 예시를 포맷팅할 템플릿
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", f"{{{example_input_key}}}"),
            ("ai", f"{{{example_output_key}}}"),
        ])
        
        # Few-shot 템플릿 생성
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
        )
        
        # 기존 프롬프트의 메시지들 추출
        messages = list(base_prompt.messages)
        
        # 시스템 메시지 찾기
        system_messages = []
        other_messages = []
        for msg in messages:
            if hasattr(msg, 'prompt'):
                role = RealEstatePromptTemplate._get_role(msg)
                if role == "system":
                    system_messages.append(msg)
                else:
                    other_messages.append(msg)
            else:
                other_messages.append(msg)
        
        # 새 프롬프트 조합: [system] + [few-shot] + [other messages]
        final_messages = system_messages + [few_shot_prompt] + other_messages
        
        return ChatPromptTemplate.from_messages(final_messages)
    
    @staticmethod
    def with_dynamic_few_shot(
        base_prompt: ChatPromptTemplate,
        example_selector: BaseExampleSelector,
        example_input_key: str = "input",
        example_output_key: str = "output",
    ) -> ChatPromptTemplate:
        """입력과 유사한 예시만 동적 선별하는 템플릿
        
        Args:
            base_prompt: 기본 프롬프트
            example_selector: 예시 선별기 (Semantic Similarity 등)
            example_input_key: 예시 입력 키
            example_output_key: 예시 출력 키
            
        Returns:
            동적 Few-shot이 적용된 ChatPromptTemplate
        """
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", f"{{{example_input_key}}}"),
            ("ai", f"{{{example_output_key}}}"),
        ])
        
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            example_selector=example_selector,
        )
        
        messages = list(base_prompt.messages)
        system_messages = [m for m in messages if RealEstatePromptTemplate._get_role(m) == "system"]
        other_messages = [m for m in messages if RealEstatePromptTemplate._get_role(m) != "system"]
        
        final_messages = system_messages + [few_shot_prompt] + other_messages
        return ChatPromptTemplate.from_messages(final_messages)
    
    @staticmethod
    def with_history(
        prompt: ChatPromptTemplate,
        history_variable: str = "chat_history",
        optional: bool = True,
    ) -> ChatPromptTemplate:
        """MessagesPlaceholder로 대화 기록 슬롯 추가
        
        보고서 2.2.2장 구현: 가변 길이 대화 기록 관리
        
        Args:
            prompt: 기본 프롬프트
            history_variable: 대화 기록 변수명
            optional: 대화 기록이 없어도 동작할지 여부
            
        Returns:
            대화 기록 슬롯이 추가된 ChatPromptTemplate
        """
        messages = list(prompt.messages)
        
        # 시스템 메시지와 나머지 분리
        system_messages = []
        other_messages = []
        for msg in messages:
            role = RealEstatePromptTemplate._get_role(msg)
            if role == "system":
                system_messages.append(msg)
            else:
                other_messages.append(msg)
        
        # 시스템 + placeholder + 나머지
        final_messages = (
            system_messages + 
            [MessagesPlaceholder(variable_name=history_variable, optional=optional)] +
            other_messages
        )
        
        return ChatPromptTemplate.from_messages(final_messages)
    
    @staticmethod
    def with_partial(
        prompt: ChatPromptTemplate,
        **partial_variables: Any,
    ) -> ChatPromptTemplate:
        """Partial variables 적용 (커링 패턴)
        
        보고서 2.1.3장: 부분 변수 적용 기술
        
        Args:
            prompt: 기본 프롬프트
            **partial_variables: 미리 고정할 변수들 (값 또는 함수)
            
        Returns:
            부분 변수가 적용된 새 프롬프트
        """
        return prompt.partial(**partial_variables)
    
    @staticmethod
    def combine(
        *prompts: ChatPromptTemplate,
    ) -> ChatPromptTemplate:
        """여러 프롬프트의 메시지들을 결합
        
        Args:
            *prompts: 결합할 프롬프트들
            
        Returns:
            결합된 ChatPromptTemplate
        """
        all_messages = []
        for prompt in prompts:
            all_messages.extend(prompt.messages)
        
        return ChatPromptTemplate.from_messages(all_messages)
    
    @staticmethod
    def _get_role(message: Any) -> str:
        """메시지에서 역할 추출"""
        if hasattr(message, 'prompt'):
            type_name = type(message).__name__
            if "System" in type_name:
                return "system"
            elif "Human" in type_name:
                return "human"
            elif "AI" in type_name:
                return "ai"
        
        if isinstance(message, tuple) and len(message) >= 2:
            return message[0]
        
        if isinstance(message, MessagesPlaceholder):
            return "placeholder"
        
        return "unknown"


class Jinja2PromptMixin:
    """Jinja2 조건부 렌더링 지원 믹스인
    
    보고서 2.1.2장: Jinja2 포맷팅 엔진 지원
    """
    
    @staticmethod
    def create_jinja2_prompt(template: str, input_variables: List[str]) -> PromptTemplate:
        """Jinja2 형식의 PromptTemplate 생성
        
        Args:
            template: Jinja2 템플릿 문자열
            input_variables: 입력 변수 목록
            
        Returns:
            Jinja2 형식의 PromptTemplate
        """
        return PromptTemplate(
            template=template,
            input_variables=input_variables,
            template_format="jinja2",
        )
    
    @staticmethod
    def create_conditional_prompt(
        base_template: str,
        conditions: Dict[str, str],
        condition_variable: str = "mode",
    ) -> PromptTemplate:
        """조건부 렌더링이 적용된 프롬프트 생성
        
        Args:
            base_template: 기본 템플릿
            conditions: 조건-내용 매핑 {"expert": "Use technical jargon", ...}
            condition_variable: 조건 판단에 사용할 변수명
            
        Returns:
            조건부 PromptTemplate
        """
        # Jinja2 조건문 생성
        condition_blocks = []
        for idx, (condition_value, content) in enumerate(conditions.items()):
            if idx == 0:
                condition_blocks.append(f"{{% if {condition_variable} == '{condition_value}' %}}\n{content}")
            else:
                condition_blocks.append(f"{{% elif {condition_variable} == '{condition_value}' %}}\n{content}")
        condition_blocks.append("{% endif %}")
        
        conditional_section = "\n".join(condition_blocks)
        full_template = f"{base_template}\n{conditional_section}"
        
        # 모든 변수 추출
        input_vars = [condition_variable]
        # 기본 템플릿의 변수도 포함해야 함
        
        return PromptTemplate(
            template=full_template,
            input_variables=input_vars,
            template_format="jinja2",
        )
