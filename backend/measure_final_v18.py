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

def measure_v18():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # 1. Trigger
        print("Triggering Rough Stock...")
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

        # 2. Click Axis Select
        print("Clicking Select button...")
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        for c in children:
            if "Select" in get_text(c):
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(2)
                break
        
        # 3. SEARCH for AP_AXIS (Publication)
        print("Searching for Publication via Search tool...")
        sel.Clear()
        # The query 'Name=AP_AXIS' will find the publication
        sel.Search("Name='AP_AXIS',all")
        time.sleep(2)
        
        # 4. SEARCH for Plate
        print("Searching for Body via Search tool...")
        # Since Search returns a new selection, we don't need Clear() 
        # but we do it to be safe for the next step
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        time.sleep(5)

        # 5. SCRAPE
        print("Final Results Scrape:")
        children = get_children(hw)
        for c in children:
            txt = get_text(c)
            if "mm" in txt and "0mm" not in txt:
                print(f"FOUND: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v18()
