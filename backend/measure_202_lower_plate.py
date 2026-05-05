"""
Measure the 202_LOWER PLATE part using both STL and ROUGH_STOCK methods.
Compares dimensions returned by each measurement tier in GeometryService.
"""
import win32com.client
import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.services.geometry_service import geometry_service


def find_part_by_substring(product, substring):
    """Recursively search the assembly tree for a product whose name contains the substring."""
    name = getattr(product, "Name", "")
    # Match on partial name (case-insensitive)
    if substring.upper() in name.upper():
        return product
    try:
        for i in range(1, product.Products.Count + 1):
            result = find_part_by_substring(product.Products.Item(i), substring)
            if result:
                return result
    except Exception:
        pass
    return None


def main():
    try:
        caa = win32com.client.GetActiveObject("CATIA.Application")
    except Exception:
        print("ERROR: CATIA is not running or not accessible.")
        return

    doc = caa.ActiveDocument
    print(f"Active document: {doc.Name}")

    # Search for 202_LOWER PLATE in the assembly tree
    target = find_part_by_substring(doc.Product, "202_LOWER")
    if not target:
        # Also try with underscore variants
        target = find_part_by_substring(doc.Product, "202 LOWER")
    if not target:
        target = find_part_by_substring(doc.Product, "LOWER PLATE")
    if not target:
        # List top-level children to help the user identify the correct name
        print("\nERROR: Could not find '202_LOWER PLATE' in the assembly tree.")
        print("Top-level children in this assembly:")
        try:
            for i in range(1, doc.Product.Products.Count + 1):
                child = doc.Product.Products.Item(i)
                print(f"  [{i}] {child.Name}  (PartNumber: {getattr(child, 'PartNumber', 'N/A')})")
        except Exception as e:
            print(f"  Could not enumerate children: {e}")
        return

    print(f"\nFound target: {target.Name}")
    print(f"  PartNumber: {getattr(target, 'PartNumber', 'N/A')}")
    print("=" * 60)

    # --- METHOD 1: STL ---
    print("\n>>> METHOD 1: STL <<<")
    geometry_service.clear_cache()
    try:
        stl_result = geometry_service.get_bounding_box(target, method="STL")
        print(f"  Method Used : {stl_result.get('method_used', 'N/A')}")
        print(f"  Stock Size  : {stl_result.get('stock_size', 'N/A')}")
        print(f"  Dimensions  : {stl_result.get('x', 0)} x {stl_result.get('y', 0)} x {stl_result.get('z', 0)} mm")
        print(f"  Confidence  : {stl_result.get('measurement_confidence', 'N/A')}")
        print(f"  Ordered Dims: {stl_result.get('orderedDims', [])}")
        print(f"  Is Round?   : {stl_result.get('is_round', False)}")
    except Exception as e:
        print(f"  STL measurement failed: {e}")
        stl_result = None

    # --- METHOD 2: ROUGH_STOCK ---
    print("\n>>> METHOD 2: ROUGH_STOCK <<<")
    geometry_service.clear_cache()
    try:
        rs_result = geometry_service.get_bounding_box(target, method="ROUGH_STOCK")
        print(f"  Method Used : {rs_result.get('method_used', 'N/A')}")
        print(f"  Stock Size  : {rs_result.get('stock_size', 'N/A')}")
        print(f"  Dimensions  : {rs_result.get('x', 0)} x {rs_result.get('y', 0)} x {rs_result.get('z', 0)} mm")
        print(f"  Confidence  : {rs_result.get('measurement_confidence', 'N/A')}")
        print(f"  Ordered Dims: {rs_result.get('orderedDims', [])}")
        print(f"  Is Round?   : {rs_result.get('is_round', False)}")
    except Exception as e:
        print(f"  ROUGH_STOCK measurement failed: {e}")
        rs_result = None

    # --- COMPARISON ---
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    if stl_result and rs_result:
        print(f"  STL         : {stl_result.get('x',0):.2f} x {stl_result.get('y',0):.2f} x {stl_result.get('z',0):.2f} mm  →  {stl_result.get('stock_size','N/A')}")
        print(f"  ROUGH_STOCK : {rs_result.get('x',0):.2f} x {rs_result.get('y',0):.2f} x {rs_result.get('z',0):.2f} mm  →  {rs_result.get('stock_size','N/A')}")
        # Delta
        dx = abs(stl_result.get('x',0) - rs_result.get('x',0))
        dy = abs(stl_result.get('y',0) - rs_result.get('y',0))
        dz = abs(stl_result.get('z',0) - rs_result.get('z',0))
        print(f"  Delta       : {dx:.2f} x {dy:.2f} x {dz:.2f} mm")
    else:
        print("  One or both methods failed — cannot compare.")


if __name__ == "__main__":
    main()
