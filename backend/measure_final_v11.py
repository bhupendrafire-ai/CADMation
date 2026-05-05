import win32com.client
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.services.rough_stock_service import RoughStockService

def measure_v11():
    try:
        # Set the axis substring for RoughStockService to pick up
        os.environ["CADMATION_STOCK_AXIS_SUBSTRING"] = "AP_AXIS"
        
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        
        def find_obj_by_name(target_name):
            sel = doc.Selection
            sel.Clear()
            sel.Search(f"Name='*{target_name}*',all")
            if sel.Count > 0:
                return sel.Item(1).Value
            return None

        print("Locating objects...")
        target_plate = find_obj_by_name("202_LOWER PLATE")
        if not target_plate:
            print("202_LOWER PLATE not found.")
            return
            
        # Resolve to MainBody for the service
        try:
            target_obj = target_plate.ReferenceProduct.Parent.Part.MainBody
        except: target_obj = target_plate

        print(f"Target object for service: {target_obj.Name}")

        # Run the service's measurement
        # It should find AP_AXIS and use the SPA-axis-aligned calculation
        dx, dy, dz = RoughStockService.get_rough_stock_dims(caa, target_obj=target_obj, stay_open=True)
        
        print(f"\n==============================")
        print(f"ROUGH STOCK SERVICE RESULTS")
        print(f"==============================")
        print(f"DX: {dx}")
        print(f"DY: {dy}")
        print(f"DZ: {dz}")
        if dx and dy and dz:
            dims = sorted([dx, dy, dz], reverse=True)
            print(f"Final Size: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")
        else:
            print("Measurement returned None. Falling back to default search.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v11()
