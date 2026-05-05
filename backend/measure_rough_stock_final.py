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

def get_child_buttons(hw_parent):
    btns = []
    def cb(hwnd, btns):
        if win32gui.GetClassName(hwnd) == "Button":
            btns.append((hwnd, win32gui.GetWindowText(hwnd)))
    win32gui.EnumChildWindows(hw_parent, cb, btns)
    return btns

def measure_final_manual():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        def find_obj_by_name(prod, target_name):
            if target_name.upper() in prod.Name.upper() or target_name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_obj_by_name(prod.Products.Item(i), target_name)
                    if r: return r
            except: pass
            return None

        print("Locating objects in tree...")
        target_plate = find_obj_by_name(doc.Product, "202_LOWER PLATE")
        
        # Robust search for AP_AXIS
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        target_axis = None
        if sel.Count > 0:
            target_axis = sel.Item(1).Value
        sel.Clear()

        if not target_plate or not target_axis:
            print(f"Error: Plate={target_plate}, Axis={target_axis}")
            return

        print(f"Target Plate: {target_plate.Name}")
        print(f"Target Axis: {target_axis.Name}")

        # 1. Trigger Rough Stock
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        print("Triggering Rough Stock...")
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(20):
            time.sleep(0.5)
            hw = find_window_by_title("Rough Stock")
            if hw: break
        
        if not hw:
            print("Rough Stock window did not appear.")
            return

        print(f"Found Window: {hw}")
        time.sleep(1)

        # 2. Identify Buttons
        btns = get_child_buttons(hw)
        print(f"Child buttons found: {[b[1] for b in btns]}")
        
        # Based on the image, there are two "Select" buttons. 
        # The first is for Part, the second is for Axis.
        select_btns = [b[0] for b in btns if "Select" in b[1]]
        
        if len(select_btns) < 2:
            print("Could not find both Select buttons.")
            # Fallback: just try to select items directly
        else:
            # Click Axis Select Button (the second one)
            print("Clicking Axis 'Select' button...")
            win32gui.PostMessage(select_btns[1], win32con.BM_CLICK, 0, 0)
            time.sleep(1)
            
            # Select the Axis in tree
            sel.Clear()
            sel.Add(target_axis)
            time.sleep(1)
            
            # Click Part Select Button (the first one)
            print("Clicking Part 'Select' button...")
            win32gui.PostMessage(select_btns[0], win32con.BM_CLICK, 0, 0)
            time.sleep(1)
            
            # Select the Plate in tree
            sel.Clear()
            sel.Add(target_plate)
            time.sleep(2)

        # 3. Scrape Results
        print("Scraping dimensions...")
        dx, dy, dz = RoughStockService._scrape_current_window_dims(hw)
        
        print(f"\n==============================")
        print(f"MEASUREMENT RESULTS")
        print(f"==============================")
        print(f"Method: Rough Stock (with AP_AXIS)")
        print(f"X (DX): {dx} mm")
        print(f"Y (DY): {dy} mm")
        print(f"Z (DZ): {dz} mm")
        print(f"Stock Size: {dx} x {dy} x {dz}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_final_manual()
