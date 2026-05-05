import sys, os, time, logging
import win32com.client
import pythoncom

# Add backend to path
sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService

logging.basicConfig(level=logging.INFO)

def test_rs():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        
        # Target a specific part if possible
        target = doc
        if hasattr(doc, "Product") and doc.Product.Products.Count > 0:
            target = doc.Product.Products.Item(1)
            print(f"Targeting: {target.Name}")
        
        dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, target_obj=target, stay_open=True)
        print(f"\nRESULT: {dx} x {dy} x {dz}")
        
        if dx:
            print("!!! SUCCESS !!!")
        else:
            print("FAILED")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_rs()
