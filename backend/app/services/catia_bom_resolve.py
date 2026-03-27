"""
Resolve BOM row dicts to CATIA Part/Product COM objects (shared by measurement and drafting).
"""
import logging
import os
import re
import time
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def norm_path(path: str) -> str:
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(path or "")))
    except Exception:
        return (path or "").strip().lower()


def _source_path_plausible_for_item(path: str, item_id: str) -> bool:
    """Avoid binding a BOM row to the wrong CATPart when filenames share no digit group with the part id."""
    try:
        bn = "".join(c for c in os.path.basename(path or "").upper() if c.isalnum())
        for m in re.finditer(r"\d{3,}", (item_id or "").upper()):
            if m.group() not in bn:
                return False
        return True
    except Exception:
        return True


def resolve_product_for_measure(product, part_number: str, instance_name: str):
    """Resolve to a single instance; never return an assembly when multiple instances of same part exist."""
    try:
        if not hasattr(product, "Products") or product.Products.Count == 0:
            return product
        pn = (getattr(product, "PartNumber", "") or "").strip()
        name = getattr(product, "Name", "") or ""
        if pn == part_number and name == instance_name:
            return product
        first_matching = None
        for i in range(1, product.Products.Count + 1):
            child = product.Products.Item(i)
            try:
                c_pn = (getattr(child, "PartNumber", "") or "").strip()
                c_name = getattr(child, "Name", "") or ""
                if c_pn == part_number:
                    if first_matching is None:
                        first_matching = child
                    if c_name == instance_name or not instance_name:
                        return child
                if hasattr(child, "Products") and child.Products.Count > 0:
                    deeper = resolve_product_for_measure(child, part_number, instance_name)
                    if deeper is not None:
                        return deeper
            except Exception:
                continue
        return first_matching if first_matching is not None else product
    except Exception:
        return product


def _norm_part_stem(s: str) -> str:
    return "".join((s or "").upper().split()).replace("_", "").replace("-", "")


def resolve_catpart_document_for_product_instance(caa, product_instance) -> Optional[Any]:
    """Map assembly Product instance to defining CATPart Document (Parent/FullName alone are unreliable with many parts open)."""
    try:
        ref = product_instance.ReferenceProduct
    except Exception:
        return None
    ref_name = ""
    try:
        ref_name = (getattr(ref, "Name", "") or "").strip()
    except Exception:
        pass
    pn = ""
    try:
        pn = (getattr(product_instance, "PartNumber", "") or "").strip()
    except Exception:
        pass
    pnu = _norm_part_stem(pn) if pn else ""

    def _open_catparts():
        for i in range(1, caa.Documents.Count + 1):
            try:
                d = caa.Documents.Item(i)
                if (getattr(d, "Name", "") or "").lower().endswith(".catpart"):
                    yield d
            except Exception:
                continue

    # 1) PartNumber vs file stem (most stable when several CATParts are open)
    if pnu:
        for d in _open_catparts():
            try:
                stem = (getattr(d, "Name", "") or "").rsplit(".", 1)[0]
                if _norm_part_stem(stem) == pnu:
                    return d
            except Exception:
                continue

    # 2) Internal Part.Name vs ReferenceProduct.Name (file stem must match PartNumber when set — names can duplicate across open CATParts)
    if ref_name:
        for d in _open_catparts():
            try:
                part_nm = (getattr(d.Part, "Name", "") or "").strip()
                if not part_nm or part_nm != ref_name:
                    continue
                if pnu:
                    stem = (getattr(d, "Name", "") or "").rsplit(".", 1)[0]
                    if _norm_part_stem(stem) != pnu:
                        continue
                return d
            except Exception:
                continue

    # 3) Defining file path — only if basename matches PartNumber (FullName can point at the wrong file)
    ref_path = ""
    try:
        raw_fp = (getattr(ref, "FullName", "") or "").strip()
        if raw_fp and raw_fp.lower().endswith((".catpart", ".CATPart")):
            ref_path = norm_path(raw_fp)
    except Exception:
        pass
    if ref_path and pnu:
        try:
            bn = os.path.basename(ref_path)
            stem_fp = os.path.splitext(bn)[0]
            if _norm_part_stem(stem_fp) != pnu:
                ref_path = ""
        except Exception:
            ref_path = ""
    if ref_path:
        for d in _open_catparts():
            try:
                dp = norm_path(getattr(d, "FullName", "") or "")
                if dp and dp == ref_path:
                    return d
            except Exception:
                continue

    # 4) Parent only when Part internal name and file stem agree
    try:
        p = ref.Parent
        if (getattr(p, "Name", "") or "").lower().endswith(".catpart"):
            p_part_nm = (getattr(p.Part, "Name", "") or "").strip()
            if ref_name and p_part_nm == ref_name:
                if pnu:
                    stem = (getattr(p, "Name", "") or "").rsplit(".", 1)[0]
                    if _norm_part_stem(stem) != pnu:
                        return None
                return p
    except Exception:
        pass
    return None


def _activate_doc_for_search(caa, doc) -> bool:
    try:
        doc.Activate()
    except Exception:
        try:
            caa.ActiveDocument = doc
        except Exception:
            return False
    time.sleep(0.1)
    return True


def _resolve_bom_item_via_selection(caa, item: dict, item_id: str, instance_name: str) -> Optional[Any]:
    """Part Number + name Search on whichever document is currently active."""
    obj = None
    try:
        sel = caa.ActiveDocument.Selection
        sel.Clear()
        if str(item_id).strip():
            try:
                sel.Search(f"Product.'Part Number'='{item_id}',all")
                if sel.Count > 0:
                    pick = sel.Item(1).Value
                    for i in range(1, sel.Count + 1):
                        test_obj = sel.Item(i).Value
                        if getattr(test_obj, "Name", "") == instance_name:
                            pick = test_obj
                            break
                    obj = resolve_product_for_measure(pick, item_id, instance_name)
                    if obj is not None:
                        return obj
            except Exception as se:
                logger.warning("BOM resolve Part Number search failed for %s: %s", item_id, se)

        fallbacks = []
        if instance_name:
            if item.get("isManualRow"):
                fallbacks.append(f"Name='{instance_name}',all")
            fallbacks.append(f"Name='*{instance_name}*',all")
        if item_id:
            fallbacks.append(f"Name='*{item_id}*',all")
        for fq in fallbacks:
            try:
                sel.Clear()
                sel.Search(fq)
                if sel.Count > 0:
                    obj = sel.Item(1).Value
                    obj = resolve_product_for_measure(obj, item_id, instance_name)
                    if obj is not None:
                        return obj
            except Exception:
                continue
    except Exception as e:
        logger.debug("_resolve_bom_item_via_selection: %s", e)
    return None


def _resolve_bom_item_scan_open_catproducts(caa, item: dict, item_id: str, instance_name: str) -> Optional[Any]:
    """When ActiveDocument is not the owning assembly, retry Selection on every open .CATProduct."""
    try:
        n = int(caa.Documents.Count)
    except Exception:
        return None
    for i in range(1, n + 1):
        try:
            d = caa.Documents.Item(i)
            if ".catproduct" not in (getattr(d, "Name", "") or "").lower():
                continue
            if not _activate_doc_for_search(caa, d):
                continue
            hit = _resolve_bom_item_via_selection(caa, item, item_id, instance_name)
            if hit is not None:
                return hit
        except Exception:
            continue
    return None


def needle_matches_product(needle: str, pn: str, nm: str) -> bool:
    """Substring match for drafting/BOM needles vs PartNumber / instance Name (spaces vs underscores)."""
    nd = (needle or "").strip().upper().rstrip("_")
    if not nd:
        return False
    pn_u = (pn or "").strip().upper()
    nm_u = (nm or "").strip().upper()
    blob = f"{pn_u} {nm_u}".replace("_", " ")
    nd_sp = nd.replace("_", " ")
    return nd in pn_u or nd in nm_u or nd_sp in blob


def find_product_matching_needle(root, needle: str) -> Optional[Any]:
    """First Product in tree whose PartNumber or Name matches needle (substring, case-insensitive)."""
    nd = (needle or "").strip().upper().rstrip("_")
    if not nd:
        return None

    def walk(prod) -> Optional[Any]:
        try:
            pn = (getattr(prod, "PartNumber", "") or "").strip()
            nm = getattr(prod, "Name", "") or ""
            if needle_matches_product(needle, pn, nm):
                return prod
        except Exception:
            pass
        try:
            ch = prod.Products
            for i in range(1, ch.Count + 1):
                r = walk(ch.Item(i))
                if r is not None:
                    return r
        except Exception:
            pass
        return None

    try:
        return walk(root)
    except Exception:
        return None


def find_product_in_open_assemblies(caa, needle: str) -> Tuple[Optional[Any], Optional[Any]]:
    """Return (Product instance, owning CATProduct Document) or (None, None)."""
    try:
        n = int(caa.Documents.Count)
    except Exception:
        return None, None
    for i in range(1, n + 1):
        try:
            doc = caa.Documents.Item(i)
            if ".catproduct" not in (getattr(doc, "Name", "") or "").lower():
                continue
            root = doc.Product
            if root is None:
                continue
            hit = find_product_matching_needle(root, needle)
            if hit is not None:
                return hit, doc
        except Exception:
            continue
    return None, None


def build_drafting_bom_items_from_needles(caa, needles: List[str]) -> Tuple[List[dict], List[str]]:
    """
    Build BOM-style dicts for multi-layout drafting from substring needles (scans open assemblies).
    Uses actual PartNumber / instance Name from the tree so Selection resolves consistently.
    """
    items: List[dict] = []
    missing: List[str] = []
    seen_pn: set = set()
    for needle in needles:
        raw = (needle or "").strip()
        if not raw:
            continue
        prod, _doc = find_product_in_open_assemblies(caa, raw)
        if prod is None:
            missing.append(raw)
            continue
        pn = (getattr(prod, "PartNumber", "") or "").strip()
        nm = getattr(prod, "Name", "") or ""
        key = (pn, nm)
        if key in seen_pn:
            continue
        seen_pn.add(key)
        items.append(
            {
                "id": pn or raw,
                "partNumber": pn,
                "instanceName": nm,
            }
        )
    return items, missing


def resolve_obj_by_source_doc_path(caa, source_doc_path: str):
    """Open document matching normalized path; return Part or Product."""
    src = norm_path(source_doc_path)
    if not src:
        return None
    try:
        for i in range(1, caa.Documents.Count + 1):
            d = caa.Documents.Item(i)
            d_path = norm_path(getattr(d, "FullName", "") or "")
            if d_path != src:
                continue
            try:
                if getattr(d, "Part", None) is not None:
                    return d.Part
            except Exception:
                pass
            try:
                if getattr(d, "Product", None) is not None:
                    return d.Product
            except Exception:
                pass
    except Exception:
        pass
    return None


def resolve_bom_item_object(caa, item: dict) -> Any:
    """
    Resolve BOM row to a Part/Product COM object. Order matches run_rough_stock_visible_parts:
    plausible sourceDocPath first, then active CATPart only when path matches (or no path),
    then Part Number search and name fallbacks, last-chance open document by path.
    """
    if item.get("isManualRow"):
        item_id = (item.get("partNumber") or "").strip()
    else:
        item_id = item.get("id") or item.get("partNumber") or ""
    instances = item.get("instances") or []
    instance_name = item.get("instanceName") or (instances[0] if instances else None) or (
        f"{item_id}.1" if item_id else ""
    )
    source_doc_path = (item.get("sourceDocPath") or "").strip()
    obj = None
    try:
        doc = caa.ActiveDocument
    except Exception:
        return None
    if doc is None:
        return None

    try:
        if source_doc_path and _source_path_plausible_for_item(source_doc_path, item_id):
            obj = resolve_obj_by_source_doc_path(caa, source_doc_path)
            if obj is not None:
                return obj

        if ".CATPART" in (getattr(doc, "Name", "") or "").upper():
            try:
                active_fp = norm_path(getattr(doc, "FullName", "") or "")
            except Exception:
                active_fp = ""
            want_fp = norm_path(source_doc_path) if source_doc_path else active_fp
            if not source_doc_path or want_fp == active_fp:
                try:
                    obj = doc.Part
                except Exception:
                    obj = doc
                if obj is not None:
                    return obj

        obj = _resolve_bom_item_via_selection(caa, item, item_id, instance_name)

        if obj is None and source_doc_path:
            obj = resolve_obj_by_source_doc_path(caa, source_doc_path)

        if obj is None:
            obj = _resolve_bom_item_scan_open_catproducts(caa, item, item_id, instance_name)
    except Exception as e:
        logger.error("resolve_bom_item_object: %s", e)
        return None
    return obj


def generative_behavior_document_target(resolved_obj) -> Optional[Any]:
    """Object to assign to View.GenerativeBehavior.Document (Product ref or Part document)."""
    try:
        if getattr(resolved_obj, "ReferenceProduct", None) is not None:
            return resolved_obj.ReferenceProduct
        parent = getattr(resolved_obj, "Parent", None)
        if parent is not None and getattr(parent, "Part", None) is not None:
            return parent
    except Exception:
        pass
    return resolved_obj
