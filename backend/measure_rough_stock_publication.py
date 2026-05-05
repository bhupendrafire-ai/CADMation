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

def measure_publication():
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

        print("Locating Targets...")
        # 1. Body
        sel.Clear()
        sel.Search("Name='*202_LOWER PLATE*',all")
        if sel.Count == 0:
            print("202_LOWER PLATE not found.")
            return
        plate_prod = sel.Item(1).Value
        try:
            target_body = plate_prod.ReferenceProduct.Parent.Part.MainBody
        except: target_body = plate_prod
        
        # 2. Publication
        input_part = find_obj_by_name(doc.Product, "INPUT PART_01")
        ap_axis_pub = None
        if input_part:
            try:
                ap_axis_pub = input_part.Publications.Item("AP_AXIS")
            except:
                try: ap_axis_pub = input_part.ReferenceProduct.Publications.Item("AP_AXIS")
                except: pass
        
        if not ap_axis_pub:
            print("AP_AXIS Publication not found.")
            return

        print(f"Body: {target_body.Name}")
        print(f"Publication: {ap_axis_pub.Name}")

        # --- AUTOMATION SEQUENCE ---
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(0.5)

        # A. Trigger Rough Stock
        print("Triggering Rough Stock box...")
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
        
        if not hw:
            print("Rough Stock window did not appear.")
            return
        
        win32gui.SetForegroundWindow(hw)
        time.sleep(1)

        # B. Click Axis Select Button
        print("Clicking Axis 'Select' button...")
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
            time.sleep(2)
            
            # C. Select Publication
            print("Selecting AP_AXIS Publication...")
            sel.Clear()
            sel.Add(ap_axis_pub)
            time.sleep(1)
            # Some scripts toggle to ensure focus
            sel.Add(ap_axis_pub) 
            time.sleep(1)

        # D. Select Body
        print("Selecting Body...")
        sel.Clear()
        sel.Add(target_body)
        time.sleep(1)
        sel.Add(target_body)
        
        # E. Scrape results
        print("Waiting for calculation (8s)...")
        time.sleep(8)
        
        print("\n==============================")
        print("FINAL ROUGH STOCK RESULTS")
        print("==============================")
        final_children = get_children(hw)
        found_any = False
        for c in final_children:
            t = get_text(c)
            # Find values ending in mm (non-zero or containing dot)
            if "mm" in t and (any(d in t for d in "123456789") or "." in t):
                print(f"RESULT: {t}")
                found_any = True
        
        if not found_any:
            # Check for ANY label/text that looks like a dim
            for c in final_children:
                t = get_text(c)
                if any(d in t for d in "123456789") and len(t) < 30:
                    print(f"Detected Value: {t}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    measure_publication()
