import sys, os, time
import win32gui
import win32con
import ctypes

def dump_dialog():
    hw = 0
    def find_window(hwnd, ctx):
        title = win32gui.GetWindowText(hwnd).upper()
        if "ROUGH STOCK" in title or "BRUT" in title:
            ctx['hw'] = hwnd
            return False
        return True

    ctx = {'hw': 0}
    win32gui.EnumWindows(find_window, ctx)
    hw = ctx['hw']
    
    if not hw:
        print("Rough Stock dialog not found.")
        return

    print(f"Found window: {win32gui.GetWindowText(hw)} (Handle: {hw})")
    
    controls = []
    def callback(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd): return True
        cls = win32gui.GetClassName(hwnd)
        
        # Get text robustly
        length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
        buffer = ctypes.create_unicode_buffer(length + 1)
        win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
        text = buffer.value
        
        results.append((hwnd, cls, text))
        return True

    win32gui.EnumChildWindows(hw, callback, controls)
    
    for i, (h, c, t) in enumerate(controls):
        print(f"[{i}] Class: {c} | Text: '{t}'")

if __name__ == "__main__":
    dump_dialog()
