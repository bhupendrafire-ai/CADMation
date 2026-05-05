import win32com.client
import win32gui
import win32con
import time
import sys
import os

# Add backend to path for services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.services.rough_stock_service import RoughStockService

def find_window_by_title(title):
    hw_found = []
    def cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and title.upper() in win32gui.GetWindowText(hwnd).upper():
            found.append(hwnd)
    win32gui.EnumWindows(cb, hw_found)
    return hw_found[0] if hw_found else 0

def click_button_by_text(hw_parent, text_substring):
    btns = []
    def cb(hwnd, btns):
        if win32gui.GetClassName(hwnd) == "Button":
            if text_substring.upper() in win32gui.GetWindowText(hwnd).upper():
                btns.append(hwnd)
    win32gui.EnumChildWindows(hw_parent, cb, btns)
    if btns:
        # Click the first one found
        win32gui.PostMessage(btns[0], win32con.BM_CLICK, 0, 0)
        return True
    return False

def measure_request():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # 0. Find targets
        def find_product(prod, name):
            if name.upper() in prod.Name.upper() or name.upper() in prod.PartNumber.upper():
                return prod
            try:
                for i in range(1, prod.Products.Count + 1):
                    r = find_product(prod.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        print("Locating targets...")
        input_part = find_product(doc.Product, "INPUT PART_01")
        lower_plate = find_product(doc.Product, "202_LOWER PLATE")
        
        if not input_part or not lower_plate:
            print("Required parts not found.")
            return

        # Find AP_AXIS
        ap_axis = None
        try:
            ref = input_part.ReferenceProduct
            part = ref.Parent.Part
            for i in range(1, part.AxisSystems.Count + 1):
                ax = part.AxisSystems.Item(i)
                if "AP_AXIS" in ax.Name.upper():
                    ap_axis = ax
                    break
        except: pass

        if not ap_axis:
            print("AP_AXIS not found.")
            return

        print(f"Targets: Axis={ap_axis.Name}, Part={lower_plate.Name}")

        # 1. Start Rough Stock
        print("Starting Rough Stock command...")
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        # 2. Find Window
        hw = 0
        for _ in range(20):
            time.sleep(0.5)
            hw = find_window_by_title("Rough Stock")
            if hw: break
        
        if not hw:
            print("Rough Stock window did not appear.")
            return

        # 3. Handle Axis Selection (as requested: "click the select button... and then select...")
        # In CATIA Rough Stock dialog, there are often multiple "selection" buttons.
        # We'll try to find the "Select" button for the Axis field.
        # Typically the "Axis" field label is followed by a button.
        
        print("Clicking Select button (Axis)...")
        # We'll rely on the user's workflow: Axis first, then Part.
        # Often the first 'Select' button is for the Product/Part, second for Axis.
        # However, we'll try to be smart or just select them sequentially.
        
        # We'll use the Selection API to "select" the items.
        sel.Clear()
        sel.Add(ap_axis)
        time.sleep(1) # Wait for CATIA to register
        
        print("Selecting 202_LOWER PLATE...")
        sel.Clear()
        sel.Add(lower_plate)
        time.sleep(2) # Give it time to calculate

        # 4. Scrape Dimensions
        print("Scraping results...")
        dx, dy, dz = RoughStockService._scrape_current_window_dims(hw)
        print(f"\nRESULT: {dx} x {dy} x {dz}")
        
        # Keep window open as requested for "rough stock method"
        # win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_request()
