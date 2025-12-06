# 🎯 Enterprise Prompt Management System

> **LangChain 기반 엔터프라이즈급 프롬프트 관리 시스템**  
> 버전 관리, 시맨틱 태깅, LangSmith 통합을 지원하는 프로덕션-레디 프롬프트 인프라

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-green.svg)](https://langchain.com)
[![LangSmith](https://img.shields.io/badge/LangSmith-Ready-orange.svg)](https://smith.langchain.com)

---

## 📌 Overview

이 모듈은 LLM 애플리케이션에서 프롬프트를 **소프트웨어 아티팩트**로 취급하여 체계적으로 관리합니다.

### 핵심 설계 원칙

| 원칙 | 구현 |
|------|------|
| **프롬프트-코드 분리** | YAML 템플릿 기반 외부화 |
| **버전 불변성** | SHA-256 커밋 해시 |
| **환경별 배포** | 시맨틱 태깅 (dev/staging/prod) |
| **중앙 집중 관리** | LangSmith Hub 통합 |

---

## 🏗️ Architecture

```
prompts/
├── __init__.py           # 패키지 진입점
├── manager.py            # 통합 인터페이스 (Facade Pattern)
├── loaders.py            # 직렬화/역직렬화 (Strategy Pattern)
├── templates.py          # 고급 템플릿 패턴 (Decorator Pattern)
├── registry.py           # 로컬 버전 관리 (Repository Pattern)
├── langsmith_hub.py      # 클라우드 레지스트리 (Adapter Pattern)
└── templates/            # YAML 프롬프트 파일
    ├── base_system.yaml
    ├── fact_extraction.yaml
    └── ...
```

### Design Patterns Applied

- **Facade Pattern**: `PromptManager`가 복잡한 하위 시스템을 단순화된 인터페이스로 제공
- **Strategy Pattern**: `PromptLoader`가 YAML/JSON 형식을 런타임에 결정
- **Decorator Pattern**: `RealEstatePromptTemplate`이 기본 템플릿에 Few-shot, History 기능 추가
- **Repository Pattern**: `PromptRegistry`가 버전 관리 로직을 추상화

---

## ✨ Key Features

### 1. 구조화된 템플릿 시스템

```python
from prompts import PromptManager

pm = PromptManager(templates_dir="prompts/templates", environment="prod")

# YAML에서 자동 로드
prompt = pm.get_prompt("fact_extraction")

# 환경별 로드 (현재 환경: prod)
prompt = pm.get_prompt_by_env("insight_generation")
```

### 2. Few-Shot & 대화 기록 지원

```python
# Few-shot 예시 동적 주입
examples = [{"input": "Q1", "output": "A1"}]
prompt_with_examples = pm.with_few_shot("fact_extraction", examples)

# MessagesPlaceholder 기반 대화 기록
prompt_with_history = pm.with_history("fact_extraction")
```

### 3. 시맨틱 버전 관리

```python
# 프롬프트 등록 & 태깅
commit_hash = pm.register_prompt("new_prompt", my_template, tags=["dev"])

# 환경 승격
pm.promote_prompt("new_prompt", from_env="staging", to_env="prod")

# 롤백
pm.rollback_prompt("new_prompt", target="abc123")
```

### 4. LangSmith Hub 통합

```python
# 클라우드 연결
pm.connect_langsmith(api_key="ls-...")

# Hub에 업로드
url = pm.push_to_hub("fact_extraction", "my-org/re-analysis:prod")

# Hub에서 다운로드
prompt = pm.pull_from_hub("langchain-ai/rag-prompt", local_name="rag")
```

---

## 📁 YAML Template Schema

```yaml
_type: chat
name: fact_extraction
version: "1.0.0"
description: "지역 및 단지 데이터 추출"
tags: ["prod", "core"]

input_variables:
  - report_text

partial_variables:
  extraction_date: "{{current_date}}"  # 런타임 동적 바인딩

messages:
  - role: system
    content_ref: base_system.yaml  # 외부 파일 참조
  - role: user
    content: |
      분석 대상: {report_text}
      
metadata:
  author: "team"
  created_at: "2024-12-05"
```

---

## 🔧 Technical Highlights

### Immutable Commit Hashes

```python
# SHA-256 기반 콘텐츠 해시
hash_input = f"{name}:{content_json}:{timestamp}"
commit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
```

### Graceful Degradation

```python
# LangSmith SDK 미설치 시에도 동작
try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
```

### Backward Compatibility

기존 `prompt_manager.py`를 호환성 래퍼로 유지하여 **무중단 마이그레이션** 지원:

```python
# 기존 코드 (변경 없이 동작)
from analysis.prompt_manager import PromptManager
pm = PromptManager()
prompt = pm.get_fact_extraction_prompt()
```

---

## 🧪 Testing

```bash
# 유닛 테스트
python -m pytest analysis/prompts/tests/ -v

# 기본 테스트 (pytest 미설치 시)
python analysis/prompts/tests/test_prompts.py
```

---

## 📊 Module Dependencies

```
manager.py
    ├── loaders.py      (YAML/JSON 직렬화)
    ├── templates.py    (Few-shot, Placeholder)
    ├── registry.py     (로컬 버전 관리)
    └── langsmith_hub.py (클라우드 연동, Optional)
```

---

## 🛠️ Configuration

### 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 LANGSMITH_API_KEY 입력

# 2. Docker 실행 (자동으로 .env 로드)
cd docker/vllm-blackwell
docker-compose up -d
```

### 환경 변수 (.env.example 참조)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LANGSMITH_API_KEY` | LangSmith API 키 | - |
| `LANGSMITH_TRACING` | 트레이싱 활성화 | `false` |
| `LANGSMITH_PROJECT` | 프로젝트 이름 | `realEstateAnalyzer` |

### config.yaml 설정

```yaml
prompts:
  templates_dir: "prompts/templates"
  environment: "prod"  # dev / staging / prod

langsmith:
  enabled: false  # true로 활성화
  project: "realEstateAnalyzer"
  tracing: false
```

---

## 📈 Future Extensions

현재 핵심 기능만 활성화되어 있으며, 아래 모듈은 미래 확장을 위해 보존됨:

| 모듈 | 상태 | 용도 |
|------|------|------|
| `loaders.py` | ✅ 활성 | YAML 템플릿 로드 |
| `manager.py` | ✅ 활성 | 핵심 인터페이스 |
| `registry.py` | 🔮 준비됨 | 로컬 버전 관리 (Git-like) |
| `templates.py` | 🔮 준비됨 | Few-shot, MessagesPlaceholder |
| `langsmith_hub.py` | 🔮 준비됨 | 클라우드 레지스트리 연동 |

### 활성화 방법

```python
# Few-shot 예시 사용
pm = PromptManager(...)
prompt = pm.with_few_shot("fact_extraction", examples=[...])

# 로컬 버전 관리
commit_hash = pm.register_prompt("my_prompt", template, tags=["dev"])
pm.promote_prompt("my_prompt", from_env="dev", to_env="prod")

# LangSmith Hub 연동
pm.connect_langsmith(api_key="ls-...")
pm.push_to_hub("fact_extraction", "my-org/prompt:prod")
```

---

## 📚 References

- [LangChain Prompt Templates](https://python.langchain.com/docs/concepts/prompts)
- [LangSmith Prompt Hub](https://docs.smith.langchain.com/prompt_engineering)
- [Enterprise LLM Patterns](https://www.langchain.com/use-cases)

---

<div align="center">
  <sub>Built with ❤️ for production-grade LLM applications</sub>
</div>
