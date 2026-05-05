import win32com.client
import win32gui
import win32con
import time
import sys
import os
import ctypes

def get_text(h):
    length = win32gui.SendMessage(h, win32con.WM_GETTEXTLENGTH, 0, 0)
    if length == 0: return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    win32gui.SendMessage(h, win32con.WM_GETTEXT, length + 1, buf)
    return buf.value

def measure_v12():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Pre-find to avoid lag
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        plate = sel.Item(1).Value if sel.Count > 0 else None
        
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        axis = sel.Item(1).Value if sel.Count > 0 else None
        
        if not plate or not axis: return
        
        print(f"Plate: {plate.Name}, Axis: {axis.Name}")

        # Trigger
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(10):
            time.sleep(1)
            hw = win32gui.FindWindow(None, "Rough Stock")
            if hw: break
        
        if not hw: return
        win32gui.SetForegroundWindow(hw)

        # 1. Select Plate
        print("Selecting Plate...")
        sel.Clear()
        sel.Add(plate)
        time.sleep(1)
        
        # 2. Select Axis
        print("Selecting Axis...")
        children = []
        win32gui.EnumChildWindows(hw, lambda h, l: l.append(h), children)
        for c in children:
            if "Select" in get_text(c):
                # Click button
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        # Add Axis
        sel.Clear()
        sel.Add(axis)
        time.sleep(1)
        
        # THE KEY: Send Enter while CATIA is trapping inputs
        # This might help "commit" the selection to the active dialog field
        shell.SendKeys("{ENTER}", 0) 
        time.sleep(1)
        # Note: If Enter closed the dialog, we need to re-open or check
        
        # Click OK just in case it didn't calculate
        # for c in children:
        #     if "OK" == get_text(c):
        #         win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
        
        time.sleep(4)
        
        # Re-Find window if it closed (unlikely)
        hw = win32gui.FindWindow(None, "Rough Stock")
        if not hw:
            # Re-trigger to see if values stuck (sometimes they do)
            print("Dialog closed, re-triggering to read values...")
            shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
            for _ in range(5):
                time.sleep(1)
                hw = win32gui.FindWindow(None, "Rough Stock")
                if hw: break
        
        if not hw: return

        # SCRAPE
        print("\nFINAL RESULTS:")
        res_children = []
        win32gui.EnumChildWindows(hw, lambda h, l: l.append(h), res_children)
        for rc in res_children:
            txt = get_text(rc)
            if "mm" in txt:
                print(f"Dim: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v12()
