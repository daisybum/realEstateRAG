"""
Prompt Registry - Local Version Control

Git 기반 로컬 프롬프트 버전 관리 시스템
"""
import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict

from langchain_core.prompts import ChatPromptTemplate


@dataclass
class PromptCommit:
    """프롬프트 커밋 정보"""
    commit_hash: str
    name: str
    version: str
    created_at: str
    author: str
    message: str
    tags: List[str]
    parent_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptCommit":
        return cls(**data)


class PromptRegistry:
    """로컬 프롬프트 레지스트리
    
    보고서 5장 '고급 버전 관리 및 배포 전략' 구현
    - 시맨틱 태깅 (dev/staging/prod)
    - 불변 커밋 해시
    - 롤백 지원
    """
    
    DEFAULT_TAGS = ["dev", "staging", "prod"]
    
    def __init__(self, 
                 registry_dir: Union[str, Path],
                 author: str = "system"):
        """
        Args:
            registry_dir: 레지스트리 데이터 디렉토리
            author: 기본 작성자명
        """
        self.registry_dir = Path(registry_dir)
        self.author = author
        
        # 디렉토리 구조 생성
        self.prompts_dir = self.registry_dir / "prompts"
        self.commits_dir = self.registry_dir / "commits"
        self.tags_file = self.registry_dir / "tags.json"
        self.index_file = self.registry_dir / "index.json"
        
        self._ensure_directories()
        self._load_index()
    
    def _ensure_directories(self) -> None:
        """필요한 디렉토리 생성"""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.commits_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.tags_file.exists():
            self._save_json(self.tags_file, {})
        if not self.index_file.exists():
            self._save_json(self.index_file, {"prompts": {}})
    
    def _load_index(self) -> None:
        """인덱스 로드"""
        self.index = self._load_json(self.index_file)
        self.tags = self._load_json(self.tags_file)
    
    def commit(self,
               name: str,
               content: Dict[str, Any],
               message: str = "Update prompt",
               version: Optional[str] = None,
               tags: Optional[List[str]] = None) -> str:
        """프롬프트 커밋
        
        Args:
            name: 프롬프트 이름
            content: 프롬프트 설정 딕셔너리
            message: 커밋 메시지
            version: 시맨틱 버전 (자동 생성 가능)
            tags: 초기 태그 목록
            
        Returns:
            커밋 해시
        """
        # 커밋 해시 생성
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        timestamp = datetime.now().isoformat()
        hash_input = f"{name}:{content_str}:{timestamp}"
        commit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        
        # 이전 커밋 찾기
        parent_hash = None
        if name in self.index.get("prompts", {}):
            parent_hash = self.index["prompts"][name].get("latest")
        
        # 자동 버전 생성
        if version is None:
            version = self._auto_version(name)
        
        # 커밋 객체 생성
        commit = PromptCommit(
            commit_hash=commit_hash,
            name=name,
            version=version,
            created_at=timestamp,
            author=self.author,
            message=message,
            tags=tags or [],
            parent_hash=parent_hash,
        )
        
        # 커밋 저장
        commit_file = self.commits_dir / f"{commit_hash}.json"
        commit_data = commit.to_dict()
        commit_data["content"] = content
        self._save_json(commit_file, commit_data)
        
        # 인덱스 업데이트
        if "prompts" not in self.index:
            self.index["prompts"] = {}
        if name not in self.index["prompts"]:
            self.index["prompts"][name] = {"commits": [], "latest": None}
        
        self.index["prompts"][name]["commits"].append(commit_hash)
        self.index["prompts"][name]["latest"] = commit_hash
        self._save_json(self.index_file, self.index)
        
        # 태그 업데이트 (있는 경우)
        if tags:
            for tag in tags:
                self.tag(name, commit_hash, tag)
        
        return commit_hash
    
    def tag(self, name: str, commit_hash: str, tag: str) -> None:
        """커밋에 태그 부여
        
        Args:
            name: 프롬프트 이름
            commit_hash: 커밋 해시
            tag: 태그명 (dev/staging/prod 등)
        """
        prompt_tags_key = f"{name}"
        
        if prompt_tags_key not in self.tags:
            self.tags[prompt_tags_key] = {}
        
        self.tags[prompt_tags_key][tag] = commit_hash
        self._save_json(self.tags_file, self.tags)
    
    def get_by_tag(self, name: str, tag: str) -> Optional[Dict[str, Any]]:
        """태그로 프롬프트 조회
        
        Args:
            name: 프롬프트 이름
            tag: 태그명
            
        Returns:
            프롬프트 설정 딕셔너리 또는 None
        """
        prompt_tags = self.tags.get(name, {})
        commit_hash = prompt_tags.get(tag)
        
        if commit_hash:
            return self.get_by_hash(commit_hash)
        return None
    
    def get_by_hash(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """해시로 프롬프트 조회
        
        Args:
            commit_hash: 커밋 해시
            
        Returns:
            프롬프트 설정 딕셔너리
        """
        commit_file = self.commits_dir / f"{commit_hash}.json"
        if commit_file.exists():
            data = self._load_json(commit_file)
            return data.get("content")
        return None
    
    def get_latest(self, name: str) -> Optional[Dict[str, Any]]:
        """최신 버전 프롬프트 조회"""
        prompt_info = self.index.get("prompts", {}).get(name)
        if prompt_info and prompt_info.get("latest"):
            return self.get_by_hash(prompt_info["latest"])
        return None
    
    def get_commit_info(self, commit_hash: str) -> Optional[PromptCommit]:
        """커밋 정보 조회"""
        commit_file = self.commits_dir / f"{commit_hash}.json"
        if commit_file.exists():
            data = self._load_json(commit_file)
            content = data.pop("content", None)
            return PromptCommit.from_dict(data)
        return None
    
    def list_prompts(self) -> List[str]:
        """등록된 모든 프롬프트 이름 목록"""
        return list(self.index.get("prompts", {}).keys())
    
    def list_commits(self, name: str) -> List[PromptCommit]:
        """특정 프롬프트의 모든 커밋 목록"""
        prompt_info = self.index.get("prompts", {}).get(name, {})
        commits = []
        for commit_hash in prompt_info.get("commits", []):
            commit = self.get_commit_info(commit_hash)
            if commit:
                commits.append(commit)
        return commits
    
    def list_tags(self, name: str) -> Dict[str, str]:
        """특정 프롬프트의 태그 목록"""
        return self.tags.get(name, {})
    
    def rollback(self, name: str, target: str) -> Optional[Dict[str, Any]]:
        """특정 버전으로 롤백
        
        Args:
            name: 프롬프트 이름
            target: 커밋 해시 또는 태그
            
        Returns:
            롤백된 프롬프트 설정
        """
        # 태그인 경우 해시로 변환
        if len(target) < 12:  # 태그로 간주
            content = self.get_by_tag(name, target)
        else:
            content = self.get_by_hash(target)
        
        if content:
            # 새 커밋으로 등록 (롤백도 히스토리에 기록)
            self.commit(
                name=name,
                content=content,
                message=f"Rollback to {target}",
            )
        
        return content
    
    def promote(self, name: str, from_tag: str, to_tag: str) -> Optional[str]:
        """태그 승격 (예: staging -> prod)
        
        Args:
            name: 프롬프트 이름
            from_tag: 소스 태그
            to_tag: 대상 태그
            
        Returns:
            승격된 커밋 해시
        """
        prompt_tags = self.tags.get(name, {})
        commit_hash = prompt_tags.get(from_tag)
        
        if commit_hash:
            self.tag(name, commit_hash, to_tag)
            return commit_hash
        return None
    
    def _auto_version(self, name: str) -> str:
        """자동 시맨틱 버전 생성"""
        commits = self.list_commits(name)
        if not commits:
            return "1.0.0"
        
        # 마지막 버전에서 패치 버전 증가
        last_version = commits[-1].version
        try:
            parts = last_version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except:
            return f"1.0.{len(commits)}"
    
    def _save_json(self, path: Path, data: Dict) -> None:
        """JSON 파일 저장"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_json(self, path: Path) -> Dict:
        """JSON 파일 로드"""
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
