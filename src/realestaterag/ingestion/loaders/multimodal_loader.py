"""
Multimodal Loader

이미지 + 텍스트 멀티모달 데이터 로딩
- 파일 시스템 또는 S3에서 로드
- 이미지 전처리
- 청크 분할
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
import base64

import aiofiles
from loguru import logger

from realestaterag.core.models import Report
from realestaterag.core.exceptions import LoaderError, FileNotFoundError as NotFoundError
from realestaterag.config import settings


@dataclass
class MultimodalData:
    """멀티모달 데이터 컨테이너"""
    report_id: str
    text_content: str
    images: List[bytes]
    image_paths: List[str]
    metadata: Dict[str, Any]
    
    @property
    def has_images(self) -> bool:
        return len(self.images) > 0
    
    @property
    def image_count(self) -> int:
        return len(self.images)


class MultimodalLoader:
    """멀티모달 데이터 로더
    
    지원 형식:
    - 텍스트: .txt, .md
    - 이미지: .png, .jpg, .jpeg, .webp
    """
    
    SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
    SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    
    def __init__(
        self,
        base_path: Union[str, Path] = None,
        max_images: int = 10,
        max_text_length: int = 50000,
    ):
        self.base_path = Path(base_path or settings.data_dir)
        self.max_images = max_images
        self.max_text_length = max_text_length
    
    async def load(self, report_id: str) -> MultimodalData:
        """리포트 ID로 데이터 로드
        
        Args:
            report_id: 리포트 식별자 (디렉토리명)
            
        Returns:
            MultimodalData: 로드된 멀티모달 데이터
        """
        report_dir = self.base_path / report_id
        
        if not report_dir.exists():
            raise NotFoundError(f"Report directory not found: {report_dir}")
        
        logger.info(f"Loading multimodal data from {report_dir}")
        
        # 병렬 로드
        text_task = asyncio.create_task(self._load_text_files(report_dir))
        image_task = asyncio.create_task(self._load_images(report_dir))
        
        text_content, text_metadata = await text_task
        images, image_paths = await image_task
        
        return MultimodalData(
            report_id=report_id,
            text_content=text_content,
            images=images,
            image_paths=image_paths,
            metadata={
                "source_dir": str(report_dir),
                "text_length": len(text_content),
                "image_count": len(images),
                **text_metadata,
            }
        )
    
    async def load_from_report(self, report: Report) -> MultimodalData:
        """Report 모델에서 데이터 로드"""
        text_content = ""
        
        # 본문 로드
        if report.content_path:
            content_path = Path(report.content_path)
            if content_path.exists():
                async with aiofiles.open(content_path, "r", encoding="utf-8") as f:
                    text_content = await f.read()
        
        # 이미지 로드
        images = []
        image_paths = []
        
        for img_path_str in report.image_paths[:self.max_images]:
            img_path = Path(img_path_str)
            if img_path.exists():
                async with aiofiles.open(img_path, "rb") as f:
                    images.append(await f.read())
                    image_paths.append(str(img_path))
        
        return MultimodalData(
            report_id=report.id,
            text_content=text_content[:self.max_text_length],
            images=images,
            image_paths=image_paths,
            metadata=report.metadata,
        )
    
    async def _load_text_files(self, directory: Path) -> tuple[str, Dict]:
        """텍스트 파일 로드 및 병합"""
        text_parts = []
        metadata = {"text_files": []}
        
        for ext in self.SUPPORTED_TEXT_EXTENSIONS:
            for file_path in sorted(directory.glob(f"*{ext}")):
                try:
                    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        text_parts.append(content)
                        metadata["text_files"].append(file_path.name)
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
        
        combined = "\n\n".join(text_parts)
        return combined[:self.max_text_length], metadata
    
    async def _load_images(self, directory: Path) -> tuple[List[bytes], List[str]]:
        """이미지 파일 로드"""
        images = []
        paths = []
        
        for ext in self.SUPPORTED_IMAGE_EXTENSIONS:
            for file_path in sorted(directory.glob(f"*{ext}")):
                if len(images) >= self.max_images:
                    break
                    
                try:
                    async with aiofiles.open(file_path, "rb") as f:
                        images.append(await f.read())
                        paths.append(str(file_path))
                except Exception as e:
                    logger.warning(f"Failed to read image {file_path}: {e}")
        
        return images, paths
    
    def encode_image_base64(self, image_bytes: bytes) -> str:
        """이미지를 Base64로 인코딩"""
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def prepare_for_llm(self, data: MultimodalData) -> Dict[str, Any]:
        """LLM 입력용 데이터 준비
        
        Returns:
            Dict with 'text' and 'images' (base64 encoded)
        """
        return {
            "text": data.text_content,
            "images": [
                {
                    "data": self.encode_image_base64(img),
                    "path": path,
                }
                for img, path in zip(data.images, data.image_paths)
            ],
            "metadata": data.metadata,
        }
