# LangChain 의존성 설치 가이드

## 🔧 문제 상황

`python3`가 시스템 Python을 가리켜 가상환경(`.venv`)의 패키지를 인식하지 못합니다.

```bash
which python3
# /usr/bin/python3 (시스템 버전)

# 기대값: /home/sanghyun/Projects/realEstateRAG/.venv/bin/python3
```

## ✅ 해결 방법

### 방법 1: 가상환경 Python 직접 사용 (권장)

```bash
# .venv의 Python 직접 실행
.venv/bin/python3 -m pip install langchain langchain-core langsmith

# 또는 uv 사용
.venv/bin/python3 -m uv pip install -r requirements.txt

# 테스트
.venv/bin/python3 scripts/sync_langsmith.py --list
```

### 방법 2: 가상환경 재활성화

```bash
# 현재 환경 비활성화
deactivate

# 재활성화
source .venv/bin/activate

# which python3 확인 (여전히 /usr/bin/python3인 경우 방법 3 사용)
which python3

# 설치
python3 -m pip install langchain langchain-core langsmith
```

### 방법 3: alias 설정

```bash
# ~/.zshrc 또는 ~/.bashrc에 추가
alias python='.venv/bin/python3'
alias python3='.venv/bin/python3'

# 현재 세션에서만 적용
alias python3='.venv/bin/python3'

# 설치
python3 -m pip install langchain langchain-core langsmith
```

### 방법 4: uv를 통한 설치 (이미 시도함)

```bash
uv pip install langchain langchain-core langsmith

# uv가 올바른 가상환경을 사용하지 않는 경우
UV_PYTHON=.venv/bin/python3 uv pip install -r requirements.txt
```

## 🧪 설치 확인

```bash
# langchain 설치 확인
.venv/bin/python3 -c "import langchain_core; print('✓ langchain_core installed')"

# LangSmith 스크립트 테스트
.venv/bin/python3 scripts/sync_langsmith.py --list

# API 키 인식 테스트
.venv/bin/python3 -c "from analysis.secrets_manager import get_langsmith_config; print(get_langsmith_config()['enabled'])"
```

## 📋 필요한 패키지

`requirements.txt`에 이미 포함됨:
```txt
langchain>=0.2.0
langchain-core>=0.2.0
langsmith>=0.1.0
openai>=1.0.0
python-dotenv>=1.0.0
```

## 🚀 완료 후 실행

```bash
# 프롬프트 목록 확인
.venv/bin/python3 scripts/sync_langsmith.py --list

# db_construction 프롬프트 업로드
.venv/bin/python3 scripts/sync_langsmith.py --push db_construction

# 모든 프롬프트 업로드
.venv/bin/python3 scripts/sync_langsmith.py --push-all
```
