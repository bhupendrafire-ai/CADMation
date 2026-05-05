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
    win32gui.EnumChildWindows(hw, lambda h, r: r.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h))), controls)
    edits = [t for h, c, t in controls if c == "Edit"]
    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
    return dim_text

def run_test():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        
        # 1. Close any existing windows
        while (hw := find_rough_stock_window()):
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
            time.sleep(1)

        # 2. Find a part and its body
        part_doc = None
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if ".CATPart" in d.Name:
                part_doc = d
                break
        
        if not part_doc: return print("No Part found.")
        print(f"Target Part: {part_doc.Name}")

        # 3. ACTIVATE THE WINDOW
        found_window = False
        windows = catia.Windows
        for i in range(1, windows.Count + 1):
            w = windows.Item(i)
            if part_doc.Name in w.Caption:
                w.Activate()
                found_window = True
                print(f"Activated window: {w.Caption}")
                break
        
        if not found_window:
            print("Could not find window for part.")
            # Try activating the document's parent window anyway
            try:
                part_doc.Activate()
            except: pass

        # 4. SELECT THE BODY
        part = part_doc.Part
        body = part.Bodies.Item(1)
        sel = part_doc.Selection
        sel.Clear()
        sel.Add(body)
        print(f"Selected: {body.Name}")
        time.sleep(1)

        # 5. TRIGGER COMMAND
        print("Triggering Rough Stock...")
        catia.StartCommand("Creates rough stock")
        
        # 6. VERIFY DIMENSIONS
        for _ in range(15):
            time.sleep(1)
            hw = find_rough_stock_window()
            if hw:
                dim_txt = get_dialog_state(hw)
                print(f"Result: Dim='{dim_txt}'")
                if dim_txt != "0mm" and dim_txt != "":
                    print("!!! SUCCESS with Selection BEFORE !!!")
                    return
        print("Failed to capture non-zero dimensions.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_test()
