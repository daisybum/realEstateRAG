"""
FastAPI Application

RealEstateRAG REST API
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from realestaterag.config import settings
from realestaterag.api.v1.routes import health, query, ingestion

try:
    from realestaterag.api.v1.routes import neo4j_query
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    from loguru import logger
    logger.info(f"Starting {settings.app_name} v1.0.0")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="GraphRAG-powered Real Estate Intelligence Platform",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics (optional)
if settings.enable_metrics:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except ImportError:
        pass

# Routes
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(ingestion.router, prefix="/api/v1/ingestion", tags=["Ingestion"])

# Neo4j Routes (if available)
if NEO4J_AVAILABLE:
    app.include_router(neo4j_query.router, prefix="/api/v1/neo4j", tags=["Neo4j"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def main():
    """Run the API server"""
    import uvicorn
    uvicorn.run(
        "realestaterag.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if not settings.debug else 1,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    main()
