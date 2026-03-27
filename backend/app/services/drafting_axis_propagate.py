"""
Propagate a resolved global HybridShapeAxisSystem orientation into leaf CATParts by creating
AXIS_DRAFTING_GLOBAL under Part.AxisSystems (PutOrigin + PutVectors). Does not use Selection.Copy.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.catia_bom_resolve import (
    generative_behavior_document_target,
    resolve_bom_item_object,
)
from app.services.drafting_axis_resolve import (
    catpart_document_for_axis_object,
    catpart_documents_same,
    rebind_axis_system_to_activated_part,
    resolve_axis_system_by_name,
    resolve_axis_system_from_selection,
)
from app.services.drafting_orientation import (
    catpart_document_for_part,
    front_plane_and_axis_from_part,
    orthonormal_basis_from_axis_with_fallbacks,
    part_from_generative_product,
)
from app.services.geometry_service import geometry_service

logger = logging.getLogger(__name__)

AXIS_DRAFTING_GLOBAL = "AXIS_DRAFTING_GLOBAL"
_PRIMARY_DEFINE_FRONT = "xz"


def _activate_doc(caa: Any, doc: Any) -> bool:
    try:
        doc.Activate()
    except Exception:
        try:
            caa.ActiveDocument = doc
        except Exception:
            return False
    time.sleep(0.08)
    return True


def part_key_from_item(item: Dict[str, Any], idx: int) -> str:
    sid = item.get("sourceRowId")
    if sid:
        return str(sid)
    pid = item.get("partNumber") or item.get("id") or f"row_{idx}"
    inst = item.get("instanceName") or ""
    return f"{pid}|{inst}"


def axis_named_exists(part_scope: Any, name: str) -> bool:
    if part_scope is None:
        return False
    want = (name or "").strip().upper()
    if not want:
        return False
    try:
        coll = getattr(part_scope, "AxisSystems", None)
        if coll is None or int(getattr(coll, "Count", 0) or 0) == 0:
            return False
        for i in range(1, coll.Count + 1):
            ax = coll.Item(i)
            nm = (getattr(ax, "Name", "") or "").strip().upper()
            if nm == want:
                return True
    except Exception as e:
        logger.debug("axis_named_exists: %s", e)
    return False


def skip_reason_for_propagate_target(
    part_doc: Any,
    global_cat_doc: Any,
    part_scope: Any,
    propagated_name: str = AXIS_DRAFTING_GLOBAL,
) -> Optional[str]:
    """None = should create axis; else CATIA-safe skip reason code."""
    if part_doc is None:
        return "unresolved_document"
    if global_cat_doc is not None and catpart_documents_same(part_doc, global_cat_doc):
        return "same_document_as_global_axis"
    if axis_named_exists(part_scope, propagated_name):
        return "axis_already_propagated"
    plane, _ = front_plane_and_axis_from_part(
        part_scope, prefer_axis_name=None, primary_define_front=_PRIMARY_DEFINE_FRONT
    )
    if plane is not None:
        return "already_has_usable_axis"
    return None


def _create_axis_with_putvectors(part_scope: Any, ex: List[float], ey: List[float], name: str) -> None:
    coll = getattr(part_scope, "AxisSystems", None)
    if coll is None:
        raise RuntimeError("Part has no AxisSystems collection")
    ax = None
    try:
        ax = coll.Add()
    except Exception as e1:
        logger.debug("AxisSystems.Add failed: %s", e1)
        try:
            ax = coll.AddNewAxisSystem()
        except Exception as e2:
            logger.debug("AddNewAxisSystem failed: %s", e2)
            raise RuntimeError("Could not create axis (AxisSystems.Add)") from e1
    if ax is None:
        raise RuntimeError("AxisSystems add returned None")
    ax.Name = name
    origin = (0.0, 0.0, 0.0)
    try:
        ax.PutOrigin(origin)
    except Exception:
        try:
            ax.PutOrigin([0.0, 0.0, 0.0])
        except Exception as e:
            logger.warning("PutOrigin failed: %s", e)
    vx = (float(ex[0]), float(ex[1]), float(ex[2]))
    vy = (float(ey[0]), float(ey[1]), float(ey[2]))
    try:
        ax.PutVectors(vx, vy)
    except Exception:
        ax.PutVectors([vx[0], vx[1], vx[2]], [vy[0], vy[1], vy[2]])
    try:
        part_scope.UpdateObject(ax)
    except Exception:
        try:
            part_scope.Update()
        except Exception as ue:
            logger.debug("Part.Update after axis: %s", ue)


def create_propagated_axis_in_part(
    part_scope: Any,
    ex: List[float],
    ey: List[float],
    ez: List[float],
    name: str = AXIS_DRAFTING_GLOBAL,
) -> None:
    """Create a new HybridShapeAxisSystem; ex,ey,ez orthonormal (ez unused if PutVectors takes X,Y)."""
    _ = ez
    _create_axis_with_putvectors(part_scope, ex, ey, name)


def resolve_global_axis_for_propagate(
    caa: Any,
    global_drafting_axis_name: Optional[str],
    use_selection: bool,
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    if use_selection:
        axis, doc = resolve_axis_system_from_selection(caa)
        if axis is None:
            return None, None, "Could not resolve axis from selection"
        if doc is None:
            doc = catpart_document_for_axis_object(axis)
        return axis, doc, None
    nd = (global_drafting_axis_name or "").strip()
    if not nd:
        return None, None, "Provide global drafting axis name or use selection"
    axis, doc = resolve_axis_system_by_name(caa, nd)
    if axis is None:
        return None, None, f"No axis matches name {nd!r}"
    return axis, doc, None


def _basis_from_global_axis(caa: Any, axis: Any, cat_doc: Any) -> Optional[Tuple[List[float], List[float], List[float]]]:
    owner = cat_doc or catpart_document_for_axis_object(axis)
    if owner is not None:
        _activate_doc(caa, owner)
        axis = rebind_axis_system_to_activated_part(axis, owner)
    # Match multi-layout: CATScript when Python COM GetVectors/out-params fail on the axis ref
    return orthonormal_basis_from_axis_with_fallbacks(caa, owner, axis)


def _resolve_part_scope(caa: Any, item: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Any]]:
    resolved = resolve_bom_item_object(caa, item)
    if resolved is None:
        return None, None
    part_scope = geometry_service._resolve_to_part(resolved)
    if part_scope is None:
        part_scope = part_from_generative_product(generative_behavior_document_target(resolved))
    part_doc = catpart_document_for_part(part_scope) if part_scope is not None else None
    return part_scope, part_doc


def preview_propagate(
    caa: Any,
    items: List[Dict[str, Any]],
    global_drafting_axis_name: Optional[str],
    use_selection: bool,
) -> Dict[str, Any]:
    """Read-only: classify BOM rows (includeIn2dDrawing) for propagation."""
    g_axis, g_doc, err = resolve_global_axis_for_propagate(caa, global_drafting_axis_name, use_selection)
    if err:
        return {"ok": False, "error": err, "candidates": [], "globalResolved": False}
    assert g_axis is not None
    candidates: List[Dict[str, Any]] = []
    for idx, item in enumerate(items or []):
        if not item.get("includeIn2dDrawing"):
            continue
        pk = part_key_from_item(item, idx)
        part_scope, part_doc = _resolve_part_scope(caa, item)
        if part_scope is None:
            candidates.append(
                {"partKey": pk, "action": "error", "reason": "unresolved_bom_row"}
            )
            continue
        if part_doc is None:
            candidates.append(
                {"partKey": pk, "action": "error", "reason": "no_catpart_document"}
            )
            continue
        why = skip_reason_for_propagate_target(part_doc, g_doc, part_scope)
        if why:
            candidates.append({"partKey": pk, "action": "skip", "reason": why})
        else:
            candidates.append({"partKey": pk, "action": "would_create"})
    return {
        "ok": True,
        "globalResolved": True,
        "candidates": candidates,
        "propagatedAxisName": AXIS_DRAFTING_GLOBAL,
    }


def execute_propagate(
    caa: Any,
    items: List[Dict[str, Any]],
    global_drafting_axis_name: Optional[str],
    use_selection: bool,
) -> Dict[str, Any]:
    g_axis, g_doc, err = resolve_global_axis_for_propagate(caa, global_drafting_axis_name, use_selection)
    if err:
        return {"ok": False, "error": err, "updated": [], "skipped": [], "errors": []}
    assert g_axis is not None
    basis = _basis_from_global_axis(caa, g_axis, g_doc)
    if basis is None:
        return {
            "ok": False,
            "error": "Could not read orthonormal basis from global axis",
            "updated": [],
            "skipped": [],
            "errors": [],
        }
    ex, ey, ez = basis
    updated: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for idx, item in enumerate(items or []):
        if not item.get("includeIn2dDrawing"):
            continue
        pk = part_key_from_item(item, idx)
        part_scope, part_doc = _resolve_part_scope(caa, item)
        if part_scope is None or part_doc is None:
            errors.append({"partKey": pk, "message": "Could not resolve BOM row to CATPart"})
            continue
        why = skip_reason_for_propagate_target(part_doc, g_doc, part_scope)
        if why:
            skipped.append({"partKey": pk, "reason": why})
            continue
        try:
            _activate_doc(caa, part_doc)
            create_propagated_axis_in_part(part_scope, ex, ey, ez, AXIS_DRAFTING_GLOBAL)
            try:
                fp = getattr(part_doc, "FullName", "") or ""
            except Exception:
                fp = ""
            updated.append({"partKey": pk, "catpartFullName": fp})
        except Exception as e:
            logger.exception("execute_propagate row %s", pk)
            errors.append({"partKey": pk, "message": str(e)})

    return {
        "ok": True,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "propagatedAxisName": AXIS_DRAFTING_GLOBAL,
    }
