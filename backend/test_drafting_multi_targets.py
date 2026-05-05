"""
Multi-part drafting test: same projection rules for several products (macro-style path in DraftingService).

Default targets (substring match on Part Number / instance Name):
  - 202_LOWER PLATE
  - LOWER STEEL        (matches names containing LOWER STEEL, spaces/underscores)

Global drafting axis (assembly): to exercise the same behavior as the BOM “Generate 2D” flow with a
shared axis, call `drafting_service.create_multi_part_layout(items, global_drafting_axis_name="AXIS_…")`
or `global_drafting_axis_use_selection=True` after selecting a HybridShapeAxisSystem in CATIA.

Prerequisites: CATIA V5; open the assembly(ies) that contain these instances.

Usage:
  cd backend
  python test_drafting_multi_targets.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.catia_bridge import catia_bridge
from app.services.catia_bom_resolve import (
    build_drafting_bom_items_from_needles,
    find_product_in_open_assemblies,
)
from app.services.drafting_service import drafting_service

# Order preserved for layout strips on the sheet.
TARGET_NEEDLES = [
    "202_LOWER PLATE",
    "LOWER STEEL",
]


def main():
    caa = catia_bridge.get_application()
    if not caa:
        print("ERROR: CATIA is not running or not reachable via COM.")
        return 1

    items, missing = build_drafting_bom_items_from_needles(caa, TARGET_NEEDLES)
    if missing:
        print("WARNING: Not found in any open .CATProduct (check spelling / open assembly):", missing)
    if not items:
        print("ERROR: No targets resolved. Open an assembly that contains at least one of:", TARGET_NEEDLES)
        return 1

    # Activate an assembly that owns the first resolved part so Selection-based resolve matches UI expectations.
    first, doc = find_product_in_open_assemblies(caa, TARGET_NEEDLES[0])
    if doc is not None:
        try:
            doc.Activate()
        except Exception:
            try:
                caa.ActiveDocument = doc
            except Exception as e:
                print("WARNING: could not activate assembly window:", e)

    print("Resolved for multi-layout:")
    for it in items:
        print(f"  partNumber={it['partNumber']!r} instanceName={it['instanceName']!r}")

    result = drafting_service.create_multi_part_layout(items)
    if result.get("error"):
        print("FAILED:", result["error"])
        for w in result.get("warnings") or []:
            print(" ", w)
        return 1

    print("OK:", result.get("message"))
    print("Drawing:", result.get("drawing_name"))
    print("Views:", len(result.get("views_created") or []), result.get("views_created"))
    for w in result.get("warnings") or []:
        print("warning:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
