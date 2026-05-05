"""
Benchmark Comparison: Rough Stock vs STL.
Iterates through all visible parts in the active CATIA window.
Measures each part using both methods and reports.
"""
import sys, os, time, logging
import win32com.client
import pandas as pd
import pythoncom

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Benchmark")

sys.path.append(os.getcwd())
try:
    from app.services.rough_stock_service import RoughStockService
    from app.services.geometry_service import GeometryService
except ImportError:
    pass

def get_visible_parts(root_product):
    parts = []
    def _recurse(p):
        try:
            if p.Products.Count == 0:
                parts.append(p)
            else:
                for i in range(1, p.Products.Count + 1):
                    _recurse(p.Products.Item(i))
        except: pass
    _recurse(root_product)
    return parts

def main():
    try:
        pythoncom.CoInitialize()
        catia = win32com.client.Dispatch("CATIA.Application")
        main_doc = catia.ActiveDocument
        print(f"BOM Benchmark for: {main_doc.Name}")
        
        parts = get_visible_parts(main_doc.Product)
        # Select a subset of parts to verify across different tree depths
        # We target specific names if possible, or just the first few
        target_parts = parts[:10] 
        print(f"Found {len(parts)} parts. Benchmarking first {len(target_parts)}...")

        geo = GeometryService()
        results = []

        # Start dialog monitor for Rough Stock
        RoughStockService.start_dialog_monitor()

        for inst in target_parts:
            name = inst.Name
            print(f"\n[{name}]")
            
            # --- Method 1: STL (Traditional) ---
            start_stl = time.time()
            try:
                # Force STL by using the GeometryService directly
                # We want to compare against the 'nuclear' STL method
                # So we bypass the Tier 0 check
                stl_res = geo._parse_stl_manual_for_benchmark(inst) # Custom method or logic
                if not stl_res:
                    # Fallback to SPA measurement if STL fails in benchmark
                    stl_res = geo.get_bounding_box(inst) 
                
                stl_dims = f"{stl_res['x']}x{stl_res['y']}x{stl_res['z']}"
            except Exception as e:
                stl_dims = f"Error: {e}"
            stl_time = time.time() - start_stl

            # --- Method 2: Rough Stock (New) ---
            start_rs = time.time()
            try:
                # Find PartBody name for search-based selection
                ref_prod = inst.ReferenceProduct
                part_doc = ref_prod.Parent
                target_body_name = part_doc.Part.MainBody.Name
                
                # Close any old dialog first
                RoughStockService.close_window()
                
                # 1. Trigger
                dx, dy, dz = RoughStockService.get_rough_stock_dims(catia, target_name=target_body_name)
                rs_dims = f"{dx}x{dy}x{dz}" if dx else "Failed"
            except Exception as e:
                rs_dims = f"Error: {e}"
            rs_time = time.time() - start_rs

            results.append({
                "Part": name,
                "STL Dims": stl_dims,
                "STL Time": round(stl_time, 2),
                "RS Dims": rs_dims,
                "RS Time": round(rs_time, 2),
                "Delta % (Vol)": "N/A" # Calculated later
            })
            print(f"  STL: {stl_dims} ({stl_time:.2f}s)")
            print(f"  RS:  {rs_dims} ({rs_time:.2f}s)")

        RoughStockService.stop_dialog_monitor()

        # Print Final Table
        df = pd.DataFrame(results)
        print("\n" + "="*80)
        print("BOM MEASUREMENT BENCHMARK RESULTS")
        print("="*80)
        print(df.to_string(index=False))
        print("="*80)

    except Exception as e:
        logger.exception(f"Fatal bench error: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    main()
