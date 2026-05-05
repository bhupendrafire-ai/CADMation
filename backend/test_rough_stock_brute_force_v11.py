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
            # Just use GetWindowText - it's usually fine for Edits
            t = win32gui.GetWindowText(h)
            edits.append(t)
    return edits

def try_selection(sel, hw, targets, name):
    print(f"\n--- Method: {name} ---")
    sel.Clear()
    for t in targets:
        print(f"  Adding: {t.Name if hasattr(t, 'Name') else str(t)}")
        sel.Add(t)
    time.sleep(2.0)
    edits = get_edits(hw)
    print(f"  Edits: {edits}")
    # index 2, 5, 8 are usually the DX, DY, DZ
    for i in [2, 5, 8]:
        if i < len(edits) and "mm" in edits[i] and edits[i] != "0mm" and edits[i] != "":
            print(f"!!! SUCCESS with {name} !!!")
            return True
    return False

def run_test():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        # 1. Close
        hw = find_rough_stock_window()
        if hw: win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0); time.sleep(1)

        # 2. Find Body
        body = None
        part = None
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if ".CATPart" in d.Name:
                part = d.Part; body = part.Bodies.Item(1); break
        
        if not body: return print("No body found.")
        print(f"Testing on: {part.Name} -> {body.Name}")

        # 3. Test Select BEFORE
        print("\n--- Method: Select BEFORE ---")
        sel.Clear()
        sel.Add(body)
        time.sleep(0.5)
        catia.StartCommand("Creates rough stock")
        time.sleep(3)
        hw = find_rough_stock_window()
        if hw:
            edits = get_edits(hw)
            print(f"  Edits: {edits}")
            if any(e != "0mm" and e != "" for e in edits):
                print("!!! SUCCESS with Select BEFORE !!!")
                return
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0); time.sleep(1)

        # 4. Test Select AFTER
        catia.StartCommand("Creates rough stock")
        time.sleep(3)
        hw = find_rough_stock_window()
        if not hw: return print("Dialog didn't open.")
        
        methods = [
            ("Direct Body", [body]),
            ("Part Ref", [part.CreateReferenceFromObject(body)]),
        ]
        
        for name, targets in methods:
            if try_selection(sel, hw, targets, name):
                return

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_test()
