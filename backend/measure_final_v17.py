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

def measure_v17():
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

        # 1. Locate Publication
        print("Locating AP_AXIS Publication...")
        input_part = find_prod(doc.Product, "INPUT PART_01")
        if not input_part:
            print("INPUT PART_01 not found.")
            return

        pub = None
        try:
            pub = input_part.Publications.Item("AP_AXIS")
        except:
            try: pub = input_part.ReferenceProduct.Publications.Item("AP_AXIS")
            except: pass
            
        if not pub:
            print("Publication 'AP_AXIS' not found.")
            return

        print(f"Publication Found: {pub.Name}")

        # 2. Trigger
        print("Triggering Rough Stock...")
        shell.AppActivate("CATIA")
        time.sleep(0.5)
        shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
        
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
        
        if not hw: return
        win32gui.SetForegroundWindow(hw)

        # 3. Click Select (Axis)
        print("Clicking Select button...")
        def get_children(p):
            r = []
            win32gui.EnumChildWindows(p, lambda h, l: l.append(h), r)
            return r
            
        children = get_children(hw)
        for c in children:
            if "Select" in get_text(c):
                win32gui.SendMessage(c, win32con.BM_CLICK, 0, 0)
                time.sleep(1.5)
                break
        
        # 4. SELECT PUBLICATION
        print("Adding Publication to selection...")
        sel.Clear()
        sel.Add(pub)
        time.sleep(1)
        # Commit trick: Send space then Enter while CATIA has focus
        shell.AppActivate("CATIA")
        shell.SendKeys(" ", 0)
        time.sleep(0.5)
        # shell.SendKeys("{ENTER}", 0) # Danger: might close dialog
        
        # 5. SELECT BODY
        print("Selecting Body...")
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

        # 6. SCRAPE
        print("Waiting for results...")
        time.sleep(10) # Longer wait
        children = get_children(hw)
        for c in children:
            txt = get_text(c)
            if "mm" in txt:
                print(f"RESULT: {txt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_v17()
