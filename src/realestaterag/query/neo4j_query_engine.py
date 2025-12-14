"""
Neo4j Query Engine

Implements semantic search and graph traversal using Neo4j with vector embeddings.
"""

from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from loguru import logger


class Neo4jQueryEngine:
    """Query engine for Neo4j with vector search support"""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple = ("neo4j", "realestaterag123"),
        model_name: str = "jhgan/ko-sbert-nli"
    ):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.encoder = SentenceTransformer(model_name)
        logger.info(f"Neo4jQueryEngine initialized with {uri}")
    
    def close(self):
        """Close driver connection"""
        self.driver.close()
    
    async def semantic_search(
        self,
        query: str,
        node_type: str = "Complex",
        top_k: int = 10
    ) -> List[Dict]:
        """
        Semantic search using vector similarity
        
        Args:
            query: Natural language search query
            node_type: Type of nodes to search (Complex, Facility, etc.)
            top_k: Number of results to return
            
        Returns:
            List of matching nodes with similarity scores
        """
        # Generate query embedding
        query_embedding = self.encoder.encode(query).tolist()
        
        # Neo4j vector search query (requires 5.11+ with vector index)
        cypher = f"""
        CALL db.index.vector.queryNodes(
            '{node_type.lower()}_description_embedding_idx',
            $top_k,
            $query_embedding
        ) YIELD node, score
        RETURN
            node.name AS name,
            node.address AS address,
            node.description AS description,
            score
        ORDER BY score DESC
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    top_k=top_k,
                    query_embedding=query_embedding
                )
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            logger.warning("Falling back to text-based search")
            return await self._fallback_text_search(query, node_type, top_k)
    
    async def _fallback_text_search(
        self,
        query: str,
        node_type: str,
        top_k: int
    ) -> List[Dict]:
        """Fallback to text-based search if vector search unavailable"""
        cypher = f"""
        MATCH (n:{node_type})
        WHERE n.name CONTAINS $query OR n.description CONTAINS $query
        RETURN
            n.name AS name,
            n.address AS address,
            n.description AS description,
            1.0 AS score
        LIMIT $top_k
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, query=query, top_k=top_k)
            return [dict(record) for record in result]
    
    async def facility_based_search(
        self,
        facility_name: str,
        max_distance: int = 30,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Find complexes near a facility with optional filters
        
        Args:
            facility_name: Name of facility (e.g., "강남역")
            max_distance: Maximum distance in minutes
            filters: Additional filters (jeonse_ratio, price_range, etc.)
            
        Returns:
            List of matching complexes with distance and market data
        """
        filters = filters or {}
        
        # Generate facility embedding
        facility_embedding = self.encoder.encode(facility_name).tolist()
        
        cypher = """
        // 1. Find similar facilities using vector search
        CALL db.index.vector.queryNodes(
            'facility_name_embedding_idx',
            5,
            $facility_embedding
        ) YIELD node AS facility, score
        WHERE score > 0.8
        
        // 2. Find nearby complexes
        MATCH (facility)<-[r:NEAR]-(c:Complex)
        WHERE r.distance_minutes <= $max_distance
        
        // 3. Get latest market data
        OPTIONAL MATCH (c)-[:HAS_MARKET_DATA]->(m:MarketSnapshot)
        WHERE m.date >= date() - duration({months: 1})
        
        // 4. Apply filters
        WITH c, m, r.distance_minutes AS distance
        WHERE ($jeonse_ratio IS NULL OR m.jeonse_ratio >= $jeonse_ratio)
          AND ($min_price IS NULL OR m.avg_price >= $min_price)
          AND ($max_price IS NULL OR m.avg_price <= $max_price)
        
        RETURN
            c.name AS complex_name,
            c.address,
            distance,
            m.avg_price AS price,
            m.jeonse_ratio,
            m.date AS market_date
        ORDER BY distance ASC, m.jeonse_ratio DESC
        LIMIT 20
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    facility_embedding=facility_embedding,
                    max_distance=max_distance,
                    jeonse_ratio=filters.get("jeonse_ratio"),
                    min_price=filters.get("min_price"),
                    max_price=filters.get("max_price")
                )
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Facility search failed: {e}")
            return await self._fallback_facility_search(facility_name, max_distance, filters)
    
    async def _fallback_facility_search(
        self,
        facility_name: str,
        max_distance: int,
        filters: Dict
    ) -> List[Dict]:
        """Fallback facility search without vector index"""
        cypher = """
        MATCH (f:Facility)<-[r:NEAR]-(c:Complex)
        WHERE f.name CONTAINS $facility_name
          AND r.distance_minutes <= $max_distance
        
        OPTIONAL MATCH (c)-[:HAS_MARKET_DATA]->(m:MarketSnapshot)
        WHERE m.date >= date() - duration({months: 1})
        
        RETURN
            c.name AS complex_name,
            c.address,
            r.distance_minutes AS distance,
            m.avg_price AS price,
            m.jeonse_ratio
        ORDER BY distance ASC
        LIMIT 20
        """
        
        with self.driver.session() as session:
            result = session.run(
                cypher,
                facility_name=facility_name,
                max_distance=max_distance
            )
            return [dict(record) for record in result]
    
    async def hybrid_search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Hybrid search combining vector similarity and graph context
        
        Args:
            query: Natural language query
            filters: Filters to apply
            top_k: Number of results
            
        Returns:
            Ranked list of results combining semantic and structural relevance
        """
        filters = filters or {}
        
        # Get semantic matches
        semantic_results = await self.semantic_search(query, top_k=top_k * 2)
        
        # Enrich with graph context
        cypher = """
        MATCH (c:Complex {name: $complex_name})
        
        // Get market data
        OPTIONAL MATCH (c)-[:HAS_MARKET_DATA]->(m:MarketSnapshot)
        WHERE m.date >= date() - duration({months: 1})
        
        // Get nearby facilities
        OPTIONAL MATCH (c)-[r:NEAR]->(f:Facility)
        WHERE r.distance_minutes <= 30
        
        RETURN
            c.name AS name,
            c.address,
            m.avg_price AS price,
            m.jeonse_ratio,
            collect(f.name)[..5] AS nearby_facilities
        """
        
        enriched_results = []
        with self.driver.session() as session:
            for result in semantic_results[:top_k]:
                context = session.run(cypher, complex_name=result["name"]).single()
                if context:
                    enriched_results.append({
                        **result,
                        **dict(context)
                    })
        
        return enriched_results
    
    async def get_statistics(self) -> Dict[str, int]:
        """Get graph statistics"""
        with self.driver.session() as session:
            stats = {}
            
            # Node counts
            for label in ["Complex", "MarketSnapshot", "Facility", "District"]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                stats[f"{label.lower()}_count"] = result.single()["count"]
            
            # Relationship counts
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats["relationship_count"] = result.single()["count"]
            
            return stats


# Singleton instance
_engine: Optional[Neo4jQueryEngine] = None


def get_neo4j_engine() -> Neo4jQueryEngine:
    """Get singleton Neo4j query engine instance"""
    global _engine
    if _engine is None:
        _engine = Neo4jQueryEngine()
    return _engine


if __name__ == "__main__":
    import asyncio
    
    async def test():
        engine = Neo4jQueryEngine()
        
        try:
            # Test semantic search
            results = await engine.semantic_search("전세가율 높은 아파트")
            print(f"\nSemantic search results: {len(results)}")
            for r in results[:3]:
                print(f"  - {r['name']}: {r.get('score', 0):.3f}")
            
            # Test statistics
            stats = await engine.get_statistics()
            print(f"\nGraph statistics: {stats}")
            
        finally:
            engine.close()
    
    asyncio.run(test())
