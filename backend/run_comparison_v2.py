import sys
import os
import time
import logging
import win32com.client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CompareTest")

# Add backend to path
sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService
from app.services.geometry_service import geometry_service

def cleanup_popups():
    print("Forcefully clearing any blocking dialogs...")
    for _ in range(3):
        err_hw = RoughStockService._find_error_window()
        if err_hw:
            RoughStockService._close_error_window(err_hw)
            time.sleep(0.5)

def main():
    try:
        cleanup_popups()
        
        catia = catia_bridge.get_application()
        
        target_name = "000_LOWER_FLANGE_STEEL_01"
        part_doc = None
        
        # 1. Check if already open
        print(f"Searching for {target_name} in open documents...")
        for d in catia.Documents:
            if target_name in d.Name and ".CATPart" in d.Name.upper():
                part_doc = d
                break
        
        # 2. If not open, look in the active assembly (RECURSIVE)
        if not part_doc:
            print(f"Not found in open docs. Searching recursively in active assembly...")
            active_doc = catia.ActiveDocument
            if "CATProduct" in active_doc.Name:
                sel = active_doc.Selection
                
                # RECURSIVE SEARCH
                found_inst = None
                def search_recursive(prod):
                    nonlocal found_inst
                    if found_inst: return
                    
                    sub_prods = prod.Products
                    for j in range(1, sub_prods.Count + 1):
                        p = sub_prods.Item(j)
                        # Check PartNumber/Name
                        if target_name in p.PartNumber or target_name in p.Name:
                            found_inst = p
                            return
                        # Recurse if it's a sub-product/component
                        try:
                            if p.Products.Count > 0:
                                search_recursive(p)
                        except: pass
                
                search_recursive(active_doc.Product)
                
                if found_inst:
                    print(f"Found instance: {found_inst.Name}. Opening in new window...")
                    # Ensure Design Mode
                    try:
                        sel.Clear()
                        sel.Add(found_inst)
                        catia.StartCommand("Design Mode")
                        time.sleep(1)
                    except: pass
                    
                    sel.Clear()
                    sel.Add(found_inst)
                    catia.StartCommand("Open in New Window")
                    time.sleep(3)
                    part_doc = catia.ActiveDocument
        
        if not part_doc or "CATPart" not in part_doc.Name:
            print(f"ERROR: Could not isolate {target_name} in its own window.")
            cleanup_popups()
            return

        print(f"Target Part isolated: {part_doc.Name}")
        part_doc.Activate()
        
        # 3. Switch to GSD
        print("Switching to Generative Shape Design...")
        cleanup_popups() # Just in case StartCommand triggered something
        catia.StartWorkbench("CATShapeDesignWorkbench")
        time.sleep(1)

        # 4. Measure via Rough Stock (Tier 0)
        print("\n[METHOD 1] Rough Stock Scraper...")
        # Force a fresh attempt
        dx_rs, dy_rs, dz_rs = RoughStockService.get_rough_stock_dims(catia)
        
        # 5. Measure via STL (Tier 3)
        print("\n[METHOD 2] STL Bounding Box...")
        temp_stl = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), "rs_compare_final.stl")
        res_stl = None
        try:
            part_doc.ExportData(temp_stl, "stl")
            res_stl = geometry_service._parse_stl_manual(temp_stl)
        except Exception as se:
            print(f"STL Export failed: {se}")

        # --- RESULTS ---
        print("\n" + "="*50)
        print(f"PART: {part_doc.Name}")
        print(f"{'Method':<20} | {'Result (W x D x H)':<20} | {'Time (s)':<10}")
        print("-" * 50)
        
        rs_str = f"{dx_rs} x {dy_rs} x {dz_rs}" if dx_rs else "FAILED"
        print(f"{'Rough Stock':<20} | {rs_str:<20} | {'-':<10}")
        
        stl_str = f"{res_stl['x']} x {res_stl['y']} x {res_stl['z']}" if res_stl else "FAILED"
        print(f"{'STL Method':<20} | {stl_str:<20} | {'-':<10}")
        print("="*50)

    except Exception as e:
        print(f"Test Error: {e}")
        cleanup_popups()

if __name__ == "__main__":
    main()
