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
    dim_text = "0mm"
    for e in edits:
        if "mm" in e and e != "0mm" and e != "" and not any(x in e for x in ["min", "max"]):
            dim_text = e
            break
    return dim_text

def run_test_selection_before():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        # Close any existing window
        hw = find_rough_stock_window()
        if hw:
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
            time.sleep(1)

        # Find target
        part = doc.Part
        body = part.Bodies.Item(1)
        print(f"Target: {body.Name}")

        print("\n>>> Testing Method: Select BEFORE Command")
        sel.Clear()
        sel.Add(body)
        time.sleep(0.5)
        
        print("Triggering command...")
        catia.StartCommand("Creates rough stock")
        
        # Wait for window
        hw = None
        for _ in range(10):
            time.sleep(0.5)
            hw = find_rough_stock_window()
            if hw: break
        
        if hw:
            time.sleep(2)
            dim_txt = get_dialog_state(hw)
            print(f"Result: Dim='{dim_txt}'")
            if dim_txt != "0mm" and dim_txt != "":
                print("!!! SUCCESS with Select BEFORE !!!")
                return True
        else:
            print("Dialog did not open.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()
    return False

def run_test_selection_after_advanced():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        # Open dialog
        catia.StartCommand("Creates rough stock")
        time.sleep(2)
        hw = find_rough_stock_window()
        if not hw: return False

        part = doc.Part
        body = part.Bodies.Item(1)
        
        print("\n>>> Testing Method: Select AFTER with Focus + ESC")
        win32gui.SetForegroundWindow(hw)
        time.sleep(0.2)
        
        # Maybe the selection field needs focus?
        # Let's try to click the first ListBox
        controls = []
        win32gui.EnumChildWindows(hw, lambda h, r: r.append(h) if "ListBox" in win32gui.GetClassName(h) else None, controls)
        if controls:
            print(f"Clicking ListBox (HWND: {controls[0]})")
            win32gui.SendMessage(controls[0], win32con.WM_LBUTTONDOWN, 0, 0)
            win32gui.SendMessage(controls[0], win32con.WM_LBUTTONUP, 0, 0)
            time.sleep(0.2)

        sel.Clear()
        sel.Add(body)
        time.sleep(1.5)
        
        dim_txt = get_dialog_state(hw)
        print(f"Result: Dim='{dim_txt}'")
        if dim_txt != "0mm" and dim_txt != "":
            print("!!! SUCCESS with Select AFTER + Focus !!!")
            return True

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()
    return False

if __name__ == "__main__":
    if not run_test_selection_before():
        run_test_selection_after_advanced()
