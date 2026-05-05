import win32com.client
import pythoncom
import logging
import sys
import os

# Set up logging to a dedicated file for this verification run
log_file = r"h:\CADMation\backend\verification_debug.log"
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-16'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Force rough_stock_service logger to INFO level
logging.getLogger("app.services.rough_stock_service").setLevel(logging.INFO)

# Add the backend directory to sys.path to import our services
sys.path.append(r"h:\CADMation\backend")

from app.services.rough_stock_service import RoughStockService

def verify_fix():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        print(f"Connected to {catia.Name}")
        
        doc = catia.ActiveDocument
        print(f"Active Document: {doc.Name}")
        
        # Try to find a target object (Part or Product)
        target = doc
        if hasattr(doc, "Part"):
            target = doc.Part
        
        print(f"Testing RoughStockService on: {target.Name}")
        
        dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, target_obj=target, stay_open=True)
        
        print("\n" + "="*40)
        print("VERIFICATION RESULTS")
        print("="*40)
        print(f"DX: {dx}")
        print(f"DY: {dy}")
        print(f"DZ: {dz}")
        print("="*40)
        
        if dx and dy and dz:
            print("\nSUCCESS: Dimensions captured!")
        else:
            print("\nFAILURE: Dimensions NOT captured. Check logs.")
            
    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    verify_fix()
