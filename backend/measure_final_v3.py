import win32com.client
import win32gui
import win32con
import time
import sys
import os
import array

def get_text_advanced(hwnd):
    length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
    buf = array.array('u', '\0' * (length + 1))
    win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buf)
    return buf.tostring()[:-1]

def measure_v3():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # 1. Trigger
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(15):
            time.sleep(0.5)
            hw = win32gui.FindWindow(None, "Rough Stock")
            if not hw:
                # Try finding by title substring
                def cb(h, r):
                    if "Rough Stock" in win32gui.GetWindowText(h): r.append(h)
                rs = []
                win32gui.EnumWindows(cb, rs)
                if rs: hw = rs[0]
            if hw: break
        
        if not hw:
            print("Rough Stock window not found.")
            return

        # 2. Automation
        def get_children(parent):
            res = []
            win32gui.EnumChildWindows(parent, lambda h, l: l.append(h), res)
            return res

        children = get_children(hw)
        for c in children:
            txt = get_text_advanced(c)
            if "Select" in txt:
                print(f"Clicking Select button (Handle: {c})...")
                win32gui.PostMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        # Assuming Axis is selected after clicking first Select found (based on image)
        # Selection
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        if sel.Count > 0:
            print("Axis selected.")
        
        time.sleep(1)
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count > 0:
            print("Plate selected.")
        
        time.sleep(3) # Wait for calc

        # 3. Scrape ALL Edit fields
        print("\nSCRAPING RESULTS...")
        children = get_children(hw)
        for idx, c in enumerate(children):
            txt = get_text_advanced(c)
            # Find dimensions
            if "mm" in txt or "in" in txt or any(char.isdigit() for char in txt):
                print(f"[{idx}] {win32gui.GetClassName(c)}: '{txt}'")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v3()
