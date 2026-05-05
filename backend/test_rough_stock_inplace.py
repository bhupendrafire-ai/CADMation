"""
STRICTLY SAME-WINDOW Rough Stock Flow.
Advanced Deep Selection (Search + Add)
The user must be in GSD manually.
Targets: 000_LOWER_FLANGE_STEEL_02 -> LOWER STEEL-02
"""
import sys, os, time, logging
import win32com.client
import win32gui
import win32con
import pythoncom
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("SelectionFix")

sys.path.append(os.getcwd())
try:
    from app.services.rough_stock_service import RoughStockService
except ImportError:
    pass

def main():
    try:
        catia = win32com.client.Dispatch("CATIA.Application")
        main_doc = catia.ActiveDocument
        print(f"STRICTLY using active document: {main_doc.Name}")

        parent_part_name = "000_LOWER_FLANGE_STEEL_02"
        target_body_name = "LOWER STEEL-02"

        # 1. Trigger Command FIRST (Matches user sequence)
        RoughStockService.start_dialog_monitor(interval=0.5)
        print("\nTriggering command...")
        w_shell = win32com.client.Dispatch("WScript.Shell")
        w_shell.AppActivate("CATIA")
        time.sleep(0.5)
        w_shell.SendKeys("{ESC}c:Creates rough stock{ENTER}", 0)
        
        # 2. Wait for Dialog
        for i in range(10):
            time.sleep(0.5)
            if RoughStockService._find_window(): break
        
        print("Dialog detected. Attempting deep selection search...")

        # 3. Selection via SEARCH (Usually triggers UI better than direct Add)
        sel = main_doc.Selection
        sel.Clear()
        
        # We search specifically for the body name inside the tree.
        # String format: "CATShapeDesignSearch.Body;Name='LOWER STEEL-02',all"
        # Since we are in an assembly, we use the broad name search
        try:
            query = f"Name='*{target_body_name}*',all"
            print(f"Executing search: {query}")
            sel.Search(query)
            print(f"Items found via search: {sel.Count}")
            
            if sel.Count > 0:
                for i in range(1, sel.Count + 1):
                    item = sel.Item(i).Value
                    print(f"  [{i}] Found: {item.Name} (Type: {type(item).__name__})")
            else:
                print("Search yielded zero results. Checking manual path...")
        except Exception as e:
            print(f"Search failed: {e}")

        # 4. Scraping Loop with feedback
        print("\nStarting data capture loop (20s)...")
        dims_found = None
        for i in range(20):
            # If search didn't result in dimensions, try one manual Add() to the first item found
            if i == 5 and sel.Count > 0:
                print("Selection refresh: Clear then Add first search item...")
                first_val = sel.Item(1).Value
                sel.Clear()
                sel.Add(first_val)

            dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, stay_open=True)
            if dx is not None and dx > 0.001:
                print(f"  [{i}s] SUCCESS! Dimensions captured: {dx} x {dy} x {dz}")
                dims_found = (dx, dy, dz)
                break
            else:
                print(f"  [{i}s] Waiting for calculation... ({dx} x {dy} x {dz})")
            time.sleep(1)

        if dims_found:
            print(f"\n[AUTOMATION SUCCESS]")
            print(f"Final Dims: {dims_found[0]:.2f} x {dims_found[1]:.2f} x {dims_found[2]:.2f} mm")
        else:
            print("\nFAILED: The script could not automatically trigger the calculation.")
            print("Please confirm if the search query matched the tree node exactly.")

        RoughStockService.stop_dialog_monitor()
        print("\nFlow complete.")

    except Exception as e:
        logger.exception(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
