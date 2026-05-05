import win32gui
import win32con
import time
import win32com.client
import pythoncom
import re

def find_rough_stock_window():
    hw_found = []
    def enum_cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and "Rough Stock" in win32gui.GetWindowText(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(enum_cb, hw_found)
    return hw_found[0] if hw_found else 0

def get_dialog_state(hw):
    controls = []
    def cb(h, r):
        cls = win32gui.GetClassName(h)
        try:
            buf_size = 512
            buffer = win32gui.PyGetMemory(buf_size)
            len_txt = win32gui.SendMessage(h, win32con.WM_GETTEXT, buf_size, buffer)
            txt = buffer[:len_txt*2].tobytes().decode('utf-16', errors='ignore').strip().replace('\x00', '')
        except: txt = ""
        r.append((h, cls, txt))
    win32gui.EnumChildWindows(hw, cb, controls)
    
    edits = [t for h, c, t in controls if c == "Edit"]
    lb_text = ""
    for h, c, t in controls:
        if c == "ListBox" and t: lb_text = t
    
    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
    return lb_text, dim_text

def try_selection(catia, hw, body, instance, root_prod, method_name):
    print(f"\n>>> Testing Method: {method_name}")
    sel = catia.ActiveDocument.Selection
    sel.Clear()
    
    if "Activate" in method_name and instance:
        print(f"Activating {instance.Name}...")
        sel.Add(instance)
        try:
            catia.StartCommand("Activate Terminal Node")
            time.sleep(1.0)
        except: pass
        sel.Clear()

    if "WithClick" in method_name:
        btns = []
        win32gui.EnumChildWindows(hw, lambda h, r: r.append(h) if "Button" in win32gui.GetClassName(h) and "SELECT" in win32gui.GetWindowText(h).upper() else None, btns)
        if btns:
            print("Clicking 'Select' button...")
            win32gui.SendMessage(btns[0], win32con.BM_CLICK, 0, 0)
            time.sleep(0.5)

    try:
        if "AssyRef" in method_name and root_prod and instance:
            print(f"Creating Assembly Reference for {body.Name}...")
            ref = root_prod.CreateReferenceFromObject(body)
            sel.Add(ref)
        elif "InstAdd" in method_name and instance:
            print(f"Adding Instance: {instance.Name}")
            sel.Add(instance)
        else:
            print(f"Adding Body: {body.Name}")
            sel.Add(body)
    except Exception as e:
        print(f"Selection failed: {e}")
        return False

    time.sleep(1.5)
    sel_txt, dim_txt = get_dialog_state(hw)
    print(f"Result: Selection='{sel_txt}', Dim='{dim_txt}'")
    
    if dim_txt != "0mm" and dim_txt != "":
        print(f"!!! SUCCESS with {method_name} !!!")
        return True
    return False

def run_brute_force():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        
        hw = find_rough_stock_window()
        if not hw:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("CATIA")
            shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
            for _ in range(10):
                time.sleep(1)
                hw = find_rough_stock_window()
                if hw: break
        
        if not hw:
            print("Failed to open dialog.")
            return

        # Find target in the assembly
        body = None
        instance = None
        root_prod = None
        
        if hasattr(doc, "Product"):
            root_prod = doc.Product
            # Find first part instance
            for i in range(1, root_prod.Products.Count + 1):
                p = root_prod.Products.Item(i)
                try:
                    part = p.ReferenceProduct.Parent.Part
                    body = part.Bodies.Item(1)
                    instance = p
                    break
                except: continue
        else:
            body = doc.Part.Bodies.Item(1)
            instance = doc

        if not body:
            print("No test target found.")
            return

        print(f"Found Target -> Body: {body.Name}, Instance: {instance.Name if instance else 'N/A'}")

        methods = [
            "DirectBodyAdd",
            "AssyRefAdd",
            "InstAdd",
            "WithClick_DirectBodyAdd",
            "WithClick_AssyRefAdd",
            "Activate_DirectBodyAdd",
            "Activate_AssyRefAdd"
        ]
        
        for m in methods:
            if try_selection(catia, hw, body, instance, root_prod, m):
                pass # Keep going to see if others work
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_brute_force()
