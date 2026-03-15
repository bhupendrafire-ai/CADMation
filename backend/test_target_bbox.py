"""Debug bbox for 203_UPPER_FLANGE_STEEL_01.1; expected: 163.14 x 310 x 160 mm."""
import logging
import sys
import os

sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

logging.basicConfig(level=logging.INFO)

EXPECTED = (163.14, 310.0, 160.0)


def check_target_size():
    target_name = "203_UPPER_FLANGE_STEEL_01.1"

    caa = catia_bridge.get_application()
    if not caa:
        print("Not connected to CATIA")
        return

    doc = caa.ActiveDocument

    def find_target(prod):
        if target_name in prod.Name:
            return prod
        for i in range(1, prod.Products.Count + 1):
            res = find_target(prod.Products.Item(i))
            if res:
                return res
        return None

    target_prod = find_target(doc.Product)

    if not target_prod:
        print(f"Could not find {target_name} in the tree.")
        return

    print(f"\nFound Target: {target_prod.Name}")

    try:
        ref_doc = target_prod.ReferenceProduct.Parent
        part = ref_doc.Part

        print("\n--- GeometryService (part-local AABB first) ---")
        bbox = geometry_service.get_bounding_box(part)
        x, y, z = bbox.get("x"), bbox.get("y"), bbox.get("z")
        print(f"Extracted: {x} x {y} x {z} mm")
        print(f"stock_size: {bbox.get('stock_size')}")

        if "xmin" in bbox:
            print(f"AABB min: ({bbox['xmin']}, {bbox['ymin']}, {bbox['zmin']}) mm")
            print(f"AABB max: ({bbox['xmax']}, {bbox['ymax']}, {bbox['zmax']}) mm")

        print("\n--- Expected ---")
        print(f"Expected: {EXPECTED[0]} x {EXPECTED[1]} x {EXPECTED[2]} mm")

        got = (float(x), float(y), float(z))
        perm = sorted(got, reverse=True)
        exp_perm = sorted(EXPECTED, reverse=True)
        match = all(abs(a - b) < 0.1 for a, b in zip(perm, exp_perm))
        print(f"Match (sorted): {match}")

        print("\n--- Raw properties ---")
        product = target_prod.ReferenceProduct
        print(f"Volume: {product.Analyze.Volume:.2f}")
        print(f"Mass: {product.Analyze.Mass:.3f} kg")
        print(f"WetArea: {product.Analyze.WetArea:.2f}")

    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_target_size()
