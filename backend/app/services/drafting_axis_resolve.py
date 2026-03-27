"""
Resolve HybridShapeAxisSystem from assembly/session (name or selection) for global drafting orientation.
"""
import logging
import time
from typing import Any, Optional, Tuple

from app.services.catia_bom_resolve import needle_matches_product, norm_path

logger = logging.getLogger(__name__)


def _activate_doc(caa, doc) -> bool:
    try:
        doc.Activate()
    except Exception:
        try:
            caa.ActiveDocument = doc
        except Exception:
            return False
    time.sleep(0.08)
    return True


def catpart_document_for_axis_object(axis_obj) -> Any:
    """Walk parents from a spec-tree object to the owning .CATPart Document."""
    cur = axis_obj
    for _ in range(48):
        if cur is None:
            return None
        try:
            par = getattr(cur, "Parent", None)
            if par is None:
                return None
            n = (getattr(par, "Name", "") or "").lower()
            if n.endswith(".catpart"):
                return par
            cur = par
        except Exception:
            return None
    return None


def _axis_name_matches_needle(needle: str, axis_obj) -> bool:
    try:
        nm = (getattr(axis_obj, "Name", "") or "").strip()
        return needle_matches_product(needle, nm, nm)
    except Exception:
        return False


def _iter_axes_in_part(part) -> Any:
    coll = getattr(part, "AxisSystems", None)
    if coll is None or coll.Count == 0:
        return
    for i in range(1, coll.Count + 1):
        try:
            yield coll.Item(i)
        except Exception:
            continue


def _part_from_product_instance(prod) -> Tuple[Optional[Any], Optional[Any]]:
    """Return (CATPart Document, Part) for a Product node, or (None, None)."""
    try:
        ref = getattr(prod, "ReferenceProduct", None)
        if ref is None:
            return None, None
        parent = getattr(ref, "Parent", None)
        if parent is None:
            return None, None
        if not (getattr(parent, "Name", "") or "").lower().endswith(".catpart"):
            return None, None
        pt = getattr(parent, "Part", None)
        return parent, pt
    except Exception:
        return None, None


def _walk_products(prod, visit):
    try:
        visit(prod)
    except Exception:
        pass
    try:
        ch = prod.Products
        for i in range(1, ch.Count + 1):
            _walk_products(ch.Item(i), visit)
    except Exception:
        pass


def resolve_axis_system_by_name(caa, needle: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    First HybridShapeAxisSystem in any open document whose name matches needle (substring).
    Scans open .CATPart and all Product instances under open .CATProduct.
    """
    nd = (needle or "").strip()
    if not nd:
        return None, None
    try:
        n_docs = int(caa.Documents.Count)
    except Exception:
        return None, None

    for di in range(1, n_docs + 1):
        try:
            doc = caa.Documents.Item(di)
            dn = (getattr(doc, "Name", "") or "").lower()
            if not dn.endswith(".catpart"):
                continue
            part = getattr(doc, "Part", None)
            if part is None:
                continue
            for ax in _iter_axes_in_part(part):
                if _axis_name_matches_needle(nd, ax):
                    logger.info("drafting_axis_resolve: matched axis %r in %s", getattr(ax, "Name", "?"), dn)
                    return ax, doc
        except Exception:
            continue

    for di in range(1, n_docs + 1):
        try:
            doc = caa.Documents.Item(di)
            if ".catproduct" not in (getattr(doc, "Name", "") or "").lower():
                continue
            root = doc.Product
            if root is None:
                continue

            found = [None, None]

            def visit(prod):
                if found[0] is not None:
                    return
                pdoc, part = _part_from_product_instance(prod)
                if part is None:
                    return
                for ax in _iter_axes_in_part(part):
                    if _axis_name_matches_needle(nd, ax):
                        found[0], found[1] = ax, pdoc
                        return

            _walk_products(root, visit)
            if found[0] is not None:
                logger.info(
                    "drafting_axis_resolve: matched axis %r in assembly tree",
                    getattr(found[0], "Name", "?"),
                )
                return found[0], found[1]
        except Exception:
            continue

    return None, None


def resolve_axis_system_from_selection(caa) -> Tuple[Optional[Any], Optional[Any]]:
    """Current selection must be a single HybridShapeAxisSystem (GetVectors works)."""
    try:
        doc = caa.ActiveDocument
        if doc is None:
            return None, None
        sel = doc.Selection
        if sel.Count < 1:
            return None, None
        val = sel.Item(1).Value
        vx = [0.0, 0.0, 0.0]
        vy = [0.0, 0.0, 0.0]
        ok = False
        try:
            val.GetVectors(vx, vy)
            ok = True
        except Exception:
            try:
                val.XAxis.GetDirection(vx)
                val.YAxis.GetDirection(vy)
                ok = True
            except Exception:
                pass
        if not ok:
            logger.warning("drafting_axis_resolve: selection is not an axis system")
            return None, None
        cat_doc = catpart_document_for_axis_object(val)
        logger.info("drafting_axis_resolve: axis from selection %r", getattr(val, "Name", "?"))
        return val, cat_doc
    except Exception as e:
        logger.warning("drafting_axis_resolve: selection failed: %s", e)
        return None, None


def rebind_axis_system_to_activated_part(axis_obj, catpart_doc) -> Any:
    """Re-fetch the axis from Part.AxisSystems after Activate(); stale refs often break GetVectors/GetDirection."""
    if axis_obj is None or catpart_doc is None:
        return axis_obj
    try:
        nm = (getattr(axis_obj, "Name", "") or "").strip()
        if not nm:
            return axis_obj
        part = getattr(catpart_doc, "Part", None)
        if part is None:
            return axis_obj
        coll = getattr(part, "AxisSystems", None)
        if coll is None or int(getattr(coll, "Count", 0) or 0) == 0:
            return axis_obj
        nm_u = nm.upper()
        for i in range(1, coll.Count + 1):
            ax = coll.Item(i)
            ax_name = (getattr(ax, "Name", "") or "").strip()
            if ax_name.upper() == nm_u or nm_u in ax_name.upper():
                logger.info("drafting_axis_resolve: rebound axis %r after activate", ax_name)
                return ax
    except Exception as e:
        logger.debug("rebind_axis_system_to_activated_part: %s", e)
    return axis_obj


def catpart_documents_same(doc_a, doc_b) -> bool:
    if doc_a is None or doc_b is None:
        return False
    try:
        return norm_path(getattr(doc_a, "FullName", "") or "") == norm_path(
            getattr(doc_b, "FullName", "") or ""
        )
    except Exception:
        return False


def copy_axis_system_into_part(
    caa: Any,
    source_axis: Any,
    source_catpart_doc: Any,
    target_catpart_doc: Any,
) -> bool:
    """
    Intentionally not implemented: Selection.Copy on HybridShapeAxisSystem triggers CATIA
    “Selected element(s) not allowed for this operation” (modal dialog) on many V5 builds.
    Add an Axis System under Part → Axis Systems manually, or use draftingAxisName on the BOM row.
    """
    logger.info(
        "copy_axis_system_into_part: skipped (CATIA blocks Copy on axis systems); target=%r",
        getattr(target_catpart_doc, "Name", "?"),
    )
    return False
