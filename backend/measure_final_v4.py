import win32com.client
import win32gui
import win32con
import time
import sys
import os
import ctypes

def get_text_ctypes(hwnd):
    length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
    if length == 0: return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buf)
    return buf.value

def measure_v4():
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
                def cb(h, r):
                    if "Rough Stock" in win32gui.GetWindowText(h): r.append(h)
                rs = []
                win32gui.EnumWindows(cb, rs)
                if rs: hw = rs[0]
            if hw: break
        
        if not hw: return

        # 2. Automation
        def get_children(parent):
            res = []
            win32gui.EnumChildWindows(parent, lambda h, l: l.append(h), res)
            return res

        children = get_children(hw)
        for c in children:
            txt = get_text_ctypes(c)
            if "Select" in txt:
                win32gui.PostMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        time.sleep(1)
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        time.sleep(3) # Wait for calc

        # 3. Scrape
        print("\nFINAL MEASUREMENTS:")
        final_children = get_children(hw)
        dims = []
        for c in final_children:
            txt = get_text_ctypes(c)
            # Find values ending in mm
            if "mm" in txt:
                dims.append(txt)
                print(f"Dim Field: {txt}")

        # In most Rough Stock dialogs, the last 3 'mm' values are DX, DY, DZ.
        if len(dims) >= 3:
            print("\n==============================")
            print("REPORTED ROUGH STOCK DIMS:")
            print(f"DX: {dims[-3]}")
            print(f"DY: {dims[-2]}")
            print(f"DZ: {dims[-1]}")
            print("==============================")
        else:
            print("Not enough dimensions found in dialog.")
        
        # Don't close so user can see
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v4()
