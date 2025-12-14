"""
Ingestion Service API Schemas
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReportSubmissionRequest(BaseModel):
    """Request for submitting a report"""
    title: str = Field(..., description="Report title")
    district: str = Field(..., description="District name")
    city: str = Field(default="", description="City name")
    province: str = Field(default="", description="Province name")
    date: Optional[datetime] = Field(default=None, description="Report date")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ReportSubmissionResponse(BaseModel):
    """Response for report submission"""
    report_id: str
    status: str  # queued, processing, completed, failed
    message: str


class ReportStatusResponse(BaseModel):
    """Response for report status"""
    report_id: str
    status: str
    progress: float = 0.0  # 0.0 to 1.0
    stages_completed: List[str] = []
    current_stage: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BatchSubmissionRequest(BaseModel):
    """Request for batch submission"""
    report_ids: List[str] = Field(..., description="List of report IDs to process")
    max_concurrent: int = Field(default=5, description="Max concurrent processing")


class BatchSubmissionResponse(BaseModel):
    """Response for batch submission"""
    batch_id: str
    total: int
    status: str


class BatchStatusResponse(BaseModel):
    """Response for batch status"""
    batch_id: str
    total: int
    completed: int
    failed: int
    status: str  # queued, processing, completed
    results: List[ReportStatusResponse] = []
