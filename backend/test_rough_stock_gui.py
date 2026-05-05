import win32com.client
import win32gui
import win32con
import time
import re

def get_child_windows(parent_hw):
    if not parent_hw:
        return []
    child_windows = []
    try:
        win32gui.EnumChildWindows(parent_hw, lambda hwnd, param: param.append(hwnd), child_windows)
    except Exception as e:
        print(f"Error enumerating child windows: {e}")
    return child_windows

def solve():
    try:
        # Check if window is ALREADY open
        hw = 0
        def find_rs_callback(hwnd, found):
            title = win32gui.GetWindowText(hwnd)
            if "Rough Stock" == title: # Exact match
                found.append(hwnd)
        
        found = []
        win32gui.EnumWindows(find_rs_callback, found)
        if found:
            hw = found[0]
            print(f"Found EXISTING Rough Stock window: {hw}")
        else:
            print("Rough Stock window not found. Attempting to open via selection...")
            catia = win32com.client.Dispatch("CATIA.Application")
            part_doc = catia.ActiveDocument
            selection = part_doc.Selection
            part = part_doc.Part
            body = part.Bodies.Item(1)
            selection.Clear()
            selection.Add(body)
            print(f"Selected: {body.Name}")
            catia.StartCommand("Rough Stock")
            
            for _ in range(10):
                found = []
                win32gui.EnumWindows(find_rs_callback, found)
                if found:
                    hw = found[0]
                    break
                time.sleep(0.5)
        
        if not hw:
            print("Could not find or open 'Rough Stock' window.")
            return

        print(f"Found Rough Stock window HWND: {hw}")
        
        # Extract text from all children
        def callback(hwnd, results):
            cls = win32gui.GetClassName(hwnd)
            # Use WM_GETTEXT with a large buffer
            buf_size = 512
            buffer = win32gui.PyMakeBuffer(buf_size)
            length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, buf_size, buffer)
            
            # Try decoding as UTF-16 first if it looks like wide chars
            raw_bytes = buffer[:length*2].tobytes() # length is often in chars
            try:
                # Some CATIA controls are UTF-16, some are ANSI
                # If there are nulls between chars, it's wide
                text_u16 = raw_bytes.decode('utf-16', errors='ignore').strip().replace('\x00', '')
                text_ansi = raw_bytes[:length].decode('ansi', errors='ignore').strip()
                
                # Heuristic: choose the one that makes more sense
                if len(text_u16) > 0 and (len(text_u16) >= len(text_ansi) or 'mm' in text_u16):
                    text = text_u16
                else:
                    text = text_ansi
            except:
                text = raw_bytes.decode('ansi', errors='ignore').strip()
            
            results.append((hwnd, cls, text))
            return True

        controls = []
        win32gui.EnumChildWindows(hw, callback, controls)
        
        with open("rough_stock_controls_v2.txt", "w", encoding='utf-8') as f:
            f.write(f"--- Controls for HWND {hw} ---\n")
            for h, c, t in controls:
                f.write(f"HWND: {h} | Class: {c} | Text: '{t}'\n")
        
        print("\n--- Summary of Controls with Text ---")
        for h, c, t in controls:
            if t:
                print(f"Class: {c} | Text: '{t}'")
            
        # Analyze results to find dimensions
        dims = []
        for h, c, t in controls:
            if t:
                # Look for numbers
                match = re.search(r"([-+]?\d*\.\d+|\d+)", t)
                if match:
                    dims.append((t, match.group(1)))
        
        print("\n--- Potential Dimensions ---")
        for raw, val in dims:
            print(f"Raw: {raw} | Value: {val}")

        # Try to find the specific values from screenshot to verify
        target_vals = ["140", "100", "145.03"]
        found_targets = []
        for raw, val in dims:
            for tv in target_vals:
                if tv in val:
                    found_targets.append((tv, raw))
        
        if found_targets:
            print("\n--- Verified Hits ---")
            for tv, raw in found_targets:
                print(f"Target {tv} found in: '{raw}'")
        else:
            print("\nNo target values found. Check rough_stock_controls.txt for raw dump.")

        # Close window by finding the Cancel button
        # for h, c, t in controls:
        #     if t == "Cancel" and c == "Button":
        #         win32gui.PostMessage(h, win32con.BM_CLICK, 0, 0)
        #         print("Clicked Cancel.")
        #         break

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    solve()
