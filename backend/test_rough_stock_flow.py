"""
STRICTLY IN-PLACE Rough Stock Flow.
NO opening documents. NO window switching.
Targets: 000_LOWER_FLANGE_STEEL_02
"""
import sys, os, time, logging
import win32com.client
import win32gui
import win32con

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("InPlaceFlow")

sys.path.append(os.getcwd())
try:
    from app.services.rough_stock_service import RoughStockService
except ImportError:
    pass

def find_item_in_tree(product, target_name):
    """Recursively search the assembly tree for the target Part/Product."""
    def _recurse(p):
        if target_name.upper() in p.Name.upper() or target_name.upper() in p.PartNumber.upper():
            return p
        for i in range(1, p.Products.Count + 1):
            res = _recurse(p.Products.Item(i))
            if res: return res
        return None
    return _recurse(product)

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        
        # USE ONLY THE CURRENTLY ACTIVE WINDOW
        doc = catia.ActiveDocument
        print(f"STRICTLY using active document: {doc.Name}")
        
        if "CATProduct" not in doc.Name:
            print("ERROR: Active document is not a CATProduct. Please open the assembly window.")
            return

        # Start background monitor for popups
        RoughStockService.start_dialog_monitor(interval=0.5)

        # 1. Ensure GSD workbench in THIS window
        print("Ensuring GSD workbench in current window...")
        catia.StartWorkbench("CATShapeDesignWorkbench")
        time.sleep(3.0)

        # 2. Target Part
        target_name = "000_LOWER_FLANGE_STEEL_02"
        print(f"\nSearching tree for: {target_name}")
        item = find_item_in_tree(doc.Product, target_name)
        
        if not item:
            print(f"ERROR: Could not find {target_name} in the tree.")
            return
        
        print(f"Found item: {item.Name}")

        # 3. Selection and Trigger
        sel = doc.Selection
        sel.Clear()
        sel.Add(item)
        
        # Trigger "Creates rough stock" via Power Input (Same Window)
        print("Triggering Rough Stock command...")
        w_shell = win32com.client.Dispatch("WScript.Shell")
        w_shell.AppActivate("CATIA")
        time.sleep(0.5)
        w_shell.SendKeys("{ESC}c:Creates rough stock{ENTER}", 0)
        
        # Wait for dialog
        hw = 0
        for i in range(20):
            time.sleep(0.5)
            hw = RoughStockService._find_window()
            if hw: break
        
        if not hw:
            print("ERROR: Rough Stock dialog failed to appear.")
            return

        # 4. Find the Body to select
        # We need the PartBody of the referenced document
        try:
            ref_prod = item.ReferenceProduct
            part_doc = ref_prod.Parent
            body = part_doc.Part.MainBody
            print(f"Selecting PartBody: {body.Name}")
            
            sel.Clear()
            sel.Add(body)
            time.sleep(2.0) # Wait for computation
            
            # Scrape Dims
            dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, stay_open=False)
            if dx is not None:
                print(f"\nSUCCESS for {target_name}:")
                print(f"  Dimensions: {dx:.2f} x {dy:.2f} x {dz:.2f}")
            else:
                print("FAILED to read dimensions from dialog.")
        except Exception as e:
            print(f"Error during selection/scraping: {e}")

        # Cleanup
        RoughStockService.stop_dialog_monitor()
        print("\nFlow complete.")

    except Exception as e:
        logger.exception(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()
