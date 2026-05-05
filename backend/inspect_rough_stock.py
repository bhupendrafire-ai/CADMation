import win32gui
import win32con
import win32com.client
import time
import sys
import os

# Add backend to path to use services
sys.path.append(os.getcwd())
from app.services.rough_stock_service import RoughStockService
from app.services.catia_bridge import catia_bridge

def dump_controls():
    hw = RoughStockService._find_window()
    if not hw:
        print("Rough Stock window NOT found. Triggering...")
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.AppActivate("CATIA")
        time.sleep(1)
        shell.SendKeys("{ESC}c:Creates rough stock{ENTER}", 0)
        for i in range(10):
            time.sleep(0.5)
            hw = RoughStockService._find_window()
            if hw: break
    
    if not hw:
        print("FAILED to find Rough Stock window.")
        return

    print(f"Window Handle: {hw}")
    controls = []
    def callback(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd): return True
        cls = win32gui.GetClassName(hwnd)
        buf_size = 512
        try:
            buffer = win32gui.PyMakeBuffer(buf_size)
            length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, buf_size, buffer)
            raw_bytes = buffer[:length*2].tobytes()
            text_u16 = raw_bytes.decode('utf-16', errors='ignore').strip().replace('\x00', '')
            text_ansi = raw_bytes[:length].decode('ansi', errors='ignore').strip()
            text = text_u16 if len(text_u16) >= len(text_ansi) else text_ansi
        except:
            text = ""
        results.append((hwnd, cls, text))
        return True

    win32gui.EnumChildWindows(hw, callback, controls)
    
    with open("rough_stock_inspect.txt", "w") as f:
        for i, (h, c, t) in enumerate(controls):
            line = f"[{i}] Class: {c}, Text: '{t}', HWND: {h}\n"
            print(line.strip())
            f.write(line)
    
    edits = [(i, t) for i, (h, c, t) in enumerate(controls) if c == "Edit"]
    print("\nEDITS found:")
    for idx, (original_idx, text) in enumerate(edits):
        print(f"Edit Index {idx} (Original {original_idx}): '{text}'")

if __name__ == "__main__":
    dump_controls()
