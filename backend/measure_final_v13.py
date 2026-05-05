import win32com.client
import win32gui
import win32con
import time
import sys
import os
import ctypes

def get_text(hwnd):
    length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
    if length == 0: return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buf)
    return buf.value

def measure_v13():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # 1. Open Rough Stock box
        print("Opening Rough Stock box...")
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(15):
            time.sleep(1)
            hw = win32gui.FindWindow(None, "Rough Stock")
            if not hw:
                # Substring search as fallback
                def cb(h, r):
                    if "Rough Stock" in win32gui.GetWindowText(h): r.append(h)
                rs = []
                win32gui.EnumWindows(cb, rs)
                if rs: hw = rs[0]
            if hw: break
        
        if not hw:
            print("Rough Stock window not found.")
            return
        
        win32gui.SetForegroundWindow(hw)
        time.sleep(1)

        # 2. Click Select button (for Axis)
        print("Clicking 'Select' button for Axis...")
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        btn_axis = None
        for c in children:
            if "Select" in get_text(c):
                btn_axis = c
                break
        
        if not btn_axis:
            print("Select button not found.")
            return
            
        # Physical-like click simulation
        win32gui.SendMessage(btn_axis, win32con.BM_CLICK, 0, 0)
        time.sleep(1.5)

        # 3. Select AP_AXIS
        print("Locating and selecting AP_AXIS...")
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        if sel.Count == 0:
            print("AP_AXIS not found via Search.")
        else:
            axis_obj = sel.Item(1).Value
            print(f"Selection found: {axis_obj.Name}")
            # Ensure it is definitively added
            sel.Clear()
            sel.Add(axis_obj)
            time.sleep(1)
            # Some scripts toggle selection to force recognition
            sel.Add(axis_obj) 
            time.sleep(1)

        # 4. Once you select AP_AXIS, then you select the body
        print("Locating and selecting 202_LOWER PLATE...")
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count == 0:
            print("202_LOWER PLATE not found.")
        else:
            plate_obj = sel.Item(1).Value
            plate_body = None
            try:
                # Prefer MainBody if it's a Part/Product
                ref = plate_obj.ReferenceProduct
                plate_body = ref.Parent.Part.MainBody
            except: plate_body = plate_obj
            
            print(f"Adding Body to selection: {plate_body.Name}")
            sel.Clear()
            sel.Add(plate_body)
            time.sleep(1)
            sel.Add(plate_body) # Repeat for certainty
            
        # 5. Scrape sizes
        print("Waiting for calculation (5s)...")
        time.sleep(5)
        
        print("\nFINAL MEASUREMENT RESULTS:")
        final_children = get_children(hw)
        found_any = False
        for c in final_children:
            t = get_text(c)
            # Find dimensions (looks for non-zero mm or decimals)
            if "mm" in t and (any(d in t for d in "123456789") or "." in t):
                print(f"RESULT: {t}")
                found_any = True
        
        if not found_any:
            # Print everything that looks like a number just in case label is missing
            for c in final_children:
                t = get_text(c)
                if any(d in t for d in "123456789") and len(t) < 50:
                    print(f"Value found: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v13()
