"""
Health Check Routes
"""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    components: dict


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    from realestaterag.config import settings
    
    # Check components
    components = {
        "api": "healthy",
    }
    
    # Check FalkorDB
    try:
        from realestaterag.query.retriever import GraphRetriever
        retriever = GraphRetriever()
        stats = retriever.get_statistics()
        components["falkordb"] = "healthy" if stats else "degraded"
    except Exception as e:
        components["falkordb"] = f"unhealthy: {str(e)[:50]}"
    
    # Check LLM
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.llm_api_url}/models")
            components["llm"] = "healthy" if resp.status_code == 200 else "degraded"
    except Exception:
        components["llm"] = "unavailable"
    
    # Overall status
    status = "healthy"
    if any("unhealthy" in str(v) for v in components.values()):
        status = "unhealthy"
    elif any(v in ["degraded", "unavailable"] for v in components.values()):
        status = "degraded"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        components=components,
    )


@router.get("/ready")
async def readiness():
    """Readiness probe"""
    return {"ready": True}


@router.get("/live")
async def liveness():
    """Liveness probe"""
    return {"live": True}
