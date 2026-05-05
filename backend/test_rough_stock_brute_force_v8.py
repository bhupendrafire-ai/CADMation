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
        if "ListBox" in c and t: lb_text = t
    
    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
    return lb_text, dim_text

def test_selection_methods():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        
        # 1. Find a valid Part document
        target_doc = None
        for i in range(1, catia.Documents.Count + 1):
            d = catia.Documents.Item(i)
            if ".CATPart" in d.Name:
                target_doc = d
                break
        
        if not target_doc:
            print("No CATPart found in session.")
            return

        print(f"Targeting Document: {target_doc.Name}")
        # Make it active
        catia.ActiveWindow = target_doc.Parent.Windows.Item(target_doc.Name) 
        # Or more simply:
        # target_doc.Activate() # Some versions prefer this
        
        part = target_doc.Part
        body = part.Bodies.Item(1)
        
        # 2. Trigger Dialog
        catia.StartCommand("Creates rough stock")
        time.sleep(2)
        hw = find_rough_stock_window()
        if not hw:
            print("Dialog did not open via StartCommand.")
            return

        print("\n>>> Testing Method: Selection.Add(body) while dialog is open")
        sel = target_doc.Selection
        sel.Clear()
        sel.Add(body)
        time.sleep(1.5)
        
        lb, dim = get_dialog_state(hw)
        print(f"Result: LB='{lb}', Dim='{dim}'")
        
        if dim != "0mm" and dim != "":
            print("!!! SUCCESS !!!")
            return

        print("\n>>> Testing Method: Selection.Add(Reference) while dialog is open")
        try:
            ref = part.CreateReferenceFromObject(body)
            sel.Clear()
            sel.Add(ref)
            time.sleep(1.5)
            lb, dim = get_dialog_state(hw)
            print(f"Result: LB='{lb}', Dim='{dim}'")
            if dim != "0mm":
                print("!!! SUCCESS with Reference !!!")
                return
        except Exception as re:
            print(f"Ref failed: {re}")

        print("\n>>> Testing Method: Select BEFORE Trigger")
        win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
        time.sleep(1)
        sel.Clear()
        sel.Add(body)
        catia.StartCommand("Creates rough stock")
        time.sleep(2)
        hw = find_rough_stock_window()
        if hw:
            dim = get_dialog_state(hw)
            print(f"Result: Dim='{dim}'")
            if dim != "0mm":
                print("!!! SUCCESS with Select BEFORE !!!")
                return

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_selection_methods()
