import win32gui
import win32con
import time
import win32com.client
import pythoncom
import ctypes

def find_rough_stock_window():
    hw_found = []
    def enum_cb(hwnd, found):
        if "Rough Stock" in win32gui.GetWindowText(hwnd): found.append(hwnd)
    win32gui.EnumWindows(enum_cb, hw_found)
    return hw_found[0] if hw_found else 0

def get_control_text(hwnd):
    length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(length + 1)
    win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buf)
    return buf.value

def get_all_controls(hw):
    controls = []
    def cb(h, r):
        cls = win32gui.GetClassName(h)
        txt = get_control_text(h)
        r.append((h, cls, txt))
    win32gui.EnumChildWindows(hw, cb, controls)
    return controls

def try_selection(catia, hw, body, name):
    print(f"\n--- Method: {name} ---")
    doc = catia.ActiveDocument
    sel = doc.Selection
    sel.Clear()
    sel.Add(body)
    time.sleep(2.0)
    
    controls = get_all_controls(hw)
    lb_text = ""
    dim_found = False
    for h, c, t in controls:
        if "ListBox" in c and t: lb_text = t
        if "mm" in t and t != "0mm" and t != "": dim_found = True
    
    print(f"  ListBox Text: '{lb_text}'")
    print(f"  Dimensions found? {dim_found}")
    
    if lb_text != "" or dim_found:
        print(f"!!! SUCCESS with {name} !!!")
        return True
    return False

def run_test():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        
        # 1. Clear windows
        while (hw := find_rough_stock_window()):
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0); time.sleep(1)

        # 2. Find Body
        body = None
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if ".CATPart" in d.Name:
                body = d.Part.Bodies.Item(1); break
        
        if not body: return print("No body found.")
        print(f"Testing on: {body.Name}")

        # 3. Test Select BEFORE
        print("\n--- Method: Select BEFORE ---")
        catia.ActiveDocument.Selection.Clear()
        catia.ActiveDocument.Selection.Add(body)
        catia.StartCommand("Creates rough stock")
        time.sleep(3)
        hw = find_rough_stock_window()
        if hw:
            controls = get_all_controls(hw)
            lb = next((t for h, c, t in controls if "ListBox" in c), "")
            print(f"  ListBox: '{lb}'")
            if lb: print("!!! SUCCESS with Select BEFORE !!!"); return
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0); time.sleep(1)

        # 4. Test Select AFTER
        catia.StartCommand("Creates rough stock")
        time.sleep(3)
        hw = find_rough_stock_window()
        if not hw: return print("Dialog didn't open.")
        
        try_selection(catia, hw, body, "Select AFTER")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_test()
