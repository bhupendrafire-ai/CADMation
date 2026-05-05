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

def measure_v6():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Identify Body
        def find_body():
            sel.Clear()
            sel.Search("Name='*202_LOWER PLATE*',all")
            if sel.Count == 0: return None
            prod = sel.Item(1).Value
            try:
                # Resolve to PartBody/MainBody
                ref = prod.ReferenceProduct
                part = ref.Parent.Part
                print(f"Resolving to body in {part.Name}...")
                return part.MainBody
            except: return prod
        
        body = find_body()
        
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        axis = sel.Item(1).Value if sel.Count > 0 else None
        
        if not body or not axis:
            print(f"Error: Body={body}, Axis={axis}")
            return
            
        print(f"Target Body: {body.Name}")
        print(f"Target Axis: {axis.Name}")

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

        # INTERACTION
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r

        # Select Body
        print("Selecting Body...")
        # Image shows top field is for Part Body.
        # We'll just select it in tree.
        sel.Clear()
        sel.Add(body)
        time.sleep(1)
        
        # Select Axis
        print("Selecting Axis...")
        children = get_children(hw)
        for c in children:
            if "Select" in get_text(c):
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        sel.Clear()
        sel.Add(axis)
        time.sleep(5) # Calculation time

        # SCRAPE
        print("\nSCRAPING VALUES:")
        children = get_children(hw)
        for c in children:
            t = get_text(c)
            if "mm" in t:
                print(f"FOUND: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v6()
