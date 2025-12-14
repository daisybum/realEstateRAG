"""
Graph Service - gRPC Server
"""

import grpc
from concurrent import futures
from loguru import logger
from typing import Dict, Any

# In production, these would be generated from proto
# For now, using simple implementation

class GraphServiceHandler:
    """Handler for graph operations"""
    
    def __init__(self, falkordb_url: str = "redis://localhost:6379"):
        self.falkordb_url = falkordb_url
        self._graph = None
    
    async def connect(self):
        """Connect to FalkorDB"""
        try:
            from falkordb import FalkorDB
            db = FalkorDB.from_url(self.falkordb_url)
            self._graph = db.select_graph("real_estate")
            logger.info("Connected to FalkorDB")
        except Exception as e:
            logger.warning(f"FalkorDB connection failed: {e}")
    
    async def create_node(
        self,
        label: str,
        properties: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a node in the graph"""
        if not self._graph:
            return {"id": "mock_id", "label": label, "properties": properties}
        
        props_str = ", ".join(f"{k}: '{v}'" for k, v in properties.items())
        query = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
        
        result = self._graph.query(query)
        return {"id": "created", "label": label, "properties": properties}
    
    async def execute_cypher(
        self,
        query: str,
        parameters: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Execute Cypher query"""
        if not self._graph:
            return {"nodes": [], "relationships": [], "raw_json": "[]"}
        
        result = self._graph.query(query)
        return {
            "nodes": [],
            "relationships": [],
            "raw_json": str(result.result_set),
            "result_count": len(result.result_set)
        }
    
    async def ingest_report(
        self,
        report_id: str,
        facts: list,
        insights: list,
        metadata: Dict[str, str]
    ) -> Dict[str, Any]:
        """Ingest report data into graph"""
        nodes_created = 0
        relationships_created = 0
        
        # Create Report node
        await self.create_node("Report", {"id": report_id, **metadata})
        nodes_created += 1
        
        # Create nodes for each fact
        for i, fact in enumerate(facts):
            await self.create_node("Fact", {"id": f"fact_{report_id}_{i}", "content": fact})
            nodes_created += 1
        
        return {
            "report_id": report_id,
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
            "success": True,
            "message": "Ingestion completed"
        }


async def serve(port: int = 50051):
    """Start gRPC server (simplified for development)"""
    handler = GraphServiceHandler()
    await handler.connect()
    
    # In production, use actual gRPC server
    logger.info(f"Graph Service would start on port {port}")
    logger.info("Using simplified HTTP wrapper for development")
    
    # For development, we'll use a simple HTTP wrapper
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(title="Graph Service", version="1.0.0")
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "graph-service"}
    
    @app.post("/graph/node")
    async def create_node(label: str, properties: dict):
        return await handler.create_node(label, properties)
    
    @app.post("/graph/query")
    async def execute_query(query: str, parameters: dict = None):
        return await handler.execute_cypher(query, parameters)
    
    @app.post("/graph/ingest")
    async def ingest(report_id: str, facts: list, insights: list, metadata: dict):
        return await handler.ingest_report(report_id, facts, insights, metadata)
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    import asyncio
    asyncio.run(serve())
