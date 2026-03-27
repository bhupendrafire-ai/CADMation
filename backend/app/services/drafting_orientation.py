"""
Resolve DefineFrontView(V1,V2) from Part.AxisSystems only (e.g. AXIS_LOWER_DIE).

Does not use root Default Planes / standalone xy plane features — those are ignored; orientation
comes from the chosen HybridShapeAxisSystem. Default DefineFrontView uses the XZ plane (front elevation);
child TOP/RIGHT then yield plan + side. Using XY as main duplicated the TOP child (two plan views).

Reference macro (manual front plane + projections, no SetAxisSysteme): backend/2dplaneselection.catvbs
— Document = partDocument.GetItem("202_LOWER PLATE"); DefineFrontView uses six recorded cosines
from the picked plane; then DefineProjectionView + CopyLinksTo + AlignedWithReferenceView.
"""
import array
import logging
import math
import unittest.mock as _mock
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fallback when no usable axis / basis (YZ plane, CAADoc-style)
DEFAULT_FRONT_PLANE = (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _norm3(v: List[float]) -> Optional[List[float]]:
    l = math.sqrt(sum(x * x for x in v))
    if l <= 1e-12:
        return None
    return [x / l for x in v]


def _cross(a: List[float], b: List[float]) -> List[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _vec_sum_abs(v: List[float]) -> float:
    return sum(abs(x) for x in v)


def _as_list3(v: Any) -> Optional[List[float]]:
    if v is None:
        return None
    try:
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            return [float(v[0]), float(v[1]), float(v[2])]
        return [float(v[0]), float(v[1]), float(v[2])]
    except Exception:
        pass
    try:
        return [float(x) for x in v.tolist()[:3]]
    except Exception:
        return None


def _unwrap_axis_line(ref: Any) -> Any:
    if ref is None or isinstance(ref, _mock.Mock):
        return ref
    try:
        if hasattr(ref, "GetItem"):
            return ref.GetItem()
    except Exception:
        pass
    return ref


def _line_direction3(line_obj: Any) -> Optional[List[float]]:
    """Unit direction from a line / axis line (CATIA exposes several COM patterns)."""
    line_obj = _unwrap_axis_line(line_obj)
    if line_obj is None:
        return None
    for buf in ([0.0, 0.0, 0.0], array.array("d", [0.0, 0.0, 0.0])):
        try:
            line_obj.GetDirection(buf)
            v3 = _as_list3(buf)
            if v3 and _vec_sum_abs(v3) > 1e-12:
                return v3
        except Exception as e:
            logger.debug("line GetDirection: %s", e)
    try:
        d = getattr(line_obj, "Direction", None)
        if d is not None:
            c = [0.0, 0.0, 0.0]
            d.GetCoordinates(c)
            v3 = _as_list3(c)
            if v3 and _vec_sum_abs(v3) > 1e-12:
                return v3
    except Exception as e:
        logger.debug("line Direction.GetCoordinates: %s", e)
    return None


def _try_getvectors_pair(axis_obj) -> Optional[Tuple[List[float], List[float]]]:
    try:
        r = axis_obj.GetVectors()
        if isinstance(r, (tuple, list)) and len(r) >= 2:
            vx = _as_list3(r[0])
            vy = _as_list3(r[1])
            if vx and vy and _vec_sum_abs(vx) > 1e-12 and _vec_sum_abs(vy) > 1e-12:
                return vx, vy
    except Exception as e:
        logger.debug("axis GetVectors() retval: %s", e)
    for vx, vy in (
        ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
        (array.array("d", [0.0, 0.0, 0.0]), array.array("d", [0.0, 0.0, 0.0])),
    ):
        try:
            axis_obj.GetVectors(vx, vy)
            vx3 = _as_list3(vx)
            vy3 = _as_list3(vy)
            if vx3 and vy3 and _vec_sum_abs(vx3) > 1e-12 and _vec_sum_abs(vy3) > 1e-12:
                return vx3, vy3
        except Exception as e:
            logger.debug("axis GetVectors(buf): %s", e)
    return None


def _axis_xy_directions_raw(axis_obj) -> Optional[Tuple[List[float], List[float]]]:
    """Non-unit X/Y directions for the axis XY plane; None if unavailable."""
    pair = _try_getvectors_pair(axis_obj)
    if pair is not None:
        return pair
    vx = _line_direction3(getattr(axis_obj, "XAxis", None))
    vy = _line_direction3(getattr(axis_obj, "YAxis", None))
    if vx is not None and vy is not None and _vec_sum_abs(vx) > 1e-12 and _vec_sum_abs(vy) > 1e-12:
        return vx, vy
    vx = _line_direction3(getattr(axis_obj, "XAxis", None))
    vz = _line_direction3(getattr(axis_obj, "ZAxis", None))
    if vx is not None and vz is not None:
        ey_raw = _cross(vz, vx)
        if _vec_sum_abs(ey_raw) > 1e-12:
            return vx, ey_raw
    vy = _line_direction3(getattr(axis_obj, "YAxis", None))
    vz = _line_direction3(getattr(axis_obj, "ZAxis", None))
    if vy is not None and vz is not None:
        ex_raw = _cross(vy, vz)
        if _vec_sum_abs(ex_raw) > 1e-12:
            return ex_raw, vy
    try:
        nm = getattr(axis_obj, "Name", "?")
    except Exception:
        nm = "?"
    logger.warning("drafting_orientation: could not read axis vectors for %r", nm)
    return None


def orthonormal_basis_from_axis_system(axis_obj) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """Return (ex, ey, ez) unit vectors; None if unreadable."""
    try:
        pair = _axis_xy_directions_raw(axis_obj)
        if pair is None:
            return None
        vx, vy = pair
        ex = _norm3(vx)
        ey_raw = _norm3(vy)
        if not ex or not ey_raw:
            return None
        ez = _norm3(_cross(ex, ey_raw))
        if not ez:
            return None
        ey = _norm3(_cross(ez, ex))
        if not ey:
            return None
        return ex, ey, ez
    except Exception as e:
        logger.debug("orthonormal_basis_from_axis_system: %s", e)
        return None


def _axis_sort_key(name: str) -> Tuple[int, int, str]:
    """
    Prefer specific designer AXIS_* (longer names beat AXIS_A vs AXIS_LOWER_DIE); Absolute/Default last.
    Tuple sorts ascending: lower tier first, then longer name (secondary = -len).
    """
    raw = (name or "").strip()
    u = raw.upper()
    if "ABSOLUTE" in u:
        return (3, 0, raw)
    if "DEFAULT" in u and "AXIS" in u:
        return (3, 0, raw)
    if "AXIS_" in u:
        return (0, -len(raw), raw)
    if u.startswith("AXIS"):
        return (1, -len(raw), raw)
    if "MAIN" in u or "PART" in u:
        return (2, -len(raw), raw)
    return (2, -len(raw), raw)


def pick_axis_system(part, prefer_name: Optional[str] = None) -> Any:
    """Choose HybridShapeAxisSystem under Part.AxisSystems — not the Part root Default Planes."""
    try:
        coll = getattr(part, "AxisSystems", None)
        if coll is None or coll.Count == 0:
            return None
        if prefer_name and str(prefer_name).strip():
            sub = str(prefer_name).strip().upper()
            for i in range(1, coll.Count + 1):
                ax = coll.Item(i)
                nm = (getattr(ax, "Name", "") or "").upper()
                if sub in nm:
                    logger.info("Drafting orientation: using requested axis %r", getattr(ax, "Name", "?"))
                    return ax
        items = []
        for i in range(1, coll.Count + 1):
            ax = coll.Item(i)
            nm = getattr(ax, "Name", "") or ""
            items.append((_axis_sort_key(nm), ax))
        items.sort(key=lambda x: x[0])
        # Never use Absolute/default-like axis if a designer AXIS_* (or other tier<3) exists
        if items:
            best_tier = items[0][0][0]
            if best_tier >= 3:
                non_generic = [x for x in items if x[0][0] < 3]
                if non_generic:
                    items = non_generic
        chosen = items[0][1]
        logger.info("Drafting orientation: picked axis %r", getattr(chosen, "Name", "?"))
        return chosen
    except Exception as e:
        logger.debug("pick_axis_system: %s", e)
        return None


def _orthonormal_basis_from_raw_xy_pair(
    vx: List[float], vy: List[float],
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    ex = _norm3(vx)
    ey_raw = _norm3(vy)
    if not ex or not ey_raw:
        return None
    ez = _norm3(_cross(ex, ey_raw))
    if not ez:
        return None
    ey = _norm3(_cross(ez, ex))
    if not ey:
        return None
    return ex, ey, ez


def _basis_six_for_primary(
    ex: List[float],
    ey: List[float],
    ez: List[float],
    primary_define_front: str,
) -> Tuple[float, float, float, float, float, float]:
    """DefineFrontView(V1,V2): V1×V2 = view normal. xy=plan, xz=front elevation, yz=side (plate-style triple)."""
    p = (primary_define_front or "xz").lower()
    if p == "xy":
        return (ex[0], ex[1], ex[2], ey[0], ey[1], ey[2])
    if p == "yz":
        return (ey[0], ey[1], ey[2], ez[0], ez[1], ez[2])
    # "xz" default: main = front (XZ plane), TOP/RIGHT children = plan + side
    return (ex[0], ex[1], ex[2], ez[0], ez[1], ez[2])


def _plane_six_from_raw_xy(vx: List[float], vy: List[float]) -> Optional[Tuple[float, float, float, float, float, float]]:
    basis = _orthonormal_basis_from_raw_xy_pair(vx, vy)
    if not basis:
        return None
    ex, ey, ez = basis
    return _basis_six_for_primary(ex, ey, ez, "xy")


def _update_part_for_axis_geometry(catpart_doc: Any, axis_obj: Any) -> None:
    if catpart_doc is None or isinstance(catpart_doc, _mock.Mock):
        return
    try:
        part = getattr(catpart_doc, "Part", None)
        if part is None:
            return
        try:
            part.UpdateObject(axis_obj)
        except Exception:
            try:
                part.Update()
            except Exception as e:
                logger.debug("Part.Update: %s", e)
    except Exception as e:
        logger.debug("update_part_for_axis_geometry: %s", e)


def _axis_xy_pair_from_catscript(caa: Any, axis_obj: Any) -> Optional[Tuple[List[float], List[float]]]:
    """CATScript runs in-process; VBA GetVectors often works when Python out-params do not."""
    if caa is None or isinstance(caa, _mock.Mock) or isinstance(axis_obj, _mock.Mock):
        return None
    script_gv = """
    Function CATMain(ax)
        Dim vx(2)
        Dim vy(2)
        On Error Resume Next
        ax.GetVectors vx, vy
        If Err.Number <> 0 Then
            CATMain = "ERR"
            Exit Function
        End If
        CATMain = vx(0) & "," & vx(1) & "," & vx(2) & "|" & vy(0) & "," & vy(1) & "," & vy(2)
    End Function
    """
    script_xy = """
    Function CATMain(ax)
        Dim vx(2)
        Dim vy(2)
        On Error Resume Next
        ax.XAxis.GetDirection vx
        If Err.Number <> 0 Then
            CATMain = "ERR"
            Exit Function
        End If
        ax.YAxis.GetDirection vy
        If Err.Number <> 0 Then
            CATMain = "ERR"
            Exit Function
        End If
        CATMain = vx(0) & "," & vx(1) & "," & vx(2) & "|" & vy(0) & "," & vy(1) & "," & vy(2)
    End Function
    """
    for label, script in (("GetVectors", script_gv), ("XAxis/YAxis", script_xy)):
        try:
            res = caa.SystemService.Evaluate(script, 1, "CATMain", [axis_obj])
            if res is None or str(res).strip() == "ERR":
                continue
            parts = str(res).strip().split("|")
            if len(parts) != 2:
                continue
            vx = [float(x) for x in parts[0].split(",")]
            vy = [float(x) for x in parts[1].split(",")]
            if len(vx) == 3 and len(vy) == 3 and _vec_sum_abs(vx) > 1e-30 and _vec_sum_abs(vy) > 1e-30:
                logger.info("drafting_orientation: axis vectors via CATScript (%s)", label)
                return vx, vy
        except Exception as e:
            logger.warning("CATScript axis read (%s): %s", label, e, exc_info=True)
    return None


def read_global_axis_plane_six(
    caa: Any,
    catpart_doc: Any,
    axis_obj: Any,
    primary_define_front: str = "xz",
) -> Optional[Tuple[float, float, float, float, float, float]]:
    """
    DefineFrontView six cosines for a global axis: update part, try Python COM, then CATScript.
    primary_define_front: "xz" (default) = front elevation as main so TOP/RIGHT are plan+side; "xy" = old plan-as-main.
    """
    _update_part_for_axis_geometry(catpart_doc, axis_obj)
    plane = front_plane_six_tuple_from_axis(axis_obj, primary_define_front)
    if plane is not None:
        return plane
    pair = _axis_xy_pair_from_catscript(caa, axis_obj)
    if pair is None:
        try:
            nm = getattr(axis_obj, "Name", "?")
            tn = type(axis_obj).__name__
        except Exception:
            nm, tn = "?", "?"
        logger.warning(
            "read_global_axis_plane_six: failed for axis %r (type=%s); try selection or per-part axis copy",
            nm,
            tn,
        )
        return None
    basis = _orthonormal_basis_from_raw_xy_pair(pair[0], pair[1])
    if basis is None:
        return None
    ex, ey, ez = basis
    return _basis_six_for_primary(ex, ey, ez, primary_define_front)


def orthonormal_basis_from_axis_with_fallbacks(
    caa: Any,
    catpart_doc: Any,
    axis_obj: Any,
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """(ex, ey, ez) for propagation / tooling; same resolution order as read_global_axis_plane_six (Python then CATScript)."""
    _update_part_for_axis_geometry(catpart_doc, axis_obj)
    basis = orthonormal_basis_from_axis_system(axis_obj)
    if basis is not None:
        return basis
    pair = _axis_xy_pair_from_catscript(caa, axis_obj)
    if pair is None:
        return None
    return _orthonormal_basis_from_raw_xy_pair(pair[0], pair[1])


def front_plane_six_tuple_from_axis(
    axis_obj,
    primary_define_front: str = "xz",
) -> Optional[Tuple[float, float, float, float, float, float]]:
    """
    DefineFrontView plane from axis basis: default "xz" uses XZ (normal ±ey) so child TOP≈plan and RIGHT≈side.
    "xy" uses XY (normal ±ez): main was same orientation as CATIA TOP child (duplicate plan views).
    """
    basis = orthonormal_basis_from_axis_system(axis_obj)
    if not basis:
        return None
    ex, ey, ez = basis
    return _basis_six_for_primary(ex, ey, ez, primary_define_front)


def front_plane_and_axis_from_part(
    part,
    prefer_axis_name: Optional[str] = None,
    primary_define_front: str = "xz",
) -> Tuple[Optional[Tuple[float, float, float, float, float, float]], Any]:
    """DefineFrontView six cosines + axis for SetAxisSysteme(CATPart, axis)."""
    if part is None:
        return None, None
    ax = pick_axis_system(part, prefer_name=prefer_axis_name)
    if ax is None:
        return None, None
    tup = front_plane_six_tuple_from_axis(ax, primary_define_front)
    if tup is not None:
        logger.info(
            "Drafting orientation: front plane from axis %r (use with SetAxisSysteme on CATPart)",
            getattr(ax, "Name", "?"),
        )
    return tup, ax


def front_plane_from_part(
    part,
    prefer_axis_name: Optional[str] = None,
    primary_define_front: str = "xz",
) -> Optional[Tuple[float, float, float, float, float, float]]:
    tup, _ = front_plane_and_axis_from_part(
        part, prefer_axis_name=prefer_axis_name, primary_define_front=primary_define_front
    )
    return tup


def front_plane_and_axis_for_row(
    part_scope: Any,
    prefer_axis_name: Optional[str],
    global_axis: Any = None,
    global_catpart_doc: Any = None,
    global_plane_six: Optional[Tuple[float, float, float, float, float, float]] = None,
    primary_define_front: str = "xz",
) -> Tuple[Optional[Tuple[float, float, float, float, float, float]], Any, Any]:
    """
    One BOM row: use global assembly axis (DefineFrontView cosines; SetAxisSysteme only if same CATPart as row).
    If global_axis is None, use Part.AxisSystems + prefer_axis_name on part_scope.
    If global_axis is set but this row’s CATPart is not the axis owner, use that part’s AxisSystems instead of global
    plane cosines alone — otherwise DefineFrontView uses assembly directions without SetAxisSysteme (bad for rings, etc.).
    global_plane_six: optional cosines read before e.g. creating a Drawing (COM refs to the axis can go stale after).
    primary_define_front: pass same value as read_global_axis_plane_six (default xz).
    Returns (plane_six, axis_ref_or_none, catpart_doc_for_setaxis_or_none).
    """
    from app.services.drafting_axis_resolve import catpart_documents_same

    if global_axis is not None:
        plane = (
            global_plane_six
            if global_plane_six is not None
            else front_plane_six_tuple_from_axis(global_axis, primary_define_front)
        )
        if plane is None:
            return None, None, None
        part_doc = catpart_document_for_part(part_scope)
        if part_doc is not None and global_catpart_doc is not None and catpart_documents_same(
            part_doc, global_catpart_doc
        ):
            return plane, global_axis, global_catpart_doc
        local_plane, local_ax = front_plane_and_axis_from_part(
            part_scope,
            prefer_axis_name=prefer_axis_name or None,
            primary_define_front=primary_define_front,
        )
        if local_plane is not None:
            return local_plane, local_ax, part_doc
        return plane, None, None

    plane, ax = front_plane_and_axis_from_part(
        part_scope,
        prefer_axis_name=prefer_axis_name or None,
        primary_define_front=primary_define_front,
    )
    if plane is None:
        return None, None, None
    return plane, ax, catpart_document_for_part(part_scope)


def catpart_document_for_part(part) -> Any:
    """CATPart Document that owns this Part (SetAxisSysteme first argument must be this, not Product)."""
    if part is None:
        return None
    try:
        par = getattr(part, "Parent", None)
        if par is not None and (getattr(par, "Name", "") or "").lower().endswith(".catpart"):
            return par
    except Exception:
        pass
    try:
        doc = getattr(part, "Document", None)
        if doc is not None and (getattr(doc, "Name", "") or "").lower().endswith(".catpart"):
            return doc
    except Exception:
        pass
    return None


def part_from_generative_product(product) -> Any:
    """Root Product under CATPart -> Part."""
    try:
        if product is None:
            return None
        parent = getattr(product, "Parent", None)
        if parent is not None and getattr(parent, "Part", None) is not None:
            return parent.Part
    except Exception:
        pass
    return None
