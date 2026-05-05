"""
Measure all visible BOM-fast-list parts with Rough Stock (first body only, same as RoughStockService).

Before running: open CATIA Rough Stock, set the publication / axis you want, leave the dialog open.
"""
import os
import re
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("rs_visible")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.catia_bridge import catia_bridge
from app.services.bom_service import bom_service
from app.services.geometry_service import geometry_service
from app.services.rough_stock_service import RoughStockService

# Reuse BOM websocket resolution helpers
from app.routers.catia import (
    _resolve_product_for_measure,
    _resolve_obj_by_source_doc_path,
    _resolve_rough_stock_scope_product,
    _norm_path,
)


def _source_path_plausible_for_item(path: str, item_id: str) -> bool:
    # e.g. row 202_* must not bind to 001_LOWER_SHOE.CATPart when "202" is absent from the filename
    bn = "".join(c for c in os.path.basename(path or "").upper() if c.isalnum())
    for m in re.finditer(r"\d{3,}", (item_id or "").upper()):
        if m.group() not in bn:
            return False
    return True


def _resolve_item_object(caa, item):
    item_id = item.get("id") or item.get("partNumber", "")
    instance_name = item.get("instanceName") or (item.get("instances") or [f"{item_id}.1"])[0]
    source_doc_path = (item.get("sourceDocPath") or "").strip()
    doc = caa.ActiveDocument
    obj = None  # set by source path, active CATPart, or Search below

    if source_doc_path and _source_path_plausible_for_item(source_doc_path, item_id):
        obj = _resolve_obj_by_source_doc_path(caa, source_doc_path)
        if obj is not None:
            return obj, item_id, instance_name
    elif source_doc_path:
        logger.warning(
            "Skipping sourceDocPath for %r (filename missing id digit groups): %s",
            item_id,
            source_doc_path,
        )

    if ".CATPART" in doc.Name.upper():
        try:
            active_fp = _norm_path(getattr(doc, "FullName", "") or "")
        except Exception:
            active_fp = ""
        want_fp = _norm_path(source_doc_path) if source_doc_path else active_fp
        if source_doc_path and want_fp != active_fp:
            obj = None
        else:
            try:
                obj = doc.Part
            except Exception:
                obj = doc
        if obj is not None:
            return obj, item_id, instance_name

    sel = caa.ActiveDocument.Selection
    try:
        sel.Clear()
        sel.Search(f"Product.'Part Number'='{item_id}',all")
        if sel.Count > 0:
            pick = sel.Item(1).Value
            for i in range(1, sel.Count + 1):
                test_obj = sel.Item(i).Value
                if getattr(test_obj, "Name", "") == instance_name:
                    pick = test_obj
                    break
            obj = _resolve_product_for_measure(pick, item_id, instance_name)
    except Exception as e:
        logger.warning("Search failed for %s: %s", item_id, e)

    if obj is None:
        try:
            fallbacks = []
            if instance_name:
                fallbacks.append(f"Name='*{instance_name}*',all")
            fallbacks.append(f"Name='*{item_id}*',all")
            for search_query in fallbacks:
                sel.Clear()
                logger.info("Fallback search %s: %s", item_id, search_query)
                sel.Search(search_query)
                if sel.Count > 0:
                    obj = sel.Item(1).Value
                    obj = _resolve_product_for_measure(obj, item_id, instance_name)
                    break
        except Exception as e:
            logger.warning("Fallback search failed for %s: %s", item_id, e)
    return obj, item_id, instance_name


def main():
    skip_prompt = os.environ.get("CADMATION_RS_SKIP_CONFIRM", "").strip() in ("1", "true", "yes")
    if not skip_prompt:
        print(
            "\n=== Rough Stock batch (visible parts) ===\n"
            "1. In CATIA: open the Rough Stock command and leave the dialog visible.\n"
            "2. Select the correct axis / publication (e.g. AP_AXIS) in that dialog.\n"
            "3. When ready, type YES and press Enter (anything else aborts).\n"
        )
        if input().strip().upper() != "YES":
            print("Aborted.")
            return 1

    caa = catia_bridge.get_application()
    if not caa:
        print("CATIA not reachable.")
        return 2

    hw = RoughStockService.open_rough_stock_dialog(caa)
    if not hw:
        print("Rough Stock window not found. Open it, set axis, then retry.")
        return 3

    items = bom_service.get_bom_fast_list() or []
    visible = [r for r in items if r.get("keepInExport", r.get("selected", True))]
    if not visible:
        print("No visible parts from get_bom_fast_list().")
        return 4

    print(f"\nMeasuring {len(visible)} visible row(s) with rough_stock_window={hw} ...\n")
    geometry_service.clear_cache()
    rows_out = []
    for item in visible:
        obj, item_id, instance_name = _resolve_item_object(caa, item)
        label = item_id or item.get("partNumber", "?")
        if obj is None:
            print(f"  [{label}] SKIP — could not resolve")
            rows_out.append((label, None, "unresolved"))
            continue
        try:
            rs_scope = _resolve_rough_stock_scope_product(caa, obj, instance_name, item_id)
            bbox = geometry_service.get_bounding_box(
                obj,
                method="ROUGH_STOCK",
                rough_stock_window=hw,
                fast_mode=False,
                stay_open=True,
                rough_stock_scope_product=rs_scope,
            )
            ss = (bbox or {}).get("stock_size", "Not Measurable")
            raw = (bbox or {}).get("rawDims")
            if raw:
                print(f"  [{label}] {ss}  |  dialog DX,DY,DZ (mm)={raw}")
            else:
                print(f"  [{label}] {ss}")
            rows_out.append((label, bbox, "ok"))
        except Exception as e:
            print(f"  [{label}] ERROR: {e}")
            rows_out.append((label, None, str(e)))
        time.sleep(0.05)

    print("\n--- summary ---")
    for label, bbox, status in rows_out:
        if status == "ok" and bbox:
            print(f"  {label}: {bbox.get('stock_size')}")
        else:
            print(f"  {label}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
