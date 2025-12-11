
import subprocess
import sys
import time
import os
from pathlib import Path

# Configuration
MAX_SAMPLES = 100
DATA_DIR = "../realEstateCrawler/output"

def get_report_ids(data_dir: str, max_samples: int = 100) -> list:
    """Get report IDs sorted by ID descending (newest first)"""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory not found: {data_dir}")
        return []
    
    # Find all numeric directories
    report_ids = []
    for item in data_path.iterdir():
        if item.is_dir() and item.name.isdigit():
            report_ids.append(item.name)
    
    # Sort descending (newest/highest ID first)
    report_ids.sort(key=lambda x: int(x), reverse=True)
    
    # Limit to max_samples
    return report_ids[:max_samples]

def run_batch():
    target_ids = get_report_ids(DATA_DIR, MAX_SAMPLES)
    total = len(target_ids)
    
    if total == 0:
        print("No reports found!")
        return
        
    print(f"Starting batch analysis for {total} reports (sorted by ID descending)...")
    
    start_time = time.time()
    success = 0
    failed = []
    
    for i, rid in enumerate(target_ids, 1):
        print(f"\n[{i}/{total}] Processing Report {rid}...")
        
        cmd = [
            "/home/sanghyun/miniforge3/envs/realEstateAnal/bin/python",
            "analysis/main_analysis.py",
            "--data_dir", DATA_DIR,
            "--output_dir", "analysis_results",
            "--report_id", rid,
            "--enable-graph"
        ]
        
        try:
            # Running without timeout as per user request (Wait indefinitely)
            result = subprocess.run(cmd, check=False)
            
            if result.returncode == 0:
                print(f"✅ Success: {rid}", flush=True)
                success += 1
            else:
                print(f"❌ Failed: {rid}", flush=True)
                failed.append(rid)
                
        except Exception as e:
            print(f"⚠️ Error: {rid} - {e}")
            failed.append(rid)

    elapsed = time.time() - start_time
    print(f"\n=== Batch Complete ===")
    print(f"Total: {total}, Success: {success}, Failed: {len(failed)}")
    print(f"Time: {elapsed:.2f}s ({elapsed/total:.2f}s per report)")
    if failed:
        print(f"Failed IDs: {failed}")

if __name__ == "__main__":
    run_batch()

