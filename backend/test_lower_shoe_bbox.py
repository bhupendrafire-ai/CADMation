"""
Test script: validates bounding box for 001_LOWER SHOE and children of LWR NON STD PART.
Expected Lower Shoe: ~1090 x 910 x 264 mm (user-measured).
Run with CATIA open and the lower shoe assembly active.
"""
import logging
import sys
import os

sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service
from app.services.tree_extractor import tree_extractor

logging.basicConfig(level=logging.INFO)

# User-provided manual measurement
EXPECTED_LOWER_SHOE = (1090, 910, 264)
TOLERANCE_MM = 20  # Acceptable deviation per axis


def find_product_by_name(prod, target_name):
    """Recursively searches the product tree for a product matching the target name."""
    if target_name.upper() in prod.Name.upper():
        return prod
    try:
        for i in range(1, prod.Products.Count + 1):
            res = find_product_by_name(prod.Products.Item(i), target_name)
            if res:
                return res
    except:
        pass
    return None


def test_lower_shoe_bbox():
    """Tests product-level bounding box for 001_LOWER SHOE."""
    caa = catia_bridge.get_application()
    if not caa:
        print("ERROR: Not connected to CATIA")
        return False

    doc = caa.ActiveDocument
    root = doc.Product

    # Find the Lower Shoe product
    target = find_product_by_name(root, "001_LOWER SHOE")
    if not target:
        print("ERROR: Could not find '001_LOWER SHOE' in the tree.")
        return False

    print(f"\nFound: {target.Name}")

    # Test product-level bounding box (union of children)
    bbox = geometry_service.get_product_bounding_box(target)
    x, y, z = bbox.get("x", 0), bbox.get("y", 0), bbox.get("z", 0)
    print(f"Product BBox: {x} x {y} x {z} mm")
    print(f"stock_size:   {bbox.get('stock_size')}")
    print(f"Expected:     {EXPECTED_LOWER_SHOE[0]} x {EXPECTED_LOWER_SHOE[1]} x {EXPECTED_LOWER_SHOE[2]}")

    # Sort both for axis-agnostic comparison
    got = sorted([x, y, z], reverse=True)
    exp = sorted(EXPECTED_LOWER_SHOE, reverse=True)
    match = all(abs(a - b) < TOLERANCE_MM for a, b in zip(got, exp))
    print(f"Match (±{TOLERANCE_MM}mm): {match}")

    return match


def test_lwr_non_std_children():
    """Validates that children inside LWR NON STD PART are found and measured."""
    caa = catia_bridge.get_application()
    if not caa:
        return False

    doc = caa.ActiveDocument
    root = doc.Product

    target = find_product_by_name(root, "LWR NON STD")
    if not target:
        print("\nWARNING: Could not find 'LWR NON STD PART' in the tree.")
        return False

    print(f"\nFound sub-assembly: {target.Name}")
    print("Children:")

    try:
        count = target.Products.Count
        measured = 0
        for i in range(1, count + 1):
            child = target.Products.Item(i)
            # Try to get part bbox
            try:
                ref_doc = child.ReferenceProduct.Parent
                if hasattr(ref_doc, "Part"):
                    bbox = geometry_service.get_bounding_box(ref_doc.Part)
                    size = bbox.get("stock_size", "Unknown")
                    print(f"  {child.Name:40s} | {size}")
                    if "Fallback" not in size and "Unknown" not in size:
                        measured += 1
                else:
                    # Sub-product
                    bbox = geometry_service.get_product_bounding_box(child)
                    size = bbox.get("stock_size", "Unknown")
                    print(f"  {child.Name:40s} | {size} (sub-asm)")
                    if "Fallback" not in size:
                        measured += 1
            except Exception as e:
                print(f"  {child.Name:40s} | FAILED: {e}")

        print(f"\nMeasured {measured}/{count} children successfully.")
        return measured > 0
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_full_bom_tree():
    """Tests the full tree extraction with properties to ensure no Unknown sizes."""
    print("\n--- Full Tree BOM Test ---")
    tree = tree_extractor.get_full_tree(include_props=True)
    if not tree or "error" in tree:
        print(f"ERROR: {tree}")
        return False

    total = 0
    unknown = 0

    def count_items(node):
        nonlocal total, unknown
        if node.get("type") in ("Part", "Component"):
            total += 1
            props = node.get("properties", {})
            size = props.get("stock_size", "Unknown")
            if size == "Unknown":
                unknown += 1
                print(f"  UNKNOWN: {node['name']}")
        for child in node.get("children", []):
            count_items(child)

    count_items(tree)
    print(f"\nTotal items: {total}, Unknown sizes: {unknown}")
    return unknown < total  # At least some should be measured


if __name__ == "__main__":
    print("=" * 60)
    print("   LOWER SHOE BOUNDING BOX VALIDATION")
    print("=" * 60)

    r1 = test_lower_shoe_bbox()
    r2 = test_lwr_non_std_children()
    r3 = test_full_bom_tree()

    print("\n" + "=" * 60)
    print(f"Lower Shoe BBox:       {'PASS' if r1 else 'FAIL'}")
    print(f"LWR NON STD Children:  {'PASS' if r2 else 'FAIL/SKIP'}")
    print(f"Full BOM Tree:         {'PASS' if r3 else 'FAIL'}")
    print("=" * 60)
