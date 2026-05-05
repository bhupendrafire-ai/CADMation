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

def measure_v9():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Identify Targets
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        body = None
        if sel.Count > 0:
            prod_plate = sel.Item(1).Value
            try: body = prod_plate.ReferenceProduct.Parent.Part.MainBody
            except: body = prod_plate
            
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        axis = sel.Item(1).Value if sel.Count > 0 else None
        
        if not body or not axis: return
            
        print(f"Body: {body.Name}, Axis: {axis.Name}")

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
        time.sleep(1)

        # SELECT BODY
        print("Selecting Body...")
        sel.Clear()
        sel.Add(body)
        time.sleep(1)
        print(f"Selection Count (after Body): {sel.Count}")

        # Find Axis Select Button
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        btn_select = None
        for c in children:
            if "Select" in get_text(c):
                btn_select = c
                break
        
        if btn_select:
            print("Clicking 'Select' button for Axis...")
            win32gui.SendMessage(btn_select, win32con.BM_CLICK, 0, 0)
            time.sleep(1)
            
            print("Selecting Axis...")
            sel.Clear()
            sel.Add(axis)
            time.sleep(1)
            print(f"Selection Count (after Axis): {sel.Count}")
            if sel.Count > 0:
                print(f"Selected Object: {sel.Item(1).Value.Name}")

        # WAIT FOR CALC
        print("Waiting for calculation...")
        time.sleep(5)

        # SCRAPE
        print("\nSCRAPING VALUES:")
        final_children = get_children(hw)
        for c in final_children:
            t = get_text(c)
            # Rough stock values are usually 'Edit' or 'Static'
            if "mm" in t:
                print(f"Result: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v9()
