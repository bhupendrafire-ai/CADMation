"""
Rough Stock vs STL: Side-by-side comparison on 3 parts.
Uses Direct File Opening to guarantee Design Mode geometry.
"""
import sys, os, time, logging
import win32com.client
import win32gui
import win32con

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("SampleTest")

sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService
from app.services.geometry_service import geometry_service


def cleanup_popups():
    """Forcefully clear any blocking dialogs."""
    for _ in range(5):
        err_hw = RoughStockService._find_error_window()
        if err_hw:
            logger.info(f"Clearing popup: '{win32gui.GetWindowText(err_hw)}'")
            RoughStockService._close_error_window(err_hw)
            time.sleep(0.5)
        else:
            break


def find_part_path(assembly_product, part_name):
    """
    Recursively search the assembly tree and return the full file path
    of the part document that matches part_name.
    This is the KEY fix: we extract the file path so we can open
    the part directly (not via 'Open in New Window' which stays in Viz Mode).
    """
    result = [None]

    def _recurse(prod):
        if result[0]:
            return
        sub_prods = prod.Products
        for j in range(1, sub_prods.Count + 1):
            if result[0]:
                return
            p = sub_prods.Item(j)
            # Check if this instance matches our target
            if part_name in p.PartNumber or part_name in p.Name:
                try:
                    # Get the underlying document's full file path
                    ref_product = p.ReferenceProduct
                    parent_doc = ref_product.Parent  # The Document
                    full_path = parent_doc.FullName
                    logger.info(f"Found '{part_name}' -> file: {full_path}")
                    result[0] = full_path
                    return
                except Exception as e:
                    logger.warning(f"Could not get path for '{p.Name}': {e}")
            # Recurse into sub-assemblies
            try:
                if p.Products.Count > 0:
                    _recurse(p)
            except:
                pass

    _recurse(assembly_product)
    return result[0]


def measure_part(catia, part_name, assembly_doc):
    """Measure a single part using both Rough Stock and STL methods."""
    print(f"\n{'='*60}")
    print(f">>> MEASURING: {part_name}")
    print(f"{'='*60}")
    opened_doc = None

    try:
        cleanup_popups()

        # --- STEP 1: Find the part's file path from the assembly ---
        logger.info(f"Searching assembly for '{part_name}'...")
        file_path = find_part_path(assembly_doc.Product, part_name)

        if not file_path:
            logger.error(f"Could NOT locate file path for '{part_name}' in assembly.")
            return None

        # --- STEP 2: Open the file DIRECTLY (forces Design Mode) ---
        logger.info(f"Opening file directly: {file_path}")
        
        # Check if already open
        already_open = False
        for d in catia.Documents:
            try:
                if d.FullName == file_path:
                    opened_doc = d
                    already_open = True
                    logger.info(f"'{part_name}' is already open as {d.Name}")
                    break
            except:
                pass

        if not already_open:
            opened_doc = catia.Documents.Open(file_path)
            time.sleep(2.0)
            logger.info(f"Opened: {opened_doc.Name}")

        opened_doc.Activate()
        cleanup_popups()

        # --- STEP 3: Verify geometry exists ---
        try:
            bodies = opened_doc.Part.Bodies
            body_count = bodies.Count
            logger.info(f"Part has {body_count} bodies.")
            if body_count == 0:
                logger.error(f"Part '{opened_doc.Name}' has 0 bodies - geometry not loaded!")
                return None
        except Exception as ge:
            logger.error(f"Cannot access Part.Bodies: {ge}")
            return None

        # --- STEP 4: Switch to Generative Shape Design workbench ---
        logger.info("Switching to GSD workbench...")
        catia.StartWorkbench("CATShapeDesignWorkbench")
        time.sleep(5.0)  # Wait for workbench to fully load
        cleanup_popups()

        # --- STEP 5: Rough Stock measurement ---
        print("  [Tier 0] Running Rough Stock scraper...")
        t0 = time.time()
        dx_rs, dy_rs, dz_rs = RoughStockService.get_rough_stock_dims(catia)
        t_rs = time.time() - t0
        if dx_rs is not None:
            print(f"  [Tier 0] Result: {dx_rs:.2f} x {dy_rs:.2f} x {dz_rs:.2f}  ({t_rs:.1f}s)")
        else:
            print(f"  [Tier 0] FAILED ({t_rs:.1f}s)")

        # --- STEP 6: STL measurement (for comparison) ---
        print("  [Tier 3] Running STL method...")
        t0 = time.time()
        stl_path = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"rs_{part_name}.stl")
        stl_result = None
        try:
            opened_doc.ExportData(stl_path, "stl")
            stl_result = geometry_service._parse_stl_manual(stl_path)
        except Exception as e:
            logger.error(f"STL export/parse failed: {e}")
        t_stl = time.time() - t0

        if stl_result:
            print(f"  [Tier 3] Result: {stl_result['x']:.2f} x {stl_result['y']:.2f} x {stl_result['z']:.2f}  ({t_stl:.1f}s)")
        else:
            print(f"  [Tier 3] FAILED ({t_stl:.1f}s)")

        # --- STEP 7: Close the part if we opened it ---
        if not already_open and opened_doc:
            logger.info(f"Closing {opened_doc.Name}...")
            opened_doc.Close()

        return {
            "name": part_name,
            "rs": (dx_rs, dy_rs, dz_rs),
            "rs_time": t_rs,
            "stl": (stl_result['x'], stl_result['y'], stl_result['z']) if stl_result else (None, None, None),
            "stl_time": t_stl
        }

    except Exception as e:
        logger.exception(f"Error measuring {part_name}: {e}")
        cleanup_popups()
        return None


def main():
    try:
        catia = catia_bridge.get_application()

        # Start background dialog cleaner + selector
        RoughStockService.start_dialog_monitor(interval=0.5)

        # Find the assembly document
        active_doc = catia.ActiveDocument
        if "CATProduct" not in active_doc.Name:
            for d in catia.Documents:
                if "CATProduct" in d.Name:
                    d.Activate()
                    active_doc = d
                    break

        if "CATProduct" not in active_doc.Name:
            print("ERROR: No assembly product found. Please open the assembly.")
            return

        print(f"Assembly: {active_doc.Name}")

        # Target parts (3 for focused test)
        targets = [
            "000_LOWER_FLANGE_STEEL_01",
            "203_UPPER_FLANGE_STEEL_01",
            "004_UPPER_PAD_ST_02"
        ]

        results = []
        for t in targets:
            r = measure_part(catia, t, active_doc)
            if r:
                results.append(r)

        # Final comparison table
        print(f"\n{'='*120}")
        print(f"{'Part Name':<35} | {'Rough Stock (W x D x H)':<28} | {'STL (W x D x H)':<28} | {'Speedup'}")
        print(f"{'-'*120}")
        for r in results:
            try:
                rs = r['rs']
                rs_str = f"{rs[0]:.2f} x {rs[1]:.2f} x {rs[2]:.2f}" if rs[0] is not None else "FAILED"
                stl = r['stl']
                stl_str = f"{stl[0]:.2f} x {stl[1]:.2f} x {stl[2]:.2f}" if stl[0] is not None else "FAILED"
                spd = f"{r['stl_time']/r['rs_time']:.1f}x" if rs[0] is not None and r['rs_time'] > 0 else "N/A"
                print(f"{r['name']:<35} | {rs_str:<28} | {stl_str:<28} | {spd}")
            except Exception as te:
                print(f"Error formatting '{r.get('name','?')}': {te}")
        print(f"{'='*120}")

        RoughStockService.stop_dialog_monitor()
        print("\nDone. Review results above.")

    except Exception as e:
        logger.exception(f"Main failed: {e}")


if __name__ == "__main__":
    main()
