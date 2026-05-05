import sys, os, time, logging
import win32com.client

# Add backend to path
sys.path.append(os.getcwd())
from app.services.catia_bridge import catia_bridge
from app.services.rough_stock_service import RoughStockService
from app.services.geometry_service import geometry_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("FinalVerify")

def find_all_parts(product, parts_list):
    """Recursively find all leaf parts in the assembly."""
    if product.Products.Count == 0:
        parts_list.append(product)
        return
    for i in range(1, product.Products.Count + 1):
        find_all_parts(product.Products.Item(i), parts_list)

def verify_parts():
    try:
        catia = catia_bridge.get_application()
        if not catia:
            print("ERROR: CATIA not found.")
            return

        doc = catia.ActiveDocument
        print(f"Active Document: {doc.Name}")

        all_parts = []
        if hasattr(doc, "Product"):
            print("Scanning assembly for all leaf parts...")
            find_all_parts(doc.Product, all_parts)
        else:
            all_parts = [doc]

        print(f"Found {len(all_parts)} parts to measure.")
        
        # Limit to first 20 parts if very large, or process all? 
        # Let's try up to 30 to be thorough without taking forever.
        max_parts = 30
        test_parts = all_parts[:max_parts]

        results = []
        for p_obj in test_parts:
            p_name = p_obj.PartNumber if hasattr(p_obj, "PartNumber") else p_obj.Name
            print(f"\nTargeting: {p_name}")
            try:
                start_t = time.time()
                # We pass method="ROUGH_STOCK" to force the Tier 0 path
                # We'll use the obj directly; the service now handles Body resolution
                bbox = geometry_service.get_bounding_box(p_obj, method="ROUGH_STOCK")
                elapsed = time.time() - start_t
                
                res_str = bbox.get("stock_size", "FAILED")
                print(f"RESULT: {res_str} ({elapsed:.1f}s)")
                results.append({"name": p_name, "result": res_str, "time": elapsed})
                
                # Small delay to let CATIA breathe
                time.sleep(0.5)
            except Exception as e:
                print(f"Error measuring {p_name}: {e}")
                results.append({"name": p_name, "result": f"ERROR: {str(e)[:40]}", "time": 0})

        print("\n" + "="*80)
        print(f"{'Part Number':<40} | {'Rough Stock Result':<30}")
        print("-" * 80)
        success_count = 0
        for r in results:
            status = " [OK]" if "x" in r['result'] else ""
            if status: success_count += 1
            print(f"{r['name']:<40} | {r['result']:<30}{status}")
        print("-" * 80)
        print(f"Summary: {success_count}/{len(results)} successful measurements.")
        print("="*80)

    except Exception as e:
        logger.exception(f"Verification failed: {e}")

    except Exception as e:
        logger.exception(f"Verification failed: {e}")

if __name__ == "__main__":
    verify_parts()
