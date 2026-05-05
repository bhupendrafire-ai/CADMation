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
    listbox = [t for h, c, t in controls if "ListBox" in c or "EdtPartBody" in t]
    
    # Check ListBox for any text (not just the name listbox)
    lb_text = ""
    for h, c, t in controls:
        if c == "ListBox" and t:
            lb_text = t
            break

    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
            
    return lb_text or (listbox[0] if listbox else ""), dim_text

def try_selection(catia, hw, body, instance, method_name):
    print(f"\n>>> Testing Method: {method_name}")
    sel = catia.ActiveDocument.Selection
    sel.Clear()
    
    if "Activate" in method_name:
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
        target = instance if "Instance" in method_name else body
        print(f"Selecting: {target.Name}")
        sel.Add(target)
    except Exception as e:
        print(f"Selection failed: {e}")
        return False

    time.sleep(1.5)
    sel_txt, dim_txt = get_dialog_state(hw)
    print(f"Result: Selection='{sel_txt}', Dim='{dim_txt}'")
    
    if dim_txt != "0mm" and dim_txt != "":
        print(f"!!! SUCCESS !!!")
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

        # Improved Target Finding
        instance = None
        body = None
        
        if "Product" in str(type(doc)):
            # Find the first real Part instance
            for i in range(1, doc.Product.Products.Count + 1):
                p = doc.Product.Products.Item(i)
                try:
                    # Check if it has a Part
                    part = p.ReferenceProduct.Parent.Part
                    instance = p
                    body = part.Bodies.Item(1)
                    break
                except: continue
        else:
            instance = doc
            body = doc.Part.Bodies.Item(1)
        
        if not instance or not body:
            print("No test targets found.")
            return

        print(f"Test Targets -> Instance: {instance.Name}, Body: {body.Name}")

        methods = [
            "BodyAdd",
            "WithClick_BodyAdd",
            "InstanceAdd",
            "WithClick_InstanceAdd",
            "Activate_BodyAdd",
            "Activate_WithClick_BodyAdd",
            "Activate_InstanceAdd",
            "Activate_WithClick_InstanceAdd"
        ]
        
        for m in methods:
            if try_selection(catia, hw, body, instance, m):
                # Don't break, try all to be sure
                pass
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_brute_force()
