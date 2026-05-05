import sys
import os
import time
import logging
import win32com.client

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add backend to path
sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

def main():
    try:
        catia = catia_bridge.get_application()
        
        # FIND THE ASSEMBLY
        active_doc = catia.ActiveDocument
        if "CATProduct" not in active_doc.Name:
            print("Current active doc is not a product. Searching...")
            for d in catia.Documents:
                if "CATProduct" in d.Name:
                    d.Activate()
                    active_doc = d
                    break
        
        if "CATProduct" not in active_doc.Name:
            print("ERROR: No CATProduct found open.")
            return

        print(f"Scanning assembly: {active_doc.Name}")
        
        # Collect all unique parts
        unique_parts = {} # {PartNumber: {Name, DocName, Path}}
        
        def collect_recursive(prod):
            itms = prod.Products
            for i in range(1, itms.Count + 1):
                inst = itms.Item(i)
                pn = inst.PartNumber
                if pn not in unique_parts:
                    unique_parts[pn] = {
                        "Name": inst.Name,
                        "Instance": inst
                    }
                try:
                    if inst.Products.Count > 0:
                        collect_recursive(inst)
                except: pass

        collect_recursive(active_doc.Product)
        print(f"Found {len(unique_parts)} unique parts. Measuring...")
        
        results = []
        for pn, data in unique_parts.items():
            print(f" - Measuring {pn}...")
            part_doc = None
            try:
                from app.services.rough_stock_service import RoughStockService
                
                # Proactive cleanup
                err_hw = RoughStockService._find_error_window()
                if err_hw: RoughStockService._close_error_window(err_hw)

                # 1. Open in New Window
                sel = active_doc.Selection
                sel.Clear()
                sel.Add(data['Instance'])
                catia.StartCommand("Open in New Window")
                time.sleep(2.0) # Wait more for document load
                
                # Check for "New" or "Unknown Command" popups blocking the open
                for _ in range(5):
                    err_hw = RoughStockService._find_error_window()
                    if err_hw:
                        print(f"   Cleared popup on {pn}")
                        RoughStockService._close_error_window(err_hw)
                        time.sleep(0.5)
                    else: break

                part_doc = catia.ActiveDocument
                if part_doc == active_doc:
                    print(f"   Failed to isolate {pn} (Active doc still assembly)")
                    continue

                if "CATPart" in part_doc.Name:
                    # 2. Force Design Mode if it fails, just catch it
                    try:
                        catia.StartCommand("Design Mode")
                        time.sleep(0.5)
                        # Immediately check for "Unavailable" popup
                        err_hw = RoughStockService._find_error_window()
                        if err_hw: RoughStockService._close_error_window(err_hw)
                    except: pass

                    temp_stl = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"audit_{pn}.stl")
                    try:
                        part_doc.ExportData(temp_stl, "stl")
                        bbox = geometry_service._parse_stl_manual(temp_stl)
                        if bbox:
                            results.append({
                                "PartNumber": pn,
                                "Size": f"{bbox['x']} x {bbox['y']} x {bbox['z']}",
                                "Raw": bbox
                            })
                            print(f"   Success: {bbox['x']} x {bbox['y']} x {bbox['z']}")
                        else:
                            print(f"   Failed to parse STL {pn}")
                    except Exception as ex:
                        print(f"   Export failed {pn}: {ex}")
                        err_hw = RoughStockService._find_error_window()
                        if err_hw: RoughStockService._close_error_window(err_hw)
                    
                    part_doc.Close()
                else:
                    print(f"   (Skipped {pn} - not a part)")
                    part_doc.Close()
            except Exception as e:
                print(f"   Measurement error {pn}: {e}")
                err_hw = RoughStockService._find_error_window()
                if err_hw: RoughStockService._close_error_window(err_hw)
                if part_doc and part_doc != active_doc:
                    try: part_doc.Close()
                    except: pass

        # --- FINAL TABLE ---
        print("\n" + "="*70)
        print(f"{'Part Number':<30} | {'STL Measurement (W x D x H)':<35}")
        print("-" * 70)
        for r in results:
            print(f"{r['PartNumber']:<30} | {r['Size']:<35}")
        print("="*70)

    except Exception as e:
        print(f"Audit Error: {e}")

if __name__ == "__main__":
    main()
