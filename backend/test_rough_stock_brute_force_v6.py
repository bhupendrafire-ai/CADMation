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
    # Look for the ListBox EdtPartBody
    for h, c, t in controls:
        if "ListBox" in c and t: lb_text = t
    
    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
    return lb_text, dim_text

def try_selection(catia, hw, body, part, instance, method_name):
    print(f"\n>>> Testing Method: {method_name}")
    sel = catia.ActiveDocument.Selection
    sel.Clear()
    
    # Ensure Rough Stock is foreground
    if hw:
        win32gui.SetForegroundWindow(hw)
        time.sleep(0.5)

    if "Activate" in method_name and instance:
        print(f"Activating {instance.Name} via StartCommand...")
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
            print(f"Clicking 'Select' button (HWND: {btns[0]})")
            win32gui.SendMessage(btns[0], win32con.BM_CLICK, 0, 0)
            time.sleep(0.5)

    try:
        if "Ref" in method_name and part:
            print(f"Adding Reference to {body.Name}...")
            ref = part.CreateReferenceFromObject(body)
            sel.Add(ref)
        else:
            print(f"Adding Body directly: {body.Name}")
            sel.Add(body)
    except Exception as e:
        print(f"Selection failed: {e}")
        return False

    time.sleep(2.0) # Longer wait for refresh
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
        
        # Test StartCommand approach
        hw = find_rough_stock_window()
        if not hw:
            print("Triggering dialog via StartCommand('Creates rough stock')...")
            catia.StartCommand("Creates rough stock")
            for _ in range(10):
                time.sleep(1)
                hw = find_rough_stock_window()
                if hw: break
        
        if not hw:
            print("Failed to open dialog via StartCommand.")
            # Fallback to SendKeys
            print("Trying SendKeys as fallback...")
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("CATIA")
            time.sleep(0.5)
            shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
            for _ in range(10):
                time.sleep(1)
                hw = find_rough_stock_window()
                if hw: break
        
        if not hw:
            print("Could not open dialog at all.")
            return

        # Find target (Part 2 has one body)
        part = None
        body = None
        instance = None
        
        # Scan doc 2 or find any Part
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if hasattr(d, "Part"):
                part = d.Part
                body = part.Bodies.Item(1)
                # Try to find instance in active doc (assuming active is Product)
                if hasattr(doc, "Product"):
                    try:
                        sel = doc.Selection
                        sel.Clear()
                        sel.Search("Name=" + d.Name.replace(".CATPart", "") + ",all")
                        if sel.Count > 0:
                            instance = sel.Item(1).Value
                        sel.Clear()
                    except: pass
                break
        
        if not body:
            print("No test body found.")
            return

        print(f"Found Target -> Body: {body.Name}, Part: {part.Name}, Instance: {instance.Name if instance else 'N/A'}")

        methods = [
            "BodyAdd",
            "RefAdd",
            "WithClick_BodyAdd",
            "WithClick_RefAdd",
            "Activate_WithClick_RefAdd"
        ]
        
        for m in methods:
            if try_selection(catia, hw, body, part, instance, m):
                pass
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_brute_force()
