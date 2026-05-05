import win32com.client
import win32gui
import win32con
import time
import sys
import os
import re

def find_window_by_title(title):
    hw_found = []
    def cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and title.upper() in win32gui.GetWindowText(hwnd).upper():
            found.append(hwnd)
    win32gui.EnumWindows(cb, hw_found)
    return hw_found[0] if hw_found else 0

def get_all_child_text(hw_parent):
    results = []
    def cb(hwnd, results):
        txt = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        results.append((hwnd, cls, txt))
    win32gui.EnumChildWindows(hw_parent, cb, results)
    return results

def measure_v2():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        def find_obj_by_name(target_name):
            sel.Clear()
            sel.Search(f"Name='*{target_name}*',all")
            if sel.Count > 0:
                return sel.Item(1).Value
            return None

        print("Locating objects...")
        target_plate = find_obj_by_name("202_LOWER PLATE")
        target_axis = find_obj_by_name("AP_AXIS")
        
        if not target_plate or not target_axis:
            print(f"Error: Plate={target_plate}, Axis={target_axis}")
            return

        # 1. Trigger
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(15):
            time.sleep(0.5)
            hw = find_window_by_title("Rough Stock")
            if hw: break
        
        if not hw: return

        # 2. Automation
        children = get_all_child_text(hw)
        select_btns = [c[0] for c in children if "Select" in c[2] and c[1] == "Button"]
        
        if select_btns:
            print(f"Clicking Select button (Axis)...")
            win32gui.PostMessage(select_btns[0], win32con.BM_CLICK, 0, 0)
            time.sleep(1)
            sel.Clear()
            sel.Add(target_axis)
            time.sleep(1)
        
        print("Selecting Part...")
        sel.Clear()
        sel.Add(target_plate)
        time.sleep(3) # Wait for calc

        # 3. Scrape ALL Edit fields
        print("Scraping all fields...")
        final_children = get_all_child_text(hw)
        
        # Look for the DX, DY, DZ values
        # They are usually in 'Edit' or 'Static' controls
        dims = {}
        for h, cls, txt in final_children:
            # We're looking for patterns like "123.45mm"
            match = re.search(r'([-+]?\d*\.?\d+)\s*(mm|in)?', txt)
            if match:
                val = match.group(0)
                # Check for context (is there a label nearby?)
                # We'll just print everything that looks like a dimension
                print(f"Potential Dim: {txt} (Handle: {h})")

        # More specific DX, DY, DZ check
        # Usually they are in the order X, Y, Z or similar.
        # DX, DY, DZ are fields 6, 7, 8 in some versions or labeled.
        
        dx = dy = dz = None
        # Try to find 'DX', 'DY', 'DZ' labels then the next field
        # But for now, let's just get the most significant ones.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v2()
