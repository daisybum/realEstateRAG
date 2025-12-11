#!/usr/bin/env python3
"""
LangSmith Prompt Sync Utility

로컬 프롬프트를 LangSmith Hub에 동기화

Usage:
    # 모든 프롬프트 업로드
    python scripts/sync_langsmith.py --push-all
    
    # 특정 프롬프트 업로드
    python scripts/sync_langsmith.py --push db_construction
    
    # Hub에서 프롬프트 다운로드
    python scripts/sync_langsmith.py --pull daisybum/re-db-construction
"""
import argparse
import logging
import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.prompts.manager import PromptManager
from analysis.config_loader import get_config
from analysis.secrets_manager import get_langsmith_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def push_all_prompts(pm: PromptManager, config):
    """모든 로컬 프롬프트를 LangSmith Hub에 업로드"""
    
    # LangSmith 설정 확인 (secrets_manager 자동 연동)
    langsmith_config = get_langsmith_config()
    
    if not langsmith_config["enabled"]:
        logger.error("LangSmith API key not found!")
        logger.error("Please set LANGSMITH_API_KEY in one of the following:")
        logger.error("  1. Environment variable: export LANGSMITH_API_KEY='lsv2_pt_...'")
        logger.error("  2. .env file: LANGSMITH_API_KEY='lsv2_pt_...'")
        logger.error("  3. Get your key from: https://smith.langchain.com/settings")
        return
    
    logger.info(f"Using LangSmith project: {langsmith_config['project']}")
    
    # LangSmith 연결 (API 키를 os.environ에 설정하여 tenant 자동 인식)
    os.environ["LANGSMITH_API_KEY"] = langsmith_config["api_key"]
    os.environ["LANGSMITH_PROJECT"] = langsmith_config["project"]
    
    try:
        pm.connect_langsmith(api_key=langsmith_config["api_key"])
        logger.info("Connected to LangSmith Hub")
    except Exception as e:
        logger.error(f"Failed to connect to LangSmith: {e}")
        return
    
    # config.yaml에서 hub 설정 로드 (YAML 파일 직접 읽기)
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "analysis" / "config.yaml"
    with open(config_path, 'r') as f:
        yaml_config = yaml.safe_load(f)
    
    hub_config = yaml_config.get("langsmith", {}).get("hub", {})
    prompts_list = hub_config.get("prompts", [])
    
    for prompt_config in prompts_list:
        local_name = prompt_config['local_name']
        hub_name = prompt_config['name']
        description = prompt_config['description']
        tags = prompt_config['tags']
        
        # Personal account는 owner 없이 직접 prompt_identifier 사용
        logger.info(f"Pushing {local_name} -> {hub_name}")
        
        try:
            url = pm.push_to_hub(
                name=local_name,
                hub_identifier=hub_name,  # owner 제거
                version="prod",  # 현재 prod 버전 사용
                description=description,
                tags=tags,
                is_public=False,
            )
            logger.info(f"  ✓ Success: {url}")
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")


def push_single_prompt(pm: PromptManager, config, local_name: str):
    """특정 프롬프트를 LangSmith Hub에 업로드"""
    
    # LangSmith 설정 확인
    langsmith_config = get_langsmith_config()
    
    if not langsmith_config["enabled"]:
        logger.error("LangSmith API key not found!")
        return
    
    # LangSmith 연결 (API 키 명시적 전달)
    try:
        pm.connect_langsmith(api_key=langsmith_config["api_key"])
    except Exception as e:
        logger.error(f"Failed to connect to LangSmith: {e}")
        return
    
    # config.yaml에서 hub 설정 로드 (YAML 파일 직접 읽기)
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "analysis" / "config.yaml"
    with open(config_path, 'r') as f:
        yaml_config = yaml.safe_load(f)
    
    hub_config = yaml_config.get("langsmith", {}).get("hub", {})
    prompts_list = hub_config.get("prompts", [])
    
    prompt_config = None
    for p in prompts_list:
        if p['local_name'] == local_name:
            prompt_config = p
            break
    
    if not prompt_config:
        logger.error(f"Prompt '{local_name}' not found in config.yaml")
        logger.info(f"Available: {[p['local_name'] for p in prompts_list]}")
        return
    
    hub_name = prompt_config['name']
    description = prompt_config['description']
    tags = prompt_config['tags']
    
    # Personal account는 owner 없이 직접 사용
    logger.info(f"Pushing {local_name} -> {hub_name}")
    
    try:
        url = pm.push_to_hub(
            name=local_name,
            hub_identifier=hub_name,  # owner 제거
            version="prod",
            description=description,
            tags=tags,
            is_public=False,
        )
        logger.info(f"Success: {url}")
    except Exception as e:
        logger.error(f"Failed: {e}")


def pull_prompt(pm: PromptManager, hub_identifier: str, local_name: str = None):
    """LangSmith Hub에서 프롬프트 다운로드"""
    
    # LangSmith 설정 확인
    langsmith_config = get_langsmith_config()
    
    if not langsmith_config["enabled"]:
        logger.error("LangSmith API key not found!")
        return
    
    try:
        pm.connect_langsmith(api_key=langsmith_config["api_key"])
    except Exception as e:
        logger.error(f"Failed to connect to LangSmith: {e}")
        return
    
    logger.info(f"Pulling {hub_identifier}")
    
    try:
        prompt = pm.pull_from_hub(
            hub_identifier=hub_identifier,
            local_name=local_name,
            save_to_registry=True,
            tags=["prod"],
        )
        logger.info(f"Success: Saved as '{local_name or hub_identifier.split('/')[-1]}'")
    except Exception as e:
        logger.error(f"Failed: {e}")


def list_prompts(pm: PromptManager):
    """로컬 프롬프트 목록 출력"""
    prompts = pm.list_prompts()
    
    print("\n=== Local Prompts ===")
    for name in prompts:
        print(f"  - {name}")
    print()


def main():
    parser = argparse.ArgumentParser(description="LangSmith Prompt Sync Utility")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--push-all", action="store_true",
                      help="Push all prompts to LangSmith Hub")
    group.add_argument("--push", type=str, metavar="NAME",
                      help="Push specific prompt to Hub")
    group.add_argument("--pull", type=str, metavar="HUB_ID",
                      help="Pull prompt from Hub (e.g., 'owner/name:tag')")
    group.add_argument("--list", action="store_true",
                      help="List local prompts")
    
    parser.add_argument("--local-name", type=str,
                       help="Local name when pulling (default: auto)")
    
    args = parser.parse_args()
    
    # Config 및 PromptManager 초기화
    config = get_config()
    pm = PromptManager(
        templates_dir=Path(__file__).parent.parent / "analysis" / "prompts" / "templates",
        environment="prod",
        author="system",
    )
    
    # 명령 실행
    if args.push_all:
        push_all_prompts(pm, config)
    elif args.push:
        push_single_prompt(pm, config, args.push)
    elif args.pull:
        pull_prompt(pm, args.pull, args.local_name)
    elif args.list:
        list_prompts(pm)


if __name__ == "__main__":
    main()
