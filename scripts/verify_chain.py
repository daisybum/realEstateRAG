
import sys
import logging
from falkordb import FalkorDB

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_graph():
    # Connect to FalkorDB
    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph("real_estate")
    
    print("=== Graph Statistics ===")
    try:
        res = graph.query("MATCH (n) RETURN count(n) as node_count")
        print(f"Total Nodes: {res.result_set[0][0]}")
        
        res = graph.query("MATCH ()-[r]->() RETURN count(r) as rel_count")
        print(f"Total Relationships: {res.result_set[0][0]}")
    except Exception as e:
        print(f"Error querying stats: {e}")
        return

    print("\n=== Verifying Reasoning Chain (Unknown Complex -> Analysis -> Grades) ===")
    query = """
    MATCH (c:ApartmentComplex)-[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
    OPTIONAL MATCH (g:GradeMetric)-[:SUPPORTS]->(a)
    RETURN c.name, a.verdict, a.reasoning, collect(g.category + ':' + g.grade) as grades
    """
    
    try:
        res = graph.query(query)
        if not res.result_set:
            print("No reasoning chains found!")
        for row in res.result_set:
            print(f"Complex: {row[0]}")
            print(f"Verdict: {row[1]}")
            print(f"Reasoning: {row[2]}")
            print(f"Supporting Grades: {row[3]}")
            print("-" * 30)
    except Exception as e:
        print(f"Error verification query: {e}")

if __name__ == "__main__":
    verify_graph()
