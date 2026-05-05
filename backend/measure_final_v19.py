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

def measure_v19():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
        doc = caa.ActiveDocument
        sel = doc.Selection
        shell = win32com.client.Dispatch("WScript.Shell")
        
        def find_prod(root, name):
            if name.upper() in root.Name.upper(): return root
            try:
                for i in range(1, root.Products.Count + 1):
                    r = find_prod(root.Products.Item(i), name)
                    if r: return r
            except: pass
            return None

        # Targets
        input_part = find_prod(doc.Product, "INPUT PART_01")
        pub = input_part.Publications.Item("AP_AXIS") if input_part else None
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        body = None
        if sel.Count > 0:
            prod = sel.Item(1).Value
            try: body = prod.ReferenceProduct.Parent.Part.MainBody
            except: body = prod

        if not pub or not body: return

        # Trigger
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

        # 1. Select AXIS
        print("Selecting Axis...")
        children = []
        win32gui.EnumChildWindows(hw, lambda h, l: l.append(h), children)
        for c in children:
            if "Select" in get_text(c):
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                break
        
        sel.Clear()
        sel.Add(pub)
        time.sleep(1)
        shell.AppActivate("CATIA")
        shell.SendKeys("{TAB}", 0) # Tab away to commit Axis
        time.sleep(1)

        # 2. Select BODY
        print("Selecting Body...")
        sel.Clear()
        sel.Add(body)
        time.sleep(1)
        shell.AppActivate("CATIA")
        shell.SendKeys("{TAB}", 0) # Tab away to commit Body
        
        # 3. Scrape
        time.sleep(5)
        print("\nSCRAPE:")
        children = []
        win32gui.EnumChildWindows(hw, lambda h, l: l.append(h), children)
        for c in children:
            txt = get_text(c)
            if "mm" in txt:
                print(f"VAL: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v19()
