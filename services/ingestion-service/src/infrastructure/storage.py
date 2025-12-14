"""
Storage Service Client
"""

from typing import List, Dict, Any
from loguru import logger
import httpx


class StorageClient:
    """Client for Storage Service"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def upload_files(
        self,
        report_id: str,
        files: List
    ) -> List[str]:
        """Upload files to storage service"""
        file_urls = []
        
        if not files:
            return file_urls
        
        try:
            async with httpx.AsyncClient() as client:
                for file in files:
                    content = await file.read()
                    response = await client.post(
                        f"{self.base_url}/api/v1/storage/upload",
                        files={"file": (file.filename, content)},
                        data={"report_id": report_id}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        file_urls.append(result.get("url", ""))
        except Exception as e:
            logger.warning(f"Storage upload failed: {e}")
        
        return file_urls
    
    async def download_file(self, file_url: str) -> bytes:
        """Download file from storage"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url)
                return response.content
        except Exception as e:
            logger.error(f"Storage download failed: {e}")
            return b""
