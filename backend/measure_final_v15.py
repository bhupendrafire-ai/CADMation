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

def measure_v15():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        
        def find_obj_by_name(root, target_name):
            if target_name.upper() in root.Name.upper(): return root
            try:
                for i in range(1, root.Products.Count + 1):
                    r = find_obj_by_name(root.Products.Item(i), target_name)
                    if r: return r
            except: pass
            return None

        # 1. Pre-find targets
        plate = find_obj_by_name(doc.Product, "202_LOWER PLATE")
        input_part = find_obj_by_name(doc.Product, "INPUT PART_01")
        if not plate or not input_part: return

        pub = None
        try: pub = input_part.Publications.Item("AP_AXIS")
        except: pass
        
        if not pub: return

        # 2. SELECT AXIS FIRST
        print("Pre-selecting AP_AXIS Publication...")
        sel.Clear()
        sel.Add(pub)
        time.sleep(1)

        # 3. TRIGGER COMMAND
        print("Triggering Rough Stock...")
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
        # 4. FIND WINDOW
        hw = 0
        for _ in range(15):
            time.sleep(1)
            hw = win32gui.FindWindow(None, "Rough Stock")
            if not hw:
                def cb(h, r):
                   if "Rough Stock" in win32gui.GetWindowText(h): r.append(h)
                rs = []
                win32gui.EnumWindows(cb, rs)
                if rs: hw = rs[0]
            if hw: break
        
        if not hw:
            print("Window not found.")
            return
        
        win32gui.SetForegroundWindow(hw)
        time.sleep(1)

        # 5. SELECT BODY
        print("Selecting Body...")
        # Resolve to MainBody
        try: target_body = plate.ReferenceProduct.Parent.Part.MainBody
        except: target_body = plate
        
        sel.Clear()
        sel.Add(target_body)
        time.sleep(5)

        # 6. SCRAPE
        print("\nFINAL SCAN:")
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        for c in children:
            t = get_text(c)
            if "mm" in t:
                print(f"FOUND: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v15()
