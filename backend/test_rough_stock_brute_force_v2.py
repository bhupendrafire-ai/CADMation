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
        # Try WM_GETTEXT for ListBox
        buf_size = 512
        buffer = win32gui.PyGetMemory(buf_size)
        len_txt = win32gui.SendMessage(h, win32con.WM_GETTEXT, buf_size, buffer)
        txt = buffer[:len_txt*2].tobytes().decode('utf-16', errors='ignore').strip().replace('\x00', '')
        r.append((h, cls, txt))
    win32gui.EnumChildWindows(hw, cb, controls)
    
    edits = [t for h, c, t in controls if c == "Edit"]
    listbox = [t for h, c, t in controls if "ListBox" in c or "EdtPartBody" in t]
    
    sel_text = listbox[0] if listbox else "Unknown"
    dim_text = edits[2] if len(edits) > 2 else "0mm"
    # Also check if any Edit has non-zero
    for e in edits:
        if "mm" in e and e != "0mm" and e != "":
            dim_text = e
            break
            
    return sel_text, dim_text

def try_selection(catia, hw, obj, instance, method_name):
    print(f"\n>>> Testing Method: {method_name}")
    sel = catia.ActiveDocument.Selection
    sel.Clear()
    
    if "Activate" in method_name:
        print("Attempting to Activate the Part...")
        sel.Clear()
        sel.Add(instance)
        catia.StartCommand("Activate Terminal Node")
        time.sleep(1.0)
        sel.Clear()

    if "WithClick" in method_name:
        btns = []
        win32gui.EnumChildWindows(hw, lambda h, r: r.append(h) if "Button" in win32gui.GetClassName(h) and "SELECT" in win32gui.GetWindowText(h).upper() else None, btns)
        if btns:
            win32gui.SendMessage(btns[0], win32con.BM_CLICK, 0, 0)
            time.sleep(0.5)

    try:
        target = instance if "Instance" in method_name else obj
        print(f"Selecting: {target.Name}")
        sel.Add(target)
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
        
        # Trigger dialog
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

        # Find targets
        instance = None
        body = None
        
        if "Product" in str(type(doc)):
            instance = doc.Product.Products.Item(1)
            try:
                body = instance.ReferenceProduct.Parent.Part.Bodies.Item(1)
            except: pass
        else:
            instance = doc
            body = doc.Part.Bodies.Item(1)
        
        if not instance or not body:
            print("No test targets found.")
            return

        methods = [
            "Activate_InstanceAdd",
            "Activate_WithClick_InstanceAdd",
            "Activate_BodyAdd",
            "Activate_WithClick_BodyAdd"
        ]
        
        for m in methods:
            if try_selection(catia, hw, body, instance, m):
                break
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_brute_force()
