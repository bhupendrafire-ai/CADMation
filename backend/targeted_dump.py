import sys, os, time
import win32gui
import win32con
import ctypes

def targeted_dump():
    def find_window(hwnd, ctx):
        title = win32gui.GetWindowText(hwnd).upper()
        if "ROUGH STOCK" in title or "BRUT" in title:
            ctx['hw'] = hwnd
            return False
        return True

    ctx = {'hw': 0}
    win32gui.EnumWindows(find_window, ctx)
    hw = ctx['hw']
    if not hw: return

    controls = []
    def callback(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd): return True
        cls = win32gui.GetClassName(hwnd)
        length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
        buffer = ctypes.create_unicode_buffer(length + 1)
        win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
        text = buffer.value
        results.append((hwnd, cls, text))
        return True

    win32gui.EnumChildWindows(hw, callback, controls)
    
    edit_idx = 0
    for i, (h, c, t) in enumerate(controls):
        if c == "Edit":
            # Try to find the preceding label
            label = "Unknown"
            for j in range(i-1, -1, -1):
                if controls[j][1] == "Static" and controls[j][2]:
                    label = controls[j][2]
                    break
            print(f"EDIT [{edit_idx}] (Window ID {i}) | Label: '{label}' | Value: '{t}'")
            edit_idx += 1
        elif "Static" in c and t:
            # print(f"STATIC {i}: '{t}'")
            pass

if __name__ == "__main__":
    targeted_dump()
