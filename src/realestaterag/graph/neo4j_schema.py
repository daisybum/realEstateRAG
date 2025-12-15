"""
Neo4j Schema Manager

Defines and manages Neo4j node schema with vector properties for semantic search.
"""

from typing import Dict, List, Optional
import os
from neo4j import GraphDatabase, Driver
from loguru import logger


class Neo4jSchemaManager:
    """Manages Neo4j schema including nodes, relationships, and vector indexes"""
    
    NODE_DEFINITIONS = {
        "Region": {
            "properties": ["name", "code", "description"],
            "vector": "description_embedding",
            "vector_dimensions": 768,
        },
        "District": {
            "properties": ["name", "code", "parent_region", "description"],
            "vector": "description_embedding",
            "vector_dimensions": 768,
        },
        "Neighborhood": {
            "properties": ["name", "code", "district", "description"],
            "vector": "description_embedding",
            "vector_dimensions": 768,
        },
        "Complex": {
            "properties": [
                "name", "address", "total_households",
                "construction_year", "avg_area", "description"
            ],
            "vector": "description_embedding",
            "vector_dimensions": 768,
        },
        "Facility": {
            "properties": ["name", "type", "location", "distance"],
            "vector": "name_embedding",
            "vector_dimensions": 768,
        },
        "MarketSnapshot": {
            "properties": [
                "date", "avg_price", "jeonse_ratio",
                "transaction_volume", "price_change_rate"
            ],
            "vector": None,  # Time-series data doesn't need vectors
        },
        "InvestmentAnalysis": {
            "properties": [
                "grade", "score", "analysis_date", "recommendations"
            ],
            "vector": "recommendations_embedding",
            "vector_dimensions": 768,
        }
    }
    
    RELATIONSHIPS = {
        "LOCATED_IN": {
            "from": ["District", "Complex", "Neighborhood"],
            "to": ["Region", "District"],
            "properties": []
        },
        "NEAR": {
            "from": "Complex",
            "to": "Facility",
            "properties": ["distance_minutes", "transport_type"]
        },
        "HAS_MARKET_DATA": {
            "from": "Complex",
            "to": "MarketSnapshot",
            "properties": ["date"]
        },
        "HAS_ANALYSIS": {
            "from": "Complex",
            "to": "InvestmentAnalysis",
            "properties": ["date"]
        },
        "PART_OF": {
            "from": "Neighborhood",
            "to": "District",
            "properties": []
        }
    }
    
    def __init__(self, uri: str, auth: tuple):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=auth)
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close driver connection"""
        self.driver.close()
    
    def create_constraints(self):
        """Create uniqueness constraints on node IDs"""
        constraints = [
            "CREATE CONSTRAINT region_id IF NOT EXISTS FOR (r:Region) REQUIRE r.code IS UNIQUE",
            "CREATE CONSTRAINT district_id IF NOT EXISTS FOR (d:District) REQUIRE d.code IS UNIQUE",
            "CREATE CONSTRAINT neighborhood_id IF NOT EXISTS FOR (n:Neighborhood) REQUIRE n.code IS UNIQUE",
            "CREATE CONSTRAINT complex_id IF NOT EXISTS FOR (c:Complex) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.name IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint.split()[2]}")
                except Exception as e:
                    logger.warning(f"Constraint creation failed: {e}")
    
    def create_indexes(self):
        """Create property indexes for faster queries"""
        indexes = [
            "CREATE INDEX complex_address IF NOT EXISTS FOR (c:Complex) ON (c.address)",
            "CREATE INDEX market_date IF NOT EXISTS FOR (m:MarketSnapshot) ON (m.date)",
            "CREATE INDEX facility_type IF NOT EXISTS FOR (f:Facility) ON (f.type)",
        ]
        
        with self.driver.session() as session:
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"Created index: {index.split()[2]}")
                except Exception as e:
                    logger.warning(f"Index creation failed: {e}")
    
    def create_vector_indexes(self):
        """Create vector indexes for semantic search
        
        Note: This requires Neo4j 5.11+ and vector index support
        """
        vector_indexes = []
        
        for node_type, definition in self.NODE_DEFINITIONS.items():
            if definition["vector"]:
                vector_prop = definition["vector"]
                dimensions = definition["vector_dimensions"]
                
                # Neo4j vector index syntax (5.11+)
                query = f"""
                CREATE VECTOR INDEX {node_type.lower()}_{vector_prop}_idx IF NOT EXISTS
                FOR (n:{node_type})
                ON n.{vector_prop}
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
                """
                vector_indexes.append((node_type, query))
        
        with self.driver.session() as session:
            for node_type, query in vector_indexes:
                try:
                    session.run(query)
                    logger.info(f"Created vector index for {node_type}")
                except Exception as e:
                    logger.error(f"Vector index creation failed for {node_type}: {e}")
                    logger.warning("Vector indexes require Neo4j 5.11+ Enterprise or AuraDB")
    
    def initialize_schema(self):
        """Initialize complete schema: constraints + indexes + vector indexes"""
        logger.info("Initializing Neo4j schema...")
        
        self.create_constraints()
        self.create_indexes()
        
        try:
            self.create_vector_indexes()
        except Exception as e:
            logger.warning(f"Vector index creation skipped: {e}")
            logger.info("Continuing without vector search (use Neo4j Enterprise or AuraDB)")
        
        logger.info("Schema initialization complete")
    
    def get_schema_info(self) -> Dict:
        """Get current schema information"""
        with self.driver.session() as session:
            # Get constraints
            constraints_result = session.run("SHOW CONSTRAINTS")
            constraints = [record.data() for record in constraints_result]
            
            # Get indexes
            indexes_result = session.run("SHOW INDEXES")
            indexes = [record.data() for record in indexes_result]
            
            return {
                "constraints": constraints,
                "indexes": indexes,
            }


if __name__ == "__main__":
    # Test schema creation
    schema_manager = Neo4jSchemaManager(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "")
        )
    )
    
    try:
        schema_manager.initialize_schema()
        
        # Print schema info
        info = schema_manager.get_schema_info()
        print(f"\nConstraints: {len(info['constraints'])}")
        print(f"Indexes: {len(info['indexes'])}")
        
    finally:
        schema_manager.close()
