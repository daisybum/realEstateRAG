"""
FalkorDB to Neo4j Migration Script

Migrates knowledge graph data from FalkorDB to Neo4j with vector embeddings.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger

try:
    from falkordb import FalkorDB
    FALKORDB_AVAILABLE = True
except ImportError:
    FALKORDB_AVAILABLE = False
    logger.warning("FalkorDB not available")

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

from realestaterag.graph.neo4j_schema import Neo4jSchemaManager


class DataMigrator:
    """Migrates data from FalkorDB to Neo4j with vector embeddings"""
    
    def __init__(
        self,
        falkor_host: str = "localhost",
        falkor_port: int = 6379,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_auth: tuple = ("neo4j", "realestaterag123"),
        model_name: str = "jhgan/ko-sbert-nli"
    ):
        # FalkorDB connection
        if FALKORDB_AVAILABLE:
            self.falkor_client = FalkorDB(host=falkor_host, port=falkor_port)
            self.falkor_graph = self.falkor_client.select_graph("wolbu_v3")
        else:
            self.falkor_client = None
            self.falkor_graph = None
        
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        
        # Embedding model
        logger.info(f"Loading embedding model: {model_name}")
        self.encoder = SentenceTransformer(model_name)
        
        # Schema manager
        self.schema_manager = Neo4jSchemaManager(neo4j_uri, neo4j_auth)
    
    def close(self):
        """Close all connections"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
        if self.schema_manager:
            self.schema_manager.close()
        logger.info("Connections closed")
    
    async def extract_from_falkordb(self, node_type: str) -> List[Dict]:
        """Extract nodes from FalkorDB"""
        if not self.falkor_graph:
            logger.warning("FalkorDB not available, returning empty list")
            return []
        
        query = f"MATCH (n:{node_type}) RETURN n"
        
        try:
            result = self.falkor_graph.query(query)
            nodes = []
            
            for record in result.result_set:
                node = record[0]
                # Convert FalkorDB node to dict
                node_dict = {
                    "id": node.id,
                    "labels": list(node.labels),
                    "properties": dict(node.properties)
                }
                nodes.append(node_dict)
            
            logger.info(f"Extracted {len(nodes)} {node_type} nodes from FalkorDB")
            return nodes
            
        except Exception as e:
            logger.error(f"Failed to extract {node_type} nodes: {e}")
            return []
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for texts"""
        if not texts:
            return []
        
        embeddings = self.encoder.encode(texts)
        return [emb.tolist() for emb in embeddings]
    
    async def migrate_complexes(self):
        """Migrate Complex nodes with embeddings"""
        logger.info("Migrating Complex nodes...")
        
        # Extract from FalkorDB
        complexes_data = await self.extract_from_falkordb("Complex")
        
        if not complexes_data:
            logger.warning("No Complex nodes to migrate")
            return
        
        # Prepare data with embeddings
        complexes = []
        descriptions = []
        
        for data in complexes_data:
            props = data["properties"]
            
            # Create description for embedding
            description = f"{props.get('name', '')} {props.get('address', '')} {props.get('total_households', '')}세대"
            descriptions.append(description)
            
            complexes.append({
                "name": props.get("name"),
                "address": props.get("address"),
                "total_households": props.get("total_households"),
                "construction_year": props.get("construction_year"),
                "avg_area": props.get("avg_area"),
                "description": description,
            })
        
        # Generate embeddings
        embeddings = self.generate_embeddings(descriptions)
        
        # Add embeddings to data
        for i, complex_data in enumerate(complexes):
            complex_data["description_embedding"] = embeddings[i]
        
        # Batch insert to Neo4j
        with self.neo4j_driver.session() as session:
            session.execute_write(self._create_complex_nodes, complexes)
        
        logger.info(f"Migrated {len(complexes)} Complex nodes")
    
    @staticmethod
    def _create_complex_nodes(tx, complexes):
        """Transaction function to create Complex nodes"""
        query = """
        UNWIND $complexes AS complex
        MERGE (c:Complex {name: complex.name})
        SET c.address = complex.address,
            c.total_households = complex.total_households,
            c.construction_year = complex.construction_year,
            c.avg_area = complex.avg_area,
            c.description = complex.description,
            c.description_embedding = complex.description_embedding,
            c.migrated_at = datetime()
        RETURN count(c) as created
        """
        result = tx.run(query, complexes=complexes)
        record = result.single()
        return record["created"] if record else 0
    
    async def migrate_market_snapshots(self):
        """Migrate MarketSnapshot nodes (no embeddings needed)"""
        logger.info("Migrating MarketSnapshot nodes...")
        
        snapshots_data = await self.extract_from_falkordb("MarketSnapshot")
        
        if not snapshots_data:
            logger.warning("No MarketSnapshot nodes to migrate")
            return
        
        snapshots = []
        for data in snapshots_data:
            props = data["properties"]
            snapshots.append({
                "date": props.get("date"),
                "avg_price": props.get("avg_price"),
                "jeonse_ratio": props.get("jeonse_ratio"),
                "transaction_volume": props.get("transaction_volume"),
                "price_change_rate": props.get("price_change_rate"),
            })
        
        with self.neo4j_driver.session() as session:
            session.execute_write(self._create_market_nodes, snapshots)
        
        logger.info(f"Migrated {len(snapshots)} MarketSnapshot nodes")
    
    @staticmethod
    def _create_market_nodes(tx, snapshots):
        """Transaction function to create MarketSnapshot nodes"""
        query = """
        UNWIND $snapshots AS snapshot
        CREATE (m:MarketSnapshot {
            date: snapshot.date,
            avg_price: snapshot.avg_price,
            jeonse_ratio: snapshot.jeonse_ratio,
            transaction_volume: snapshot.transaction_volume,
            price_change_rate: snapshot.price_change_rate,
            migrated_at: datetime()
        })
        RETURN count(m) as created
        """
        result = tx.run(query, snapshots=snapshots)
        record = result.single()
        return record["created"] if record else 0
    
    async def migrate_relationships(self):
        """Migrate relationships from FalkorDB"""
        logger.info("Migrating relationships...")
        
        if not self.falkor_graph:
            logger.warning("FalkorDB not available, skipping relationships")
            return
        
        # Migrate HAS_MARKET_DATA relationships
        query = """
        MATCH (c:Complex)-[r:HAS_MARKET_DATA]->(m:MarketSnapshot)
        RETURN c.name as complex_name, m.date as snapshot_date, properties(r) as rel_props
        """
        
        try:
            result = self.falkor_graph.query(query)
            relationships = []
            
            for record in result.result_set:
                relationships.append({
                    "complex_name": record[0],
                    "snapshot_date": record[1],
                    "properties": record[2] if len(record) > 2 else {}
                })
            
            logger.info(f"Extracted {len(relationships)} HAS_MARKET_DATA relationships")
            
            # Create in Neo4j
            with self.neo4j_driver.session() as session:
                session.execute_write(self._create_market_relationships, relationships)
            
        except Exception as e:
            logger.error(f"Relationship migration failed: {e}")
    
    @staticmethod
    def _create_market_relationships(tx, relationships):
        """Create HAS_MARKET_DATA relationships"""
        query = """
        UNWIND $rels AS rel
        MATCH (c:Complex {name: rel.complex_name})
        MATCH (m:MarketSnapshot {date: rel.snapshot_date})
        MERGE (c)-[r:HAS_MARKET_DATA]->(m)
        SET r.date = rel.snapshot_date
        RETURN count(r) as created
        """
        result = tx.run(query, rels=relationships)
        record = result.single()
        return record["created"] if record else 0
    
    async def validate_migration(self) -> Dict[str, Any]:
        """Validate migration by comparing node counts"""
        logger.info("Validating migration...")
        
        validation = {}
        
        with self.neo4j_driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n:Complex) RETURN count(n) as count")
            validation["neo4j_complex_count"] = result.single()["count"]
            
            result = session.run("MATCH (n:MarketSnapshot) RETURN count(n) as count")
            validation["neo4j_market_count"] = result.single()["count"]
            
            result = session.run("MATCH ()-[r:HAS_MARKET_DATA]->() RETURN count(r) as count")
            validation["neo4j_relationship_count"] = result.single()["count"]
        
        logger.info(f"Validation results: {validation}")
        return validation
    
    async def migrate_all(self):
        """Execute complete migration"""
        logger.info("=" * 60)
        logger.info("Starting FalkorDB → Neo4j Migration")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # 1. Initialize Neo4j schema
            logger.info("\n[1/5] Initializing Neo4j schema...")
            self.schema_manager.initialize_schema()
            
            # 2. Migrate Complex nodes
            logger.info("\n[2/5] Migrating Complex nodes...")
            await self.migrate_complexes()
            
            # 3. Migrate MarketSnapshot nodes
            logger.info("\n[3/5] Migrating MarketSnapshot nodes...")
            await self.migrate_market_snapshots()
            
            # 4. Migrate relationships
            logger.info("\n[4/5] Migrating relationships...")
            await self.migrate_relationships()
            
            # 5. Validate
            logger.info("\n[5/5] Validating migration...")
            validation = await self.validate_migration()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info(f"Migration completed in {duration:.2f} seconds")
            logger.info(f"Results: {validation}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            self.close()


async def main():
    """Main migration entry point"""
    migrator = DataMigrator()
    
    try:
        await migrator.migrate_all()
    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
