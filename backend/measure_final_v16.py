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

def measure_v16():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # 1. Start Command
        print("Triggering Rough Stock...")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        time.sleep(1)

        # 2. SELECT AXIS Publication
        # We need to find it precisely
        print("Searching for AP_AXIS Publication...")
        sel.Clear()
        # Search for publication specifically
        sel.Search("Name='*AP_AXIS*',all")
        
        found_pub = None
        if sel.Count > 0:
            for i in range(1, sel.Count + 1):
                item = sel.Item(i).Value
                # Verify it's a Publication
                if hasattr(item, "ValuatedElement"):
                    found_pub = item
                    break
        
        if not found_pub:
            print("Could not find a valid Publication for AP_AXIS.")
            return

        print(f"Selection found: {found_pub.Name}")
        
        # Find the "Select" button first? User said "the dialog stays hidden" if not selected.
        # This implies maybe we select AFTER the command but the window is invisible?
        
        # ACTION: FORCE SELECTION
        sel.Clear()
        sel.Add(found_pub)
        time.sleep(1)
        # Force a refresh or interaction
        shell.AppActivate("CATIA")
        # Send a Space - this often "clicks" the highlighted tree item
        shell.SendKeys(" ", 0)
        time.sleep(1)
        
        # Look for window
        hw = 0
        for _ in range(10):
            hw = win32gui.FindWindow(None, "Rough Stock")
            if not hw:
                def cb(h, r):
                    if "Rough Stock" in win32gui.GetWindowText(h): r.append(h)
                rs = []
                win32gui.EnumWindows(cb, rs)
                if rs: hw = rs[0]
            if hw: break
            time.sleep(1)
            # Try selecting again every second
            sel.Clear()
            sel.Add(found_pub)
            shell.SendKeys(" ", 0)

        if not hw:
            print("Rough Stock window still hidden.")
            return

        print(f"Found Window: {hw}")
        win32gui.SetForegroundWindow(hw)

        # 3. SELECT BODY
        print("Selecting 202_LOWER PLATE...")
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count > 0:
            target = sel.Item(1).Value
            try: target = target.ReferenceProduct.Parent.Part.MainBody
            except: pass
            sel.Clear()
            sel.Add(target)
            time.sleep(1)
            shell.SendKeys(" ", 0)
        
        # 4. SCRAPE
        print("Waiting for results...")
        time.sleep(5)
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        for c in children:
            txt = get_text(c)
            if "mm" in txt:
                print(f"Result Field: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v16()
