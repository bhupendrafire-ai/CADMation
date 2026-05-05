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

def measure_v5():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        # Trigger
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for _ in range(15):
            time.sleep(0.5)
            hw = win32gui.FindWindow(None, "Rough Stock")
            if hw: break
        
        if not hw: return
        win32gui.SetForegroundWindow(hw)

        def get_children(parent):
            res = []
            win32gui.EnumChildWindows(parent, lambda h, l: l.append(h), res)
            return res

        # 1. Select PART
        print("Activating Part selection...")
        children = get_children(hw)
        for c in children:
            txt = get_text_ctypes(c)
            cls = win32gui.GetClassName(c)
            # The top input is usually an 'Edit' control or 'Combo'
            if "No Selection" in txt:
                win32gui.SendMessage(c, win32con.WM_LBUTTONDOWN, 0, 0)
                win32gui.SendMessage(c, win32con.WM_LBUTTONUP, 0, 0)
                time.sleep(1)
                break
        
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        time.sleep(1)

        # 2. Select AXIS
        print("Activating Axis selection...")
        children = get_children(hw)
        for c in children:
            txt = get_text_ctypes(c)
            if "Select" in txt:
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        sel.Clear()
        sel.Search("Name='AP_AXIS',all")
        time.sleep(5) # Long wait for calc

        # 3. Scrape
        print("\nFINAL MEASUREMENTS:")
        final_children = get_children(hw)
        for c in final_children:
            txt = get_text_ctypes(c)
            if "mm" in txt and not "0mm" == txt:
                print(f"Result Field: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v5()
