import win32com.client
import win32gui
import win32con
import time
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.services.rough_stock_service import RoughStockService

def find_window_by_title(title):
    hw_found = []
    def cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and title.upper() in win32gui.GetWindowText(hwnd).upper():
            found.append(hwnd)
    win32gui.EnumWindows(cb, hw_found)
    return hw_found[0] if hw_found else 0

def final_measurement():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        print("Locating final targets...")
        
        # 1. Locate AP_AXIS (using the confirmed location)
        adapter_die = find_product(doc.Product, "ADAPTER_LOWER_AND_UPPER_DIE")
        ap_axis = None
        if adapter_die:
            try:
                ref = adapter_die.ReferenceProduct
                part = ref.Parent.Part
                for i in range(1, part.AxisSystems.Count + 1):
                    ax = part.AxisSystems.Item(i)
                    if "AP_AXIS" in ax.Name.upper():
                        ap_axis = ax
                        break
            except: pass
        
        if not ap_axis:
            # Global search as fallback
            print("Axis not found in adapter, searching globally...")
            def global_axis_search(prod):
                try:
                    ref = prod.ReferenceProduct
                    part = ref.Parent.Part
                    for i in range(1, part.AxisSystems.Count + 1):
                        ax = part.AxisSystems.Item(i)
                        if "AP_AXIS" in ax.Name.upper(): return ax
                except: pass
                try:
                    for i in range(1, prod.Products.Count + 1):
                        r = global_axis_search(prod.Products.Item(i))
                        if r: return r
                except: pass
                return None
            ap_axis = global_axis_search(doc.Product)

        # 2. Locate 202_LOWER PLATE
        lower_plate = find_product(doc.Product, "202_LOWER PLATE")
        
        if not ap_axis or not lower_plate:
            print(f"Error: Axis={ap_axis}, Plate={lower_plate}")
            return

        print(f"Selecting Axis: {ap_axis.Name} (from {ap_axis.Parent.Parent.Name})")
        print(f"Selecting Plate: {lower_plate.Name}")

        # 3. Trigger Command
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(15):
            time.sleep(0.5)
            hw = find_window_by_title("Rough Stock")
            if hw: break
        
        if not hw:
            print("Rough Stock window did not appear.")
            return

        print("Interacting with dialog...")
        # Most reliable way in a "black box" dialog is to set the selection items 
        # while the dialog is waiting for input.
        
        # User said: "click the select button... and then select the 202_LOWER PLATE"
        # We'll simulate this by adding them to the selection while CATIA is active.
        
        sel.Clear()
        sel.Add(ap_axis)
        time.sleep(1)
        
        sel.Clear()
        sel.Add(lower_plate)
        time.sleep(3) # Wait for calc

        # SCRAPE
        dx, dy, dz = RoughStockService._scrape_current_window_dims(hw)
        print(f"\n==============================")
        print(f"FINAL ROUGH STOCK DIMENSIONS")
        print(f"==============================")
        print(f"X: {dx} mm")
        print(f"Y: {dy} mm")
        print(f"Z: {dz} mm")
        print(f"Size String: {dx} x {dy} x {dz}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_measurement()
