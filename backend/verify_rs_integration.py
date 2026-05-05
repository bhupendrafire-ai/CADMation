import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Mock app structure for testing if needed, but here we can just import from h:\CADMation\backend
sys.path.append(os.path.join(os.getcwd(), "app"))
sys.path.append(os.getcwd())

from app.services.geometry_service import geometry_service
from app.services.catia_bridge import catia_bridge

def main():
    try:
        catia = catia_bridge.get_application()
        part_doc = catia.ActiveDocument
        part = part_doc.Part
        
        print(f"Testing GeometryService on: {part.Name}")
        
        # Trigger measurement
        # This should hit TIER 0 first
        bbox = geometry_service.get_bounding_box(part)
        
        print("\n--- MEASUREMENT RESULT ---")
        print(f"Stock Size: {bbox.get('stock_size')}")
        print(f"Raw Dims: {bbox.get('x')} x {bbox.get('y')} x {bbox.get('z')}")
        
        if bbox.get('x') == 140.0 and bbox.get('y') == 100.0:
            print("\nSUCCESS: Matches Rough Stock expected values!")
        else:
            print("\nWARNING: Values do not match expected '140 x 100 x 145.03'. Check if window was open.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
