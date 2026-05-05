import win32gui
import win32con
import time
import win32com.client
import pythoncom

def callback(hwnd, results):
    if not win32gui.IsWindowVisible(hwnd): return True
    title = win32gui.GetWindowText(hwnd)
    cls = win32gui.GetClassName(hwnd)
    results.append((hwnd, title, cls))
    return True

def find_rough_stock_window():
    hw_found = []
    def enum_cb(hwnd, found):
        if win32gui.IsWindowVisible(hwnd) and "Rough Stock" in win32gui.GetWindowText(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(enum_cb, hw_found)
    return hw_found[0] if hw_found else 0

def dump_controls(hw):
    controls = []
    win32gui.EnumChildWindows(hw, callback, controls)
    print(f"--- Controls for Window {hw} ---")
    for i, (h, t, c) in enumerate(controls):
        # Try to get text via WM_GETTEXT if t is empty
        if not t:
            buf_size = 512
            buffer = win32gui.PyMakeBuffer(buf_size)
            length = win32gui.SendMessage(h, win32con.WM_GETTEXT, buf_size, buffer)
            raw_bytes = buffer[:length*2].tobytes()
            t = raw_bytes.decode('utf-16', errors='ignore').strip().replace('\x00', '')
        print(f"[{i}] HWND: {h}, Class: {c}, Text: '{t}'")

def run_diagnostic():
    pythoncom.CoInitialize()
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        print(f"Connected to {catia.Name}")
        
        hw = find_rough_stock_window()
        if not hw:
            print("Rough Stock window not found. Please open it manually or stay at the prompt.")
            # Start command
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("CATIA")
            time.sleep(0.5)
            shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)
            
            for _ in range(10):
                time.sleep(1)
                hw = find_rough_stock_window()
                if hw: break
        
        if hw:
            dump_controls(hw)
        else:
            print("Failed to open Rough Stock window.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_diagnostic()
