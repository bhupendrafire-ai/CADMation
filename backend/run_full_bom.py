import sys
import os
import logging
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add backend to path
sys.path.append(os.getcwd())

from app.services.bom_service import bom_service
from app.services.catia_bridge import catia_bridge

async def run_bom():
    try:
        catia = catia_bridge.get_application()
        doc = catia.ActiveDocument
        print(f"Generating BOM for: {doc.Name}")
        
        # Trigger BOM generation (this uses tree_extractor and geometry_service)
        # bom_service.generate_bom returns the file path or data
        # We'll use generate_bom_async if available, or just the direct call
        
        result = bom_service.generate_excel_bom(check_visibility=True)
        
        if result:
             print(f"\nBOM Successfully generated: {result}")

    except Exception as e:
        print(f"Error during BOM generation: {e}")

if __name__ == "__main__":
    asyncio.run(run_bom())
