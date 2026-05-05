"""
Manual CATIA check: verify local axis resolution for 723_50_126.5_30_SETTING_RING.

Automated Copy/Paste of axis systems is disabled (CATIA blocks Selection.Copy on HybridShapeAxisSystem).

Requires: CATIA running, assembly or parts open.
Usage (PowerShell):
  cd backend
  python test_setting_ring_axis_paste.py --axis-name AXIS_LOWER_DIE
  python test_setting_ring_axis_paste.py --axis-name AXIS_LOWER_DIE --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.abspath(os.path.dirname(__file__))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.catia_bridge import catia_bridge  # noqa: E402
from app.services.drafting_axis_resolve import resolve_axis_system_by_name  # noqa: E402
from app.services.drafting_orientation import (  # noqa: E402
    catpart_document_for_part,
    front_plane_and_axis_from_part,
    part_from_generative_product,
)
from app.services.geometry_service import geometry_service  # noqa: E402
from app.services.catia_bom_resolve import (  # noqa: E402
    generative_behavior_document_target,
    resolve_bom_item_object,
)


PART_NEEDLE = "723_50_126.5_30_SETTING_RING"


def _find_item_dict(caa) -> dict:
    """Build a minimal BOM row dict matching the part file stem."""
    for di in range(1, int(caa.Documents.Count) + 1):
        try:
            doc = caa.Documents.Item(di)
            dn = (getattr(doc, "Name", "") or "").lower()
            if ".catproduct" not in dn:
                continue
            root = doc.Product

            def walk(prod):
                try:
                    nm = (getattr(prod, "Name", "") or "").upper()
                    if PART_NEEDLE.upper().replace(".", "_") in nm.replace(".", "_") or PART_NEEDLE in nm:
                        return {
                            "partNumber": PART_NEEDLE,
                            "id": PART_NEEDLE,
                            "name": prod.Name,
                        }
                except Exception:
                    pass
                try:
                    ch = prod.Products
                    for i in range(1, ch.Count + 1):
                        r = walk(ch.Item(i))
                        if r:
                            return r
                except Exception:
                    pass
                return None

            r = walk(root)
            if r:
                return r
        except Exception:
            continue
    return {"partNumber": PART_NEEDLE, "id": PART_NEEDLE}


def main() -> int:
    ap = argparse.ArgumentParser(description="Test axis copy into SETTING_RING part")
    ap.add_argument("--axis-name", default="AXIS", help="Substring for global axis (resolve_axis_system_by_name)")
    ap.add_argument("--dry-run", action="store_true", help="Only print plane resolution; no Copy/Paste")
    args = ap.parse_args()

    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not connected.")
        return 1

    item = _find_item_dict(caa)
    print(f"BOM row: {item}")

    resolved = resolve_bom_item_object(caa, item)
    if resolved is None:
        print(f"Could not resolve product/part for {PART_NEEDLE}. Open the assembly in CATIA.")
        return 2

    part_scope = geometry_service._resolve_to_part(resolved)
    if part_scope is None:
        doc_link = generative_behavior_document_target(resolved)
        part_scope = part_from_generative_product(doc_link) if doc_link else None

    if part_scope is None:
        print("Could not resolve Part scope.")
        return 3

    part_doc = catpart_document_for_part(part_scope)
    print(f"Target CATPart: {getattr(part_doc, 'Name', part_doc)}")

    pl_before, ax_before = front_plane_and_axis_from_part(part_scope, None)
    print(f"Before: local plane={pl_before is not None}, axis={getattr(ax_before, 'Name', '?')!r}")

    g_axis, g_doc = resolve_axis_system_by_name(caa, args.axis_name)
    if g_axis is None:
        print(f"No axis matching {args.axis_name!r} in open documents.")
        return 4
    print(f"Global axis: {getattr(g_axis, 'Name', '?')!r} in {getattr(g_doc, 'Name', '?')}")

    if args.dry_run:
        return 0

    if pl_before is not None:
        print("Part already has a usable local axis.")
        return 0

    print(
        "No local axis: add Part → Axis Systems in CATIA (or match global axis CATPart). "
        "Automated axis copy is not supported.",
    )
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
