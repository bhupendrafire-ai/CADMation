import logging
import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.services.bom_service import bom_service

logging.basicConfig(level=logging.INFO)

def test_bom():
    print("--- Testing BOM Generation ---")
    file_path = bom_service.generate_excel_bom()
    
    if file_path and os.path.exists(file_path):
        print(f"SUCCESS: BOM generated at {file_path}")
        # Let's check some content if possible
        import pandas as pd
        mfg = pd.read_excel(file_path, sheet_name='MFG ITEM')
        std = pd.read_excel(file_path, sheet_name='STD ITEM')
        print(f"MFG Items Found: {len(mfg)}")
        print(f"STD Items Found: {len(std)}")
        if len(mfg) > 0:
            print("Sample MFG Data:")
            print(mfg.head(3).to_string())
    else:
        print("FAILED: BOM generation returned None or file missing.")

if __name__ == "__main__":
    test_bom()
