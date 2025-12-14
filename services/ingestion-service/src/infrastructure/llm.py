"""
LLM Proxy Client
"""

from typing import Dict, Any, List
from loguru import logger
import httpx


class LLMProxyClient:
    """Client for LLM Proxy Service"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.timeout = 300  # 5 minutes for LLM calls
    
    async def analyze_report(
        self,
        report_id: str,
        file_urls: List[str],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call LLM to analyze report"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/llm/analyze",
                    json={
                        "report_id": report_id,
                        "file_urls": file_urls,
                        "metadata": metadata
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"LLM analysis failed: {response.status_code}")
                    return self._mock_response(report_id, metadata)
                    
        except Exception as e:
            logger.warning(f"LLM proxy call failed: {e}, using mock response")
            return self._mock_response(report_id, metadata)
    
    def _mock_response(
        self,
        report_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate mock response for development"""
        return {
            "report_id": report_id,
            "facts": [
                f"District: {metadata.get('district', 'Unknown')}",
                f"City: {metadata.get('city', 'Unknown')}",
            ],
            "insights": [
                "Analysis completed (mock)",
            ],
            "sentiment": {
                "overall": "neutral",
                "confidence": 0.5
            },
            "confidence_score": 0.7
        }
