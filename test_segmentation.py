import os
import sys
import time
from pathlib import Path

# Add backend root to sys.path so we can import modules
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from services.manual_processor import start_manual_processing, get_job_status
from services.db import _ensure_table_exists

def test_manual_processing():
    # 1. Ensure DB table exists
    _ensure_table_exists()

    # 2. Locate the sample PDF
    pdf_path = backend_dir / "public" / "manuals" / "installation & assembly-2.pdf"
    if not pdf_path.exists():
        print(f"Error: Sample PDF not found at {pdf_path}")
        return

    print(f"Starting processing for: {pdf_path.name}")
    
    # 3. Start processing
    unique_suffix = int(time.time())
    job_id = start_manual_processing(
        file_path=pdf_path,
        name=f"Test Manual {unique_suffix}",
        slug=f"test-manual-{unique_suffix}",
        description="Testing step segmentation with magenta borders"
    )
    
    print(f"Job started! ID: {job_id}")
    
    # 4. Poll for status
    while True:
        status = get_job_status(job_id)
        if not status:
            print("Job status not found.")
            break
            
        current_status = status.get("status")
        print(f"Status: {current_status}...")
        
        if current_status == "completed":
            manual_id = status.get("manual_id")
            step_count = status.get("step_count")
            print(f"\n✅ Processing complete!")
            print(f"Manual ID: {manual_id}")
            print(f"Steps created: {step_count}")
            print(f"Images saved to: wayfair_studio_backend/public/manuals/{manual_id}/")
            break
        elif current_status == "failed":
            print(f"\n❌ Processing failed: {status.get('error')}")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    if not os.getenv("REPLICATE_API_TOKEN"):
        print("Error: REPLICATE_API_TOKEN is not set in environment.")
    else:
        test_manual_processing()
