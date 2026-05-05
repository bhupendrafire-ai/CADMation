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

def measure_v7():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Identify Targets
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        body = None
        if sel.Count > 0:
            prod = sel.Item(1).Value
            try: body = prod.ReferenceProduct.Parent.Part.MainBody
            except: body = prod
            
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        axis = sel.Item(1).Value if sel.Count > 0 else None
        
        if not body or not axis:
            print(f"Error: Body={body}, Axis={axis}")
            return
            
        print(f"Target Body: {body.Name}")
        print(f"Target Axis: {axis.Name}")

        # 1. Trigger Dialog
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

        # 2. Select BODY First (before Axis mode)
        print("Selecting Body...")
        sel.Clear()
        sel.Add(body)
        time.sleep(2)
        
        # 3. Enter Axis Mode
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
        
        if btn_axis:
            win32gui.SendMessage(btn_axis, win32con.BM_CLICK, 0, 0)
            time.sleep(1)
            
            print("Adding Axis to selection...")
            sel.Clear()
            sel.Add(axis)
            time.sleep(2)
            
            # Check if Axis selection "sticks" - sometimes we need to select something else or enter
            # shell.SendKeys("{ENTER}", 0) 
            # no, ENTER closes the dialog

        # 4. Scrape
        print("\nSCRAPING RESULTS:")
        time.sleep(5)
        final_children = get_children(hw)
        for c in final_children:
            t = get_text(c)
            if "mm" in t:
                print(f"Field Found: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v7()
