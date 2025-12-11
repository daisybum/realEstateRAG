"""
Ingestion Routes
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

router = APIRouter()


class IngestionRequest(BaseModel):
    """수집 요청"""
    report_ids: List[str] = Field(..., description="리포트 ID 목록")
    max_concurrent: int = Field(default=5, ge=1, le=10, description="최대 동시 처리")


class IngestionStatus(BaseModel):
    """수집 상태"""
    job_id: str
    status: str  # pending, running, completed, failed
    total: int
    processed: int
    failed: int
    started_at: Optional[str]
    completed_at: Optional[str]


class SingleIngestionRequest(BaseModel):
    """단일 리포트 수집"""
    report_id: str


class SingleIngestionResponse(BaseModel):
    """단일 리포트 수집 결과"""
    report_id: str
    success: bool
    entities_count: int
    relationships_count: int
    confidence: float
    processing_time: float
    error: Optional[str] = None


# In-memory job tracking (production에서는 Redis 사용)
_jobs: dict = {}


@router.post("/single", response_model=SingleIngestionResponse)
async def ingest_single(request: SingleIngestionRequest):
    """단일 리포트 수집"""
    from realestaterag.ingestion import IngestionPipeline
    
    try:
        pipeline = IngestionPipeline()
        result = await pipeline.process_report(request.report_id)
        
        return SingleIngestionResponse(
            report_id=result.report_id,
            success=True,
            entities_count=len(result.entities),
            relationships_count=len(result.relationships),
            confidence=result.confidence_score,
            processing_time=result.processing_time,
        )
        
    except Exception as e:
        return SingleIngestionResponse(
            report_id=request.report_id,
            success=False,
            entities_count=0,
            relationships_count=0,
            confidence=0.0,
            processing_time=0.0,
            error=str(e),
        )


@router.post("/batch")
async def ingest_batch(
    request: IngestionRequest,
    background_tasks: BackgroundTasks,
):
    """배치 수집 (백그라운드)"""
    import uuid
    
    job_id = str(uuid.uuid4())[:8]
    
    _jobs[job_id] = IngestionStatus(
        job_id=job_id,
        status="pending",
        total=len(request.report_ids),
        processed=0,
        failed=0,
        started_at=None,
        completed_at=None,
    )
    
    background_tasks.add_task(
        _run_batch_ingestion,
        job_id,
        request.report_ids,
        request.max_concurrent,
    )
    
    return {"job_id": job_id, "status": "accepted", "total": len(request.report_ids)}


@router.get("/status/{job_id}", response_model=IngestionStatus)
async def get_job_status(job_id: str):
    """작업 상태 조회"""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


async def _run_batch_ingestion(job_id: str, report_ids: List[str], max_concurrent: int):
    """배치 수집 실행"""
    from realestaterag.ingestion import IngestionPipeline
    
    job = _jobs[job_id]
    job.status = "running"
    job.started_at = datetime.now().isoformat()
    
    try:
        pipeline = IngestionPipeline()
        results = await pipeline.batch_process(report_ids, max_concurrent)
        
        job.processed = len(results)
        job.failed = len(report_ids) - len(results)
        job.status = "completed"
        job.completed_at = datetime.now().isoformat()
        
    except Exception as e:
        job.status = "failed"
        job.completed_at = datetime.now().isoformat()
