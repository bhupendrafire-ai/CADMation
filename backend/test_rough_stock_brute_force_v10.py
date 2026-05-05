import win32gui
import win32con
import time
import win32com.client
import pythoncom
import re

def find_rough_stock_window():
    hw_found = []
    def enum_cb(hwnd, found):
        if "Rough Stock" in win32gui.GetWindowText(hwnd): found.append(hwnd)
    win32gui.EnumWindows(enum_cb, hw_found)
    return hw_found[0] if hw_found else 0

def get_edits(hw):
    controls = []
    win32gui.EnumChildWindows(hw, lambda h, r: r.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h))), controls)
    edits = []
    for h, c, t in controls:
        if c == "Edit":
            buf = win32gui.PyGetMemory(512)
            len_t = win32gui.SendMessage(h, win32con.WM_GETTEXT, 512, buf)
            txt = buf[:len_t*2].tobytes().decode('utf-16', errors='ignore').strip().replace('\x00', '')
            edits.append(txt)
    return edits

def try_everything():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        # 1. Close Window
        hw = find_rough_stock_window()
        if hw: win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0); time.sleep(1)

        # 2. Find a Body and Instance
        part = None
        body = None
        instance = None
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if ".CATPart" in d.Name:
                part = d.Part
                body = part.Bodies.Item(1)
                break
        
        if not body: return print("No body found.")
        print(f"Testing on: {part.Name} -> {body.Name}")

        # 3. Open Dialog
        catia.StartCommand("Creates rough stock")
        time.sleep(2)
        hw = find_rough_stock_window()
        if not hw: return print("Dialog didn't open.")

        win32gui.SetForegroundWindow(hw)
        time.sleep(0.5)

        # 4. Try Selection Methods
        methods = [
            ("Direct Body", [body]),
            ("Part Ref", [part.CreateReferenceFromObject(body)]),
            ("Product + Body", [doc.Product.Products.Item(1), body] if hasattr(doc, "Product") else [body]),
        ]

        for name, targets in methods:
            print(f"\n--- Method: {name} ---")
            sel.Clear()
            for t in targets:
                print(f"  Adding: {t.Name if hasattr(t, 'Name') else str(t)}")
                sel.Add(t)
            time.sleep(1.5)
            edits = get_edits(hw)
            print(f"  Edits: {edits}")
            if any(e != "0mm" and e != "" for e in edits):
                print(f"!!! SUCCESS with {name} !!!")
                return

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    try_everything()
