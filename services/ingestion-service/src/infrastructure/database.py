"""
Database Client and Repository
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


class Database:
    """PostgreSQL database client"""
    
    _pool = None
    
    @classmethod
    async def connect(cls, url: str):
        """Establish connection pool"""
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not installed, database disabled")
            return
        
        try:
            cls._pool = await asyncpg.create_pool(url)
            logger.info("Database pool created")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
    
    @classmethod
    async def disconnect(cls):
        """Close connection pool"""
        if cls._pool:
            await cls._pool.close()
            logger.info("Database pool closed")
    
    @classmethod
    async def ping(cls) -> bool:
        """Check connection health"""
        if not ASYNCPG_AVAILABLE or not cls._pool:
            return True  # Skip if not available
        try:
            async with cls._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except:
            return False


class ReportRepository:
    """Repository for report data"""
    
    # In-memory storage for development
    _reports: Dict[str, Dict] = {}
    _statuses: Dict[str, Dict] = {}
    
    async def create_report(
        self,
        report_id: str,
        metadata: Dict[str, Any],
        file_urls: List[str]
    ):
        """Create a new report record"""
        self._reports[report_id] = {
            "id": report_id,
            "metadata": metadata,
            "file_urls": file_urls,
            "created_at": datetime.now().isoformat(),
        }
        self._statuses[report_id] = {
            "report_id": report_id,
            "status": "created",
            "progress": 0.0,
            "stages_completed": [],
            "current_stage": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    async def get_report(self, report_id: str) -> Optional[Dict]:
        """Get report by ID"""
        return self._reports.get(report_id)
    
    async def update_status(
        self,
        report_id: str,
        status: str = None,
        progress: float = None,
        current_stage: str = None,
        error: str = None
    ):
        """Update report processing status"""
        if report_id not in self._statuses:
            self._statuses[report_id] = {
                "report_id": report_id,
                "status": "unknown",
                "progress": 0.0,
                "stages_completed": [],
                "current_stage": None,
                "error": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        
        if status:
            self._statuses[report_id]["status"] = status
        if progress is not None:
            self._statuses[report_id]["progress"] = progress
        if current_stage:
            self._statuses[report_id]["current_stage"] = current_stage
            if current_stage not in self._statuses[report_id]["stages_completed"]:
                self._statuses[report_id]["stages_completed"].append(current_stage)
        if error:
            self._statuses[report_id]["error"] = error
        
        self._statuses[report_id]["updated_at"] = datetime.now().isoformat()
    
    async def get_report_status(self, report_id: str) -> Dict:
        """Get report processing status"""
        return self._statuses.get(report_id, {
            "report_id": report_id,
            "status": "not_found",
            "progress": 0.0,
            "stages_completed": [],
        })
    
    async def save_analysis_result(
        self,
        report_id: str,
        result: Dict[str, Any]
    ):
        """Save analysis result"""
        if report_id in self._reports:
            self._reports[report_id]["analysis_result"] = result
    
    async def get_batch_status(self, batch_id: str) -> Dict:
        """Get batch processing status"""
        return {
            "batch_id": batch_id,
            "status": "unknown",
            "total": 0,
            "completed": 0,
            "failed": 0,
        }
