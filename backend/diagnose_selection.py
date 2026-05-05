import win32com.client
import win32gui
import win32con
import time
import re
import ctypes

def parse_mm(text):
    try:
        match = re.search(r"([-+]?\d*\.\d+|\d+)", text)
        if match:
            return float(match.group(1))
    except: pass
    return None

def scrape_dims_production(hw):
    for attempt in range(3):
        controls = []
        def callback(hwnd, results):
            if not win32gui.IsWindowVisible(hwnd): return True
            cls = win32gui.GetClassName(hwnd)
            try:
                length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
                buffer = ctypes.create_unicode_buffer(length + 1)
                win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
                text = buffer.value
            except:
                text = ""
            results.append((hwnd, cls, text))
            return True
        win32gui.EnumChildWindows(hw, callback, controls)
        edits = [t for h, c, t in controls if c == "Edit"]
        if len(edits) >= 9:
            all_vals = [parse_mm(e) for e in edits]
            return all_vals
        time.sleep(0.5)
    return None

def find_rs_window():
    found = []
    def cb(hwnd, extra):
        title = win32gui.GetWindowText(hwnd)
        if "Rough Stock" in title:
            found.append(hwnd)
        return True
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None

def main():
    catia = win32com.client.Dispatch("CATIA.Application")
    doc = catia.ActiveDocument
    sel = doc.Selection
    
    hw = find_rs_window()
    if not hw:
        print("Please open Rough Stock dialog manually in CATIA.")
        return

    print(f"Active Document: {doc.Name}")
    
    # Let's try to find a Product node if possible
    target = None
    if sel.Count > 0:
        target = sel.Item2(1).Value
        print(f"Targeting current selection: {getattr(target, 'Name', 'Unknown')} ({type(target)})")
    else:
        print("Nothing selected. Please select a PRODUCT node in the assembly.")
        return

    # Test 1: Direct Add of target (whatever user selected)
    print(f"\n--- Testing Selection of: {target.Name} ---")
    sel.Clear()
    sel.Add(target)
    print(f"Selection count: {sel.Count}")
    time.sleep(2.5)
    vals = scrape_dims_production(hw)
    print(f"Results: {vals[2] if vals and len(vals)>2 else 'None'}, {vals[5] if vals and len(vals)>5 else 'None'}, {vals[8] if vals and len(vals)>8 else 'None'}")

    # Test 2: If it's a Product, drill to PartBody and try to select THAT
    if hasattr(target, "ReferenceProduct"):
        try:
            part = target.ReferenceProduct.Parent.Part
            body = part.MainBody
            print(f"\n--- Testing Sub-Body: {body.Name} of {target.Name} ---")
            sel.Clear()
            sel.Add(body)
            print(f"Selection count: {sel.Count}")
            time.sleep(2.5)
            vals = scrape_dims_production(hw)
            print(f"Results: {vals[2] if vals and len(vals)>2 else 'None'}, {vals[5] if vals and len(vals)>5 else 'None'}, {vals[8] if vals and len(vals)>8 else 'None'}")
        except Exception as e:
            print(f"Could not drill to Body: {e}")

if __name__ == "__main__":
    main()
