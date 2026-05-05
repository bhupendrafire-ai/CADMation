"""
Visual drafting test: activate the CATPart for product 202_LOWER PLATE (if found in open docs)
and run DraftingService.create_automated_drawing().

Prerequisites: CATIA V5 running; open an assembly or the CATPart that contains 202_LOWER PLATE.

Usage (from repo):
  cd backend
  python test_drafting_202_lower_plate.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.catia_bridge import catia_bridge
from app.services.catia_bom_resolve import resolve_catpart_document_for_product_instance
from app.services.drafting_service import drafting_service

# Tree often shows "202_LOWER PLATE.1" (space); PartNumber may use space or underscore.
TARGET_NEEDLES = (
    "202_LOWER PLATE",
    "202_LOWER_PLATE",
)


def _product_matches_needles(prod) -> bool:
    try:
        nm = (getattr(prod, "Name", "") or "").upper()
        pn = (getattr(prod, "PartNumber", "") or "").upper()
        blob = f"{nm} {pn}"
        for nd in TARGET_NEEDLES:
            nu = nd.upper()
            if nu in blob:
                return True
            if nu.replace("_", " ") in blob:
                return True
            if nu.replace(" ", "_") in blob:
                return True
        # Loose: 202 + LOWER + PLATE anywhere in name/pn (handles variants)
        if "202" in blob and "LOWER" in blob and "PLATE" in blob:
            return True
    except Exception:
        pass
    return False


def find_product(prod):
    try:
        if _product_matches_needles(prod):
            return prod
    except Exception:
        pass
    try:
        ch = prod.Products
        for i in range(1, ch.Count + 1):
            r = find_product(ch.Item(i))
            if r is not None:
                return r
    except Exception:
        pass
    return None


def main():
    caa = catia_bridge.get_application()
    if not caa:
        print("ERROR: CATIA is not running or not reachable via COM.")
        print("Start CATIA, open a document that contains 202_LOWER PLATE, then run again.")
        return 1

    target = None
    part_doc = None
    try:
        for di in range(1, caa.Documents.Count + 1):
            doc = caa.Documents.Item(di)
            root = getattr(doc, "Product", None)
            if root is None:
                continue
            target = find_product(root)
            if target is not None:
                part_doc = resolve_catpart_document_for_product_instance(caa, target)
                if part_doc is not None:
                    print(
                        f"Found 202 LOWER PLATE (matched name/pn: "
                        f"{getattr(target, 'Name', '?')!r} / {getattr(target, 'PartNumber', '?')!r}) "
                        f"in: {getattr(doc, 'Name', '?')}"
                    )
                    break
    except Exception as e:
        print("ERROR scanning Documents:", e)
        return 1

    if target is None or part_doc is None:
        print("ERROR: Could not find 202 LOWER PLATE (space or underscore) in any open document.")
        print("Open the assembly (e.g. STIFFNER FENDER tool) so 202_LOWER PLATE.1 is in the tree, then run again.")
        return 1

    try:
        caa.ActiveDocument = part_doc
    except Exception as e:
        print("WARNING: could not set active document:", e)
        print("  (Drafting will still target the part by name if that CATPart is open.)")

    part_stem = (
        getattr(target, "PartNumber", None)
        or (getattr(target, "Name", "") or "").rsplit(".", 1)[0]
    )
    print(f"Using part document: {getattr(part_doc, 'Name', '?')} (stem for lookup: {part_stem!r})")
    print("Creating drawing (Front / Right / Top projection chain)...")

    # ActiveDocument is often read-only; pass part_name so the service opens the right CATPart from Documents.
    result = drafting_service.create_automated_drawing(
        part_name=part_stem,
        product_instance=target,
    )
    if result.get("error"):
        print("FAILED:", result["error"])
        return 1

    print("OK:", result.get("message", result))
    print("Drawing name:", result.get("drawing_name", "?"))
    print("Switch to the new Drawing window in CATIA to verify views.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
