"""
Ingestion Service API Routes
"""

from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from typing import List
from uuid import uuid4

from .schemas import (
    ReportSubmissionRequest,
    ReportSubmissionResponse,
    ReportStatusResponse,
    BatchSubmissionRequest,
    BatchSubmissionResponse,
)
from ..domain.services import IngestionService
from .dependencies import get_ingestion_service

router = APIRouter()


@router.post("/reports", response_model=ReportSubmissionResponse)
async def submit_report(
    metadata: ReportSubmissionRequest,
    files: List[UploadFile] = File(default=[]),
    background_tasks: BackgroundTasks = None,
    service: IngestionService = Depends(get_ingestion_service)
):
    """
    Submit new real estate report for analysis
    
    - **files**: Report PDF and images (optional)
    - **metadata**: Report metadata (location, date, etc.)
    """
    report_id = str(uuid4())
    
    # Store files and process asynchronously
    if background_tasks:
        background_tasks.add_task(
            service.process_report,
            report_id=report_id,
            files=files,
            metadata=metadata.model_dump()
        )
    
    return ReportSubmissionResponse(
        report_id=report_id,
        status="queued",
        message="Report submitted for processing"
    )


@router.get("/reports/{report_id}/status", response_model=ReportStatusResponse)
async def get_report_status(
    report_id: str,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Get processing status of a report"""
    try:
        status = await service.get_status(report_id)
        return ReportStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")


@router.post("/reports/{report_id}/reprocess")
async def reprocess_report(
    report_id: str,
    background_tasks: BackgroundTasks,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Trigger reprocessing of a report"""
    background_tasks.add_task(
        service.reprocess_report,
        report_id=report_id
    )
    return {"message": "Reprocessing initiated", "report_id": report_id}


@router.post("/batch", response_model=BatchSubmissionResponse)
async def submit_batch(
    request: BatchSubmissionRequest,
    background_tasks: BackgroundTasks,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Submit batch of reports for processing"""
    batch_id = str(uuid4())
    
    background_tasks.add_task(
        service.process_batch,
        batch_id=batch_id,
        report_ids=request.report_ids
    )
    
    return BatchSubmissionResponse(
        batch_id=batch_id,
        total=len(request.report_ids),
        status="queued"
    )


@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Get batch processing status"""
    try:
        status = await service.get_batch_status(batch_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")
