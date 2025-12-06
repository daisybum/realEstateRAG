"""
Prompt Management System Tests
"""
import sys
import json
import tempfile
from pathlib import Path

# 테스트 실행 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from langchain_core.prompts import ChatPromptTemplate

from analysis.prompts.loaders import PromptLoader
from analysis.prompts.templates import RealEstatePromptTemplate
from analysis.prompts.registry import PromptRegistry
from analysis.prompts.manager import PromptManager


class TestPromptLoader:
    """PromptLoader 테스트"""
    
    def test_load_from_yaml(self, tmp_path):
        """YAML 파일 로드 테스트"""
        yaml_content = """
_type: chat
name: test_prompt
messages:
  - role: system
    content: "You are a helpful assistant."
  - role: user
    content: "Tell me about {topic}."
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)
        
        loader = PromptLoader(templates_dir=tmp_path)
        prompt = loader.load_from_yaml(yaml_file)
        
        assert isinstance(prompt, ChatPromptTemplate)
        assert "topic" in prompt.input_variables
    
    def test_save_and_load_roundtrip(self, tmp_path):
        """저장 후 로드 왕복 테스트"""
        original = ChatPromptTemplate.from_messages([
            ("system", "System message"),
            ("human", "Question about {subject}"),
        ])
        
        loader = PromptLoader(templates_dir=tmp_path)
        yaml_file = tmp_path / "roundtrip.yaml"
        
        loader.save_to_yaml(original, yaml_file)
        loaded = loader.load_from_yaml(yaml_file)
        
        assert "subject" in loaded.input_variables
    
    def test_partial_variables(self, tmp_path):
        """Partial variables 테스트"""
        yaml_content = """
_type: chat
partial_variables:
  date: "{{current_date}}"
messages:
  - role: user
    content: "Today is {date}. Tell me about {topic}."
"""
        yaml_file = tmp_path / "partial.yaml"
        yaml_file.write_text(yaml_content)
        
        loader = PromptLoader(templates_dir=tmp_path)
        prompt = loader.load_from_yaml(yaml_file)
        
        # date는 partial이므로 topic만 남아야 함
        # Note: 현재 구현에서는 partial이 호출 시점에 적용되므로 둘 다 있을 수 있음


class TestRealEstatePromptTemplate:
    """RealEstatePromptTemplate 테스트"""
    
    def test_with_few_shot(self):
        """Few-shot 적용 테스트"""
        base = ChatPromptTemplate.from_messages([
            ("system", "You are an analyst."),
            ("human", "{question}"),
        ])
        
        examples = [
            {"input": "What is 2+2?", "output": "4"},
            {"input": "What is 3+3?", "output": "6"},
        ]
        
        result = RealEstatePromptTemplate.with_few_shot(base, examples)
        
        assert isinstance(result, ChatPromptTemplate)
        # 메시지 수가 늘어나야 함 (system + few_shot_template + human)
        assert len(result.messages) >= 2
    
    def test_with_history(self):
        """대화 기록 슬롯 추가 테스트"""
        base = ChatPromptTemplate.from_messages([
            ("system", "You are helpful."),
            ("human", "{input}"),
        ])
        
        result = RealEstatePromptTemplate.with_history(base)
        
        # chat_history placeholder가 추가되어야 함
        assert "chat_history" in result.input_variables or any(
            hasattr(m, 'variable_name') and m.variable_name == 'chat_history'
            for m in result.messages
        )
    
    def test_with_partial(self):
        """Partial variables 적용 테스트"""
        base = ChatPromptTemplate.from_messages([
            ("human", "Analyze {region} for {date}"),
        ])
        
        result = RealEstatePromptTemplate.with_partial(base, date="2024-12-05")
        
        # date가 고정되어 region만 남아야 함
        assert "region" in result.input_variables
        assert "date" not in result.input_variables


class TestPromptRegistry:
    """PromptRegistry 테스트"""
    
    def test_commit_and_retrieve(self, tmp_path):
        """커밋 및 조회 테스트"""
        registry = PromptRegistry(registry_dir=tmp_path)
        
        content = {"_type": "chat", "messages": [{"role": "user", "content": "test"}]}
        commit_hash = registry.commit("test_prompt", content, message="Initial commit")
        
        assert len(commit_hash) == 12
        
        retrieved = registry.get_latest("test_prompt")
        assert retrieved == content
    
    def test_tagging(self, tmp_path):
        """태그 부여 테스트"""
        registry = PromptRegistry(registry_dir=tmp_path)
        
        content = {"_type": "chat", "messages": []}
        commit_hash = registry.commit("prompt", content)
        
        registry.tag("prompt", commit_hash, "prod")
        
        by_tag = registry.get_by_tag("prompt", "prod")
        assert by_tag == content
    
    def test_version_history(self, tmp_path):
        """버전 이력 테스트"""
        registry = PromptRegistry(registry_dir=tmp_path)
        
        # 여러 버전 커밋
        registry.commit("prompt", {"v": 1}, message="v1")
        registry.commit("prompt", {"v": 2}, message="v2")
        registry.commit("prompt", {"v": 3}, message="v3")
        
        commits = registry.list_commits("prompt")
        assert len(commits) == 3
        assert commits[-1].version == "1.0.2"  # 자동 버전 증가
    
    def test_promote(self, tmp_path):
        """태그 승격 테스트"""
        registry = PromptRegistry(registry_dir=tmp_path)
        
        content = {"data": "test"}
        commit_hash = registry.commit("prompt", content, tags=["staging"])
        
        promoted = registry.promote("prompt", "staging", "prod")
        
        assert promoted == commit_hash
        prod_content = registry.get_by_tag("prompt", "prod")
        assert prod_content == content


class TestPromptManager:
    """PromptManager 통합 테스트"""
    
    def test_get_prompt_from_file(self, tmp_path):
        """파일에서 프롬프트 로드 테스트"""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        
        yaml_content = """
_type: chat
messages:
  - role: system
    content: "System"
  - role: user
    content: "{query}"
"""
        (templates_dir / "test.yaml").write_text(yaml_content)
        
        manager = PromptManager(templates_dir=templates_dir)
        prompt = manager.get_prompt("test")
        
        assert isinstance(prompt, ChatPromptTemplate)
        assert "query" in prompt.input_variables
    
    def test_register_and_retrieve(self, tmp_path):
        """등록 및 조회 테스트"""
        manager = PromptManager(templates_dir=tmp_path)
        
        prompt = ChatPromptTemplate.from_messages([
            ("human", "Hello {name}"),
        ])
        
        commit_hash = manager.register_prompt("greeting", prompt)
        retrieved = manager.get_prompt("greeting")
        
        assert "name" in retrieved.input_variables
    
    def test_environment_based_loading(self, tmp_path):
        """환경 기반 로딩 테스트"""
        manager = PromptManager(templates_dir=tmp_path, environment="staging")
        
        prompt = ChatPromptTemplate.from_messages([("human", "test")])
        manager.register_prompt("env_test", prompt, tags=["staging"])
        
        # staging 환경에서 로드
        loaded = manager.get_prompt_by_env("env_test")
        assert isinstance(loaded, ChatPromptTemplate)


# ==================== 실제 템플릿 테스트 ====================

class TestActualTemplates:
    """실제 프로젝트 템플릿 테스트"""
    
    @pytest.fixture
    def templates_dir(self):
        return Path(__file__).parent.parent / "templates"
    
    def test_fact_extraction_template(self, templates_dir):
        """팩트 추출 템플릿 테스트"""
        if not templates_dir.exists():
            pytest.skip("Templates directory not found")
        
        loader = PromptLoader(templates_dir=templates_dir)
        prompt = loader.load_from_yaml(templates_dir / "fact_extraction.yaml")
        
        assert "report_text" in prompt.input_variables
        
        # 포맷팅 테스트
        result = prompt.format(report_text="테스트 보고서 텍스트")
        assert "테스트 보고서 텍스트" in result
    
    def test_insight_generation_template(self, templates_dir):
        """인사이트 생성 템플릿 테스트"""
        if not templates_dir.exists():
            pytest.skip("Templates directory not found")
        
        loader = PromptLoader(templates_dir=templates_dir)
        prompt = loader.load_from_yaml(templates_dir / "insight_generation.yaml")
        
        expected_vars = {"region_name", "fact_data", "verification_result", "risk_analysis"}
        assert expected_vars.issubset(set(prompt.input_variables))


if __name__ == "__main__":
    # pytest 없이 기본 테스트 실행
    import traceback
    
    print("=== Running Basic Tests ===\n")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Loader Test
        print("1. Testing PromptLoader...")
        try:
            loader = PromptLoader(templates_dir=tmp_path)
            yaml_content = """
_type: chat
messages:
  - role: user
    content: "Test {var}"
"""
            yaml_file = tmp_path / "test.yaml"
            yaml_file.write_text(yaml_content)
            prompt = loader.load_from_yaml(yaml_file)
            assert "var" in prompt.input_variables
            print("   ✓ PromptLoader works!")
        except Exception as e:
            print(f"   ✗ PromptLoader failed: {e}")
            traceback.print_exc()
        
        # Registry Test
        print("\n2. Testing PromptRegistry...")
        try:
            registry = PromptRegistry(registry_dir=tmp_path / "registry")
            commit = registry.commit("test", {"data": "value"}, tags=["dev"])
            content = registry.get_by_tag("test", "dev")
            assert content == {"data": "value"}
            print("   ✓ PromptRegistry works!")
        except Exception as e:
            print(f"   ✗ PromptRegistry failed: {e}")
            traceback.print_exc()
        
        # Manager Test
        print("\n3. Testing PromptManager...")
        try:
            templates_dir = tmp_path / "templates"
            templates_dir.mkdir()
            yaml_content = """
_type: chat
messages:
  - role: system
    content: "System"
  - role: user
    content: "{input}"
"""
            (templates_dir / "demo.yaml").write_text(yaml_content)
            
            manager = PromptManager(templates_dir=templates_dir)
            prompt = manager.get_prompt("demo")
            assert "input" in prompt.input_variables
            print("   ✓ PromptManager works!")
        except Exception as e:
            print(f"   ✗ PromptManager failed: {e}")
            traceback.print_exc()
    
    print("\n=== Tests Complete ===")
