#!/usr/bin/env python3
"""
Ingest existing analysis JSON files into FalkorDB
"""
import json
import os
import sys
from pathlib import Path
from falkordb import FalkorDB

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphrag.graph_ingester import GraphIngesterV2

def main():
    # DB Connection
    try:
        db = FalkorDB(host='localhost', port=6379)
        graph = db.select_graph('real_estate')
    except Exception as e:
        print(f"Failed to connect to FalkorDB: {e}")
        return

    # Clear existing data
    print("Clearing existing data...")
    try:
        graph.query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        print(f"Error clearing graph: {e}")

    # Initialize Ingester
    ingester = GraphIngesterV2(graph)
    
    # Load files
    results_dir = Path("analysis_results")
    if not results_dir.exists():
        # Fallback to temp if analysis_results not found
        results_dir = Path("temp")
        
    files = sorted(results_dir.glob("*_analysis.json"))
    print(f"Found {len(files)} files in {results_dir}")

    total_stats = {
        "nodes_created": 0, 
        "relationships_created": 0, 
        "reports": 0, 
        "complexes": 0,
        "indicators": 0
    }
    
    success = 0
    failed = 0

    for f in files:
        try:
            with open(f, 'r') as fp:
                result = json.load(fp)
            
            stats = ingester.ingest_analysis_result(result)
            
            for key in total_stats:
                if key in stats:
                    total_stats[key] += stats[key]
            
            if stats.get("nodes_created", 0) > 1:
                success += 1
            else:
                failed += 1
                # print(f"Warning: {f.name} resulted in only {stats.get('nodes_created')} nodes")
                
        except Exception as e:
            print(f"Error processing {f.name}: {e}")
            failed += 1

    print(f"\n=== Ingestion Complete ===")
    print(f"Files processed: {len(files)}")
    print(f"Success: {success}")
    print(f"Failed/Partial: {failed}")
    print(f"Total nodes: {total_stats['nodes_created']}")
    print(f"Total indicators: {total_stats['indicators']}")
    print(f"Total complexes: {total_stats['complexes']}")

    # Verification Query
    print("\n=== DB Verification ===")
    try:
        counts = {}
        for label in ['Report', 'Region', 'ApartmentComplex', 'GradeMetric', 'Indicator', 'InvestmentAnalysis']:
            res = graph.query(f"MATCH (n:{label}) RETURN count(n)")
            counts[label] = res.result_set[0][0]
            print(f"{label}: {counts[label]}")
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    main()
