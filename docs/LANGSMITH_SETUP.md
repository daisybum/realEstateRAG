# LangSmith API 키 관리 가이드

Real Estate RAG 프로젝트의 LangSmith API 키 관리 방법

## 🔐 API 키 관리 방법

### 1. .env 파일 사용 (권장 - 로컬 개발)

프로젝트는 이미 `secrets_manager.py`가 구현되어 있어 자동으로 `.env` 파일을 읽습니다.

**설정 방법**:
```bash
# 1. .env.example을 복사
cp .env.example .env

# 2. .env 파일 편집
nano .env

# 3. API 키 입력
LANGSMITH_API_KEY="lsv2_pt_your_actual_key_here"
LANGSMITH_PROJECT="realEstateAnalyzer"
LANGSMITH_TRACING="true"
```

**사용**:
```bash
# 환경변수 export 불필요 - 자동으로 .env에서 읽음
python3 scripts/sync_langsmith.py --push db_construction
```

---

### 2. 환경변수 직접 설정

`.env` 파일보다 우선순위가 높습니다.

```bash
# 현재 세션에만 적용
export LANGSMITH_API_KEY="lsv2_pt_..."
python3 scripts/sync_langsmith.py --push-all

# 영구 설정 (~/.zshrc 또는 ~/.bashrc)
echo 'export LANGSMITH_API_KEY="lsv2_pt_..."' >> ~/.zshrc
source ~/.zshrc
```

---

### 3. AWS Secrets Manager (배포 환경)

프로덕션 환경에서 권장하는 방법입니다.

**설정**:
```python
# analysis/secrets_manager.py 수정
from analysis.secrets_manager import SecretsManager, SecretConfig, SecretBackend

config = SecretConfig(
    backend=SecretBackend.AWS,
    aws_region="ap-northeast-2",
    aws_secret_name="realEstateAnalyzer/secrets"
)
secrets = SecretsManager(config)
```

**AWS 시크릿 생성**:
```bash
# AWS CLI로 시크릿 생성
aws secretsmanager create-secret \
  --name realEstateAnalyzer/secrets \
  --secret-string '{
    "LANGSMITH_API_KEY": "lsv2_pt_...",
    "LANGSMITH_PROJECT": "realEstateAnalyzer"
  }' \
  --region ap-northeast-2
```

---

### 4. GCP Secret Manager (배포 환경)

GCP를 사용하는 경우의 방법입니다.

**설정**:
```python
config = SecretConfig(
    backend=SecretBackend.GCP,
    gcp_project="your-project-id",
    gcp_secret_name="realEstateAnalyzer-secrets"
)
```

---

## ⚙️ 우선순위

`secrets_manager.py`는 다음 순서로 API 키를 찾습니다:

1. **환경변수** (`os.environ`)
2. **백엔드** (AWS/GCP/dotenv)
3. **기본값** (없음)

```python
# 자동으로 우선순위에 따라 로드
from analysis.secrets_manager import get_secret, get_langsmith_config

# 개별 값 조회
api_key = get_secret("LANGSMITH_API_KEY")

# LangSmith 전체 설정 (자동 활성화/비활성화)
config = get_langsmith_config()
if config["enabled"]:
    print(f"LangSmith enabled: {config['project']}")
```

---

## 🛡️ 보안 Best Practices

### ✅ 해야 할 것

1. **`.env` 파일은 절대 Git에 커밋하지 마세요**
   - ✅ `.gitignore`에 이미 등록되어 있음 확인됨
   
2. **`.env.example` 템플릿은 커밋하세요**
   - ✅ 방금 생성됨 - API 키 없이 구조만 표시

3. **팀원에게 API 키 공유 시 안전한 방법 사용**
   - 1Password, LastPass 등 비밀번호 관리자
   - Slack 시크릿 메시지
   - AWS Secrets Manager (배포 환경)

4. **API 키 노출 시 즉시 재발급**
   - https://smith.langchain.com/settings 에서 재발급

### ❌ 하지 말아야 할 것

- ❌ 코드에 API 키 하드코딩
- ❌ GitHub, 슬랙 공개 채널에 API 키 게시
- ❌ API 키를 파일명이나 주석에 포함

---

## 📝 현재 프로젝트 설정 상태

✅ **이미 구현된 것들**:
- `secrets_manager.py` - 다중 백엔드 시크릿 관리자
- `.gitignore` - `.env` 파일 Git 제외
- `.env.example` - 템플릿 파일
- `sync_langsmith.py` - 자동 API 키 감지

✅ **자동 통합**:
- `main_analysis.py`의 `setup_langsmith()` 함수
- `sync_langsmith.py`의 모든 함수

---

## 🚀 빠른 시작

```bash
# 1. .env 파일 생성
cp .env.example .env

# 2. API 키 입력 (https://smith.langchain.com/settings)
nano .env
# LANGSMITH_API_KEY="lsv2_pt_your_key_here"

# 3. 테스트
python3 -c "from analysis.secrets_manager import get_langsmith_config; print(get_langsmith_config())"

# 4. 프롬프트 업로드
python3 scripts/sync_langsmith.py --push db_construction
```

---

## 🔍 트러블슈팅

### "LangSmith API key not found!" 오류

```bash
# 1. .env 파일 확인
cat .env | grep LANGSMITH_API_KEY

# 2. SecretsManager 테스트
python3 -c "
from analysis.secrets_manager import get_secret
key = get_secret('LANGSMITH_API_KEY')
print('API Key:', '***' if key else 'NOT FOUND')
"

# 3. 수동으로 환경변수 설정
export LANGSMITH_API_KEY="lsv2_pt_..."
```

### API 키가 .env에 있는데도 인식 안 됨

```bash
# .env 파일 경로 확인
python3 -c "
from pathlib import Path
print('Current dir:', Path.cwd())
print('.env exists:', (Path.cwd() / '.env').exists())
"

# 또는 절대 경로로 지정
export LANGSMITH_API_KEY="lsv2_pt_..."  # 임시 해결
```

---

## 📚 참고 자료

- [LangSmith 문서](https://docs.smith.langchain.com/)
- [API 키 발급](https://smith.langchain.com/settings)
- [프로젝트 secrets_manager.py](file:///home/sanghyun/Projects/realEstateRAG/analysis/secrets_manager.py)
