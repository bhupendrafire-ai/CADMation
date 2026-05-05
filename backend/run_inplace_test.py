"""
Final In-place Rough Stock test: stay in the same assembly window.
Forces DESIGN MODE to ensure geometry is loaded.
Targets 2 parts in "LWR NON STD PART".
"""
import sys, os, time, logging
import win32com.client
import win32gui
import win32con

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("InPlaceTest")

sys.path.append(os.getcwd())
from app.services.rough_stock_service import RoughStockService

def find_lwr_asm(root):
    """Find the LWR NON STD PART assembly instance."""
    def _recurse(prod):
        n = prod.Name.upper()
        pn = ""
        try: pn = prod.PartNumber.upper()
        except: pass
        if ("LWR" in n and "NON" in n and "STD" in n) or ("LWR" in pn and "NON" in pn and "STD" in pn):
            return prod
        for i in range(1, prod.Products.Count + 1):
            res = _recurse(prod.Products.Item(i))
            if res: return res
    return _recurse(root)


def get_part_bodies(inst):
    """Get the PartBody from a product instance."""
    try:
        ref = inst.ReferenceProduct
        doc = ref.Parent
        if ".CATPart" in doc.Name:
            return doc.Part.MainBody, doc.Part.Bodies.Count
    except:
        pass
    return None, 0


def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        
        doc = None
        try:
            doc = catia.ActiveDocument
            if "CATProduct" not in doc.Name: doc = None
        except: pass
        
        if not doc:
            for d in catia.Documents:
                if "CATProduct" in d.Name:
                    d.Activate()
                    doc = d
                    break
        
        if not doc:
            print("ERROR: No CATProduct document found.")
            return

        RoughStockService.start_dialog_monitor(interval=0.5)

        print(f"Assembly: {doc.Name}")
        
        lwr_asm = find_lwr_asm(doc.Product)
        if not lwr_asm:
            print("LWR NON STD PART not found. Using root.")
            lwr_asm = doc.Product

        print(f"Target Sub-Assembly: {lwr_asm.Name}")
        
        # FORCE DESIGN MODE
        print("Activating Design Mode...")
        sel = doc.Selection
        sel.Clear()
        sel.Add(lwr_asm)
        catia.StartCommand("Design Mode")
        time.sleep(4.0)

        # Identify parts
        parts = []
        def _collect(p_root, target_list):
            for i in range(1, p_root.Products.Count + 1):
                p_inst = p_root.Products.Item(i)
                body, b_count = get_part_bodies(p_inst)
                if body and b_count > 0:
                    target_list.append({"instance": p_inst, "body": body})
                if len(target_list) >= 2: return
                try: search_sub = (p_inst.Products.Count > 0)
                except: search_sub = False
                if search_sub: _collect(p_inst, target_list)
                if len(target_list) >= 2: return
        
        _collect(lwr_asm, parts)
        if not parts:
            print("ERROR: No CATParts with bodies found.")
            return

        print(f"Measuring {len(parts)} parts...")

        # Switch to GSD
        print("Enabling GSD workbench...")
        catia.StartWorkbench("CATShapeDesignWorkbench")
        time.sleep(5.0)
        
        # Trigger Command with robust SendKeys
        print("Triggering Rough Stock command via Power Input...")
        w_shell = win32com.client.Dispatch("WScript.Shell")
        w_shell.AppActivate("CATIA")
        time.sleep(1.0)
        
        # Escape any existing text in Power Input, then type
        # Sometimes 'c:' is needed, sometimes not. Let's try what user and I saw.
        w_shell.SendKeys("{ESC}", 0) 
        time.sleep(0.5)
        w_shell.SendKeys("c:Creates rough stock{ENTER}", 0)
        
        hw = 0
        for i in range(25):
            time.sleep(0.5)
            hw = RoughStockService._find_window()
            if hw: break
            
            # Fallback retry if first one didn't take
            if i == 10:
                print("Dialog delayed. Retrying trigger...")
                w_shell.SendKeys("{ESC}c:Creates rough stock{ENTER}", 0)

        if not hw:
            print("ERROR: Rough Stock dialog failed to appear. Trying StartCommand fallback...")
            try:
                catia.StartCommand("Creates rough stock")
                time.sleep(2.0)
                hw = RoughStockService._find_window()
            except: pass

        if not hw:
            print("STILL FAILED. Please ensure the 'Rough Stock' command is available in GSD.")
            return

        print("Rough Stock dialog active. Starting measurements...")
        results = []
        for i, p in enumerate(parts):
            inst = p["instance"]
            body = p["body"]
            print(f"[{i+1}/{len(parts)}] {inst.Name}")
            
            sel.Clear()
            sel.Add(body)
            time.sleep(2.0)
            
            dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, stay_open=True)
            if dx is not None:
                print(f"  Dims: {dx} x {dy} x {dz}")
                results.append((inst.Name, dx, dy, dz))
            else:
                results.append((inst.Name, None, None, None))

        RoughStockService.close_window()
        RoughStockService.stop_dialog_monitor()

        print("\nSummary Results:")
        print("-" * 60)
        for name, dx, dy, dz in results:
            if dx is not None:
                print(f"{name:<40} | {dx:.2f} x {dy:.2f} x {dz:.2f}")
            else:
                print(f"{name:<40} | FAILED")
        print("-" * 60)

    except Exception as e:
        logger.exception(f"Error: {e}")

if __name__ == "__main__":
    main()
