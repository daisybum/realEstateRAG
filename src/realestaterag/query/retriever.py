"""
Graph Retriever

Cypher 쿼리 실행 및 결과 처리
"""

from typing import List, Dict, Any, Optional

from loguru import logger

from realestaterag.core.exceptions import CypherError, DatabaseConnectionError
from realestaterag.config import settings


class GraphRetriever:
    """그래프 검색기"""
    
    def __init__(self, graph=None):
        self._graph = graph
        self._connected = False
    
    @property
    def graph(self):
        """Lazy connection"""
        if self._graph is None:
            self._connect()
        return self._graph
    
    def _connect(self):
        """FalkorDB 연결"""
        try:
            from falkordb import FalkorDB
            
            db = FalkorDB(
                host=settings.falkordb_host,
                port=settings.falkordb_port,
                password=settings.falkordb_password,
            )
            self._graph = db.select_graph(settings.falkordb_graph_name)
            self._connected = True
            logger.info(f"Connected to FalkorDB: {settings.falkordb_graph_name}")
            
        except Exception as e:
            logger.error(f"FalkorDB connection failed: {e}")
            raise DatabaseConnectionError(f"Failed to connect: {e}")
    
    async def execute_queries(self, queries: List[str]) -> List[Dict[str, Any]]:
        """여러 Cypher 쿼리 실행
        
        Args:
            queries: Cypher 쿼리 목록
            
        Returns:
            결합된 결과 목록
        """
        all_results = []
        
        for query in queries:
            results = await self.execute_query(query)
            all_results.extend(results)
        
        return all_results
    
    async def execute_query(self, cypher: str) -> List[Dict[str, Any]]:
        """단일 Cypher 쿼리 실행"""
        try:
            logger.debug(f"Executing: {cypher[:100]}...")
            result = self.graph.query(cypher)
            
            if not result.result_set:
                return []
            
            # 결과 변환
            columns = result.header if hasattr(result, 'header') else \
                      [f"col_{i}" for i in range(len(result.result_set[0]))]
            
            return [
                {columns[i]: self._serialize_value(row[i]) for i in range(len(row))}
                for row in result.result_set
            ]
            
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
            raise CypherError(str(e), query=cypher)
    
    def _serialize_value(self, value: Any) -> Any:
        """값 직렬화"""
        if hasattr(value, 'properties'):
            return dict(value.properties)
        return value
    
    def get_statistics(self) -> Dict[str, int]:
        """그래프 통계 조회"""
        try:
            stats = {}
            labels = ["Region", "District", "Neighborhood", "ApartmentComplex", 
                     "Infra", "MarketSnapshot", "Report", "InvestmentAnalysis"]
            
            for label in labels:
                result = self.graph.query(f"MATCH (n:{label}) RETURN count(n)")
                if result.result_set:
                    stats[label] = result.result_set[0][0]
                else:
                    stats[label] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
