import sys
import os
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add backend to path
sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService
from app.services.geometry_service import geometry_service

def main():
    try:
        catia = catia_bridge.get_application()
        
        # 0. CLOSE BLOCKING DIALOGS FIRST
        print("Clearing any blocking dialogs...")
        err_hw = RoughStockService._find_error_window()
        if err_hw:
            RoughStockService._close_error_window(err_hw)
            time.sleep(0.5)

        # 1. FIND THE RIGHT DOCUMENT
        target_name = "000_LOWER_FLANGE_STEEL_01"
        target_doc = None
        for d in catia.Documents:
            if target_name in d.Name:
                target_doc = d
                break
        
        if not target_doc:
            print(f"ERROR: Could not find document containing '{target_name}'")
            print("Open documents are:")
            for d in catia.Documents: print(f" - {d.Name}")
            return

        print(f"Activating target part: {target_doc.Name}")
        target_doc.Activate()
        doc = target_doc
        
        # 2. Switch to Generative Shape Design
        print("Switching workbench to Generative Shape Design...")
        try:
            # Try both name and ID
            catia.StartWorkbench("CATShapeDesignWorkbench")
            time.sleep(1)
        except Exception as we:
            print(f"Workbench switch warning: {we}")

        # 3. Check command status
        print(f"Checking status for 'Rough Stock' command...")
        try:
             # status = catia.GetCommandStatus("Rough Stock") # Not always available in COM
             # print(f"Command Status: {status}")
             pass
        except: pass

        # 4. Measure via Rough Stock (Tier 0)
        print("\n[METHOD 1] Rough Stock Scraper...")
        start_t = time.time()
        dx_rs, dy_rs, dz_rs = RoughStockService.get_rough_stock_dims(catia)
        end_t = time.time()
        time_rs = end_t - start_t
        
        # 3. Measure via STL (Tier 3)
        # We'll bypass the Tier 0 check manually for comparison
        print("\n[METHOD 2] STL Bounding Box (Context Breaker)...")
        start_t = time.time()
        # Direct call to the parse logic or similar. 
        # Actually, let's just use the geometry_service but force it into STL path 
        # (Though current geometry_service doesn't have an 'override' flag, 
        # we can just use the internal _parse_stl_manual logic directly on the active doc)
        
        # Simulating context-breaker for a clean comparison
        from app.services.geometry_service import MM_PER_M
        
        res_stl = None
        temp_stl = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), "bench_compare.stl")
        try:
            doc.ExportData(temp_stl, "stl")
            res_stl = geometry_service._parse_stl_manual(temp_stl)
        except Exception as se:
            print(f"STL Export failed: {se}")
        
        end_t = time.time()
        time_stl = end_t - start_t

        # --- RESULTS ---
        print("\n" + "="*40)
        print(f"{'Method':<15} | {'Result (W x D x H)':<25} | {'Time (s)':<10}")
        print("-" * 40)
        
        rs_str = f"{dx_rs} x {dy_rs} x {dz_rs}" if dx_rs else "FAILED"
        print(f"{'Rough Stock':<15} | {rs_str:<25} | {time_rs:<10.2f}")
        
        stl_str = f"{res_stl['x']} x {res_stl['y']} x {res_stl['z']}" if res_stl else "FAILED"
        print(f"{'STL Method':<15} | {stl_str:<25} | {time_stl:<10.2f}")
        print("="*40)

        if dx_rs and res_stl:
            diff_x = abs(dx_rs - res_stl['x'])
            diff_y = abs(dy_rs - res_stl['y'])
            diff_z = abs(dz_rs - res_stl['z'])
            print(f"\nDiscrepancy: DX={diff_x:.2f}, DY={diff_y:.2f}, DZ={diff_z:.2f}")

    except Exception as e:
        print(f"Comparison Error: {e}")

if __name__ == "__main__":
    main()
