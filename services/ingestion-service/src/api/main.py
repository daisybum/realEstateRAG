"""
Ingestion Service - FastAPI Application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from .routes import router
from .config import get_settings
from ..infrastructure.messaging import MessageBroker
from ..infrastructure.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    settings = get_settings()
    
    # Startup
    logger.info(f"Starting {settings.service_name}...")
    
    try:
        await Database.connect(settings.database_url)
        logger.info("Database connected")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
    
    try:
        await MessageBroker.connect(settings.rabbitmq_url)
        logger.info("RabbitMQ connected")
    except Exception as e:
        logger.warning(f"RabbitMQ connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await Database.disconnect()
    await MessageBroker.disconnect()


app = FastAPI(
    title="Ingestion Service",
    version="1.0.0",
    description="Real Estate Report Ingestion Service",
    docs_url="/api/docs",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics
if PROMETHEUS_AVAILABLE:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ingestion-service",
        "version": "1.0.0"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe"""
    db_healthy = await Database.ping()
    mq_healthy = await MessageBroker.ping()
    
    status = "ready" if (db_healthy and mq_healthy) else "not_ready"
    
    return {
        "status": status,
        "database": "connected" if db_healthy else "disconnected",
        "rabbitmq": "connected" if mq_healthy else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
