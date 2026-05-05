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

def measure_v10():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Identify Targets
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count == 0: return
        body = sel.Item(1).Value
        try: body = body.ReferenceProduct.Parent.Part.MainBody
        except: pass
            
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        axis = sel.Item(1).Value if sel.Count > 0 else None
        
        if not body or not axis: return
            
        print(f"Pre-selecting Body: {body.Name} and Axis: {axis.Name}")
        sel.Clear()
        sel.Add(body)
        sel.Add(axis)
        time.sleep(1)

        # Trigger Dialog
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
        time.sleep(3) # Wait for auto-calc

        # SCRAPE
        print("\nSCRAPING VALUES:")
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        final_children = get_children(hw)
        for c in final_children:
            t = get_text(c)
            if "mm" in t and "0mm" not in t:
                print(f"Result: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v10()
