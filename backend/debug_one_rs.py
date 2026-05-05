import sys, os, time, logging
import win32com.client
import win32gui
import win32con

# Add backend to path
sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DebugMeas")

def debug_one():
    try:
        catia = catia_bridge.get_application()
        doc = catia.ActiveDocument
        sel = doc.Selection
        
        t_name = "001_LOWER SHOE"
        sel.Clear()
        sel.Search(f"Name=*{t_name}*,all")
        
        if sel.Count > 0:
            obj = sel.Item(1).Value
            print(f"Found {obj.Name} (Type: {type(obj).__name__})")
            
            # Start dialog if not open
            hw = RoughStockService._find_window()
            if not hw:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("CATIA")
                time.sleep(1)
                shell.SendKeys("{ESC}c:Creates rough stock{ENTER}", 0)
                for i in range(10):
                    time.sleep(0.5)
                    hw = RoughStockService._find_window()
                    if hw: break
            
            if not hw:
                print("Rough Stock window did not appear.")
                return

            # Try different selection strategies
            strategies = [
                ("Product/Part itself", obj),
            ]
            
            # If it's a product, try to find the body
            if hasattr(obj, "ReferenceProduct"):
                try:
                    ref = obj.ReferenceProduct
                    if hasattr(ref, "Parent") and hasattr(ref.Parent, "Part"):
                        part = ref.Parent.Part
                        if part.Bodies.Count > 0:
                            strategies.append(("PartBody", part.Bodies.Item(1)))
                except: pass

            for label, target in strategies:
                print(f"\n--- Strategy: {label} ---")
                sel.Clear()
                sel.Add(target)
                print(f"Selected {target.Name}. Waiting 5s...")
                time.sleep(5)
                
                # Check controls
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
                def get_text(h):
                    try:
                        # win32gui.GetWindowText works for most controls
                        t = win32gui.GetWindowText(h)
                        if not t:
                            # Fallback for some Edit controls
                            buf_size = 512
                            buffer = win32gui.PyMakeBuffer(buf_size)
                            length = win32gui.SendMessage(h, win32con.WM_GETTEXT, buf_size, buffer)
                            raw_bytes = buffer[:length*2].tobytes()
                            t = raw_bytes.decode('utf-16', errors='ignore').strip().replace('\x00', '')
                        return t
                    except: return ""

                print(f"ListBox Text (Before): '{get_text(controls[5][0])}'")
                
                # Strategy: Search
                sel.Clear()
                query = f"Name='*{target.Name}*',all"
                print(f"Executing Search: {query}")
                sel.Search(query)
                print(f"Selected {sel.Count} items. Waiting 5s...")
                time.sleep(5)
                
                print(f"ListBox Text (After Search): '{get_text(controls[5][0])}'")
                
                # Strategy: Click Select button + Add
                sel.Clear()
                print("Clicking 'Select' button (Index 7)...")
                win32gui.PostMessage(controls[7][0], win32con.BM_CLICK, 0, 0)
                time.sleep(1)
                sel.Add(target)
                print(f"Added to selection after click. Waiting 5s...")
                time.sleep(5)
                print(f"ListBox Text (After Click+Add): '{get_text(controls[5][0])}'")

                # Check controls again
                controls_after = []
                win32gui.EnumChildWindows(hw, callback, controls_after)
                edits = [t for h, c, t in controls_after if c == "Edit"]
                print(f"\nEdit count: {len(edits)}")
                if len(edits) >= 9:
                    print(f"X: {edits[0]}, {edits[1]}, DX: {edits[2]}")

        else:
            print(f"Target {t_name} not found.")

    except Exception as e:
        logger.exception(f"Debug failed: {e}")

if __name__ == "__main__":
    debug_one()
