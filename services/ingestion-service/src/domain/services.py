"""
Ingestion Service - Domain Services
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ..infrastructure.messaging import MessageBroker
from ..infrastructure.storage import StorageClient
from ..infrastructure.llm import LLMProxyClient
from ..infrastructure.database import ReportRepository


class IngestionService:
    """Core business logic for report ingestion"""
    
    def __init__(
        self,
        storage: StorageClient,
        llm: LLMProxyClient,
        repository: ReportRepository,
        message_broker: MessageBroker
    ):
        self.storage = storage
        self.llm = llm
        self.repository = repository
        self.message_broker = message_broker
    
    async def process_report(
        self,
        report_id: str,
        files: List,
        metadata: Dict[str, Any]
    ):
        """Main processing pipeline"""
        try:
            # Update status
            await self.repository.update_status(
                report_id,
                status="processing",
                current_stage="upload"
            )
            
            # Step 1: Store files
            logger.info(f"Storing files for report {report_id}")
            file_urls = []
            if files:
                file_urls = await self.storage.upload_files(
                    report_id=report_id,
                    files=files
                )
            
            # Step 2: Save metadata
            await self.repository.create_report(
                report_id=report_id,
                metadata=metadata,
                file_urls=file_urls
            )
            
            await self.repository.update_status(
                report_id,
                status="processing",
                current_stage="analysis"
            )
            
            # Step 3: Call LLM for analysis
            logger.info(f"Analyzing report {report_id}")
            analysis_result = await self.llm.analyze_report(
                report_id=report_id,
                file_urls=file_urls,
                metadata=metadata
            )
            
            # Step 4: Save results
            await self.repository.save_analysis_result(
                report_id=report_id,
                result=analysis_result
            )
            
            # Step 5: Publish event
            await self.message_broker.publish(
                exchange="realestaterag.events",
                routing_key="report.analyzed",
                message={
                    "report_id": report_id,
                    "facts": analysis_result.get("facts", []),
                    "insights": analysis_result.get("insights", []),
                    "metadata": metadata
                }
            )
            
            # Update status
            await self.repository.update_status(
                report_id,
                status="completed",
                progress=1.0
            )
            
            logger.info(f"Successfully processed report {report_id}")
            
        except Exception as e:
            logger.error(f"Failed to process report {report_id}: {e}")
            await self.repository.update_status(
                report_id,
                status="failed",
                error=str(e)
            )
            
            # Publish failure event
            await self.message_broker.publish(
                exchange="realestaterag.events",
                routing_key="report.analysis.failed",
                message={
                    "report_id": report_id,
                    "error": str(e)
                }
            )
            raise
    
    async def reprocess_report(self, report_id: str):
        """Reprocess an existing report"""
        report = await self.repository.get_report(report_id)
        if report:
            await self.process_report(
                report_id=report_id,
                files=[],
                metadata=report.get("metadata", {})
            )
    
    async def process_batch(
        self,
        batch_id: str,
        report_ids: List[str]
    ):
        """Process a batch of reports"""
        for i, report_id in enumerate(report_ids):
            try:
                report = await self.repository.get_report(report_id)
                if report:
                    await self.process_report(
                        report_id=report_id,
                        files=[],
                        metadata=report.get("metadata", {})
                    )
            except Exception as e:
                logger.error(f"Batch {batch_id}: Failed {report_id}: {e}")
    
    async def get_status(self, report_id: str) -> Dict[str, Any]:
        """Get report processing status"""
        return await self.repository.get_report_status(report_id)
    
    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get batch processing status"""
        return await self.repository.get_batch_status(batch_id)
