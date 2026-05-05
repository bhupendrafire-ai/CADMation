import win32gui
import win32con
import time
import win32com.client
import pythoncom
import re

def find_rough_stock_window():
    hw_found = []
    def enum_cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and "Rough Stock" in win32gui.GetWindowText(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(enum_cb, hw_found)
    return hw_found[0] if hw_found else 0

def click_button(hw, btn_text):
    controls = []
    def cb(h, r):
        if win32gui.GetClassName(h) == "Button" and btn_text.upper() in win32gui.GetWindowText(h).upper():
            r.append(h)
    win32gui.EnumChildWindows(hw, cb, controls)
    if controls:
        print(f"Clicking button '{btn_text}' (HWND: {controls[0]})")
        # win32gui.PostMessage(controls[0], win32con.BM_CLICK, 0, 0)
        # Using SendMessage for more "sync" feel or just BM_CLICK
        win32gui.SendMessage(controls[0], win32con.BM_CLICK, 0, 0)
        return True
    return False

def test_selection_methods():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        hw = find_rough_stock_window()
        if not hw:
            print("Rough Stock window NOT found. Open it and run again.")
            return

        # Try to find a Body to select
        body = None
        target = doc
        if hasattr(doc, "Part"): target = doc.Part
        if hasattr(target, "Bodies") and target.Bodies.Count > 0:
            body = target.Bodies.Item(1)
            print(f"Test target body: {body.Name}")
        
        if not body:
            print("No body found in active document.")
            return

        print("\n--- Method 1: Direct Selection.Add(body) ---")
        sel.Clear()
        sel.Add(body)
        print("Selected. Check CATIA.")
        time.sleep(3)

        print("\n--- Method 2: Click 'Select' button then Selection.Add(body) ---")
        click_button(hw, "Select")
        time.sleep(1)
        sel.Clear()
        sel.Add(body)
        print("Selected. Check CATIA.")
        time.sleep(3)

        print("\n--- Method 3: Selection.Add(Reference) ---")
        try:
            ref = target.CreateReferenceFromObject(body)
            sel.Clear()
            sel.Add(ref)
            print("Reference Selected. Check CATIA.")
        except Exception as e:
            print(f"Ref creation failed: {e}")
        time.sleep(3)

        print("\n--- Method 4: Double Click ListBox then Selection.Add ---")
        # Find ListBox EdtPartBody
        # ...
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_selection_methods()
