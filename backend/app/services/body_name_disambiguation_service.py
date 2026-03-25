"""
PartDesign body renames when duplicate names span the assembly (BOM measure flow).
Renames persist in the CATIA session; File > Save keeps them on disk. CADMation does not auto-revert.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Map key: (norm_catpart_fp, instance_name_stripped, original_name_upper) -> temp_name
ResolutionMap = Dict[Tuple[str, str, str], str]
RestoreEntry = Tuple[Any, str]  # (body_com, original_name)

_session_resolution_map: ResolutionMap = {}
_classifier_disambiguation_ran: bool = False


def clear_disambiguation_server_state() -> None:
    """Clear in-memory resolution map only (does not rename bodies in CATIA)."""
    global _classifier_disambiguation_ran
    _session_resolution_map.clear()
    _classifier_disambiguation_ran = False


def ensure_disambiguation_for_classifier(caa, want_rename: bool) -> None:
    global _classifier_disambiguation_ran
    if not caa:
        return
    if not want_rename:
        clear_disambiguation_server_state()
        return
    if _classifier_disambiguation_ran:
        return
    _, m = apply_temporary_disambiguation(caa)
    _session_resolution_map.clear()
    _session_resolution_map.update(m)
    _classifier_disambiguation_ran = True


def disambiguation_state_for_measurement(caa, want_rename: bool) -> Tuple[ResolutionMap, int]:
    """(resolution_map, rename_count_this_call). Map may come from classifier or a fresh apply."""
    if not caa or not want_rename:
        return {}, 0
    if _session_resolution_map:
        return dict(_session_resolution_map), 0
    restore_list, m = apply_temporary_disambiguation(caa)
    _session_resolution_map.clear()
    _session_resolution_map.update(m)
    return dict(_session_resolution_map), len(restore_list)


def _norm_fp(path: str) -> str:
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(path.strip())))
    except Exception:
        return (path or "").strip().lower()


def _collect_body_records(caa) -> List[dict]:
    """One record per PartDesign body under the active document tree."""
    out: List[dict] = []
    if not caa:
        return out
    try:
        doc = caa.ActiveDocument
    except Exception:
        return out
    if doc is None:
        return out

    def add_part_bodies(link_doc, prod_for_instance: Any) -> None:
        try:
            part = getattr(link_doc, "Part", None)
            bodies = getattr(part, "Bodies", None) if part is not None else None
            if bodies is None or bodies.Count < 1:
                return
            fp = _norm_fp(getattr(link_doc, "FullName", "") or "")
            inst = (getattr(prod_for_instance, "Name", "") or "").strip()
            pnum = (getattr(prod_for_instance, "PartNumber", "") or "").strip()
            for i in range(1, bodies.Count + 1):
                try:
                    b = bodies.Item(i)
                    nm = (getattr(b, "Name", "") or "").strip()
                    if not nm:
                        continue
                    out.append(
                        {
                            "body": b,
                            "fp": fp,
                            "instance_name": inst,
                            "part_number": pnum,
                            "original_name": nm,
                        }
                    )
                except Exception:
                    continue
        except Exception:
            pass

    root = None
    try:
        root = getattr(doc, "Product", None)
    except Exception:
        root = None

    if root is not None:

        def walk(prod, depth: int) -> None:
            if depth > 80:
                return
            try:
                ref = getattr(prod, "ReferenceProduct", None)
                if ref is not None:
                    link_doc = getattr(ref, "Parent", None)
                    if link_doc is not None:
                        add_part_bodies(link_doc, prod)
            except Exception:
                pass
            try:
                ch = prod.Products
                for j in range(1, ch.Count + 1):
                    walk(ch.Item(j), depth + 1)
            except Exception:
                pass

        walk(root, 0)
    else:
        try:
            part = doc.Part
            bodies = getattr(part, "Bodies", None)
            if bodies and bodies.Count > 0:
                fp = _norm_fp(getattr(doc, "FullName", "") or "")
                for i in range(1, bodies.Count + 1):
                    try:
                        b = bodies.Item(i)
                        nm = (getattr(b, "Name", "") or "").strip()
                        if nm:
                            out.append(
                                {
                                    "body": b,
                                    "fp": fp,
                                    "instance_name": "",
                                    "part_number": "",
                                    "original_name": nm,
                                }
                            )
                    except Exception:
                        continue
        except Exception:
            pass

    return out


def _body_identity(body: Any) -> int:
    try:
        o = getattr(body, "_oleobj_", None)
        if o is not None:
            return id(o)
    except Exception:
        pass
    return id(body)


def apply_temporary_disambiguation(caa) -> Tuple[List[RestoreEntry], ResolutionMap]:
    """
    Rename bodies that share the same display name across different instances/parts.
    Returns (entries for optional manual undo via restore_temporary_body_names, resolution_map).
    """
    restore_list: List[RestoreEntry] = []
    resolution_map: ResolutionMap = {}

    records = _collect_body_records(caa)
    if len(records) < 2:
        return restore_list, resolution_map

    by_name: Dict[str, List[dict]] = {}
    for r in records:
        by_name.setdefault(r["original_name"], []).append(r)

    for base_name, group in by_name.items():
        if len(group) < 2:
            continue
        seen_id = set()
        distinct = []
        for r in group:
            bid = _body_identity(r["body"])
            if bid in seen_id:
                continue
            seen_id.add(bid)
            distinct.append(r)
        if len(distinct) < 2:
            continue

        distinct.sort(
            key=lambda x: (x["fp"], x["instance_name"], x["part_number"], _body_identity(x["body"]))
        )
        for idx, r in enumerate(distinct):
            temp_name = f"{base_name}__CADM{idx}"
            body = r["body"]
            old = r["original_name"]
            try:
                body.Name = temp_name
                restore_list.append((body, old))
                key = (r["fp"], r["instance_name"], old.upper())
                resolution_map[key] = temp_name
                logger.info(
                    "Body disambiguation: %r -> %r (instance=%r fp=%s)",
                    old,
                    temp_name,
                    r["instance_name"],
                    r["fp"][:48] if r["fp"] else "",
                )
            except Exception as e:
                logger.warning("Body disambiguation failed for %r: %s", old, e)

    return restore_list, resolution_map


def restore_temporary_body_names(restore_list: List[RestoreEntry]) -> None:
    """Undo apply_temporary_disambiguation (same session); dev/tools only — BOM flow does not call this."""
    if not restore_list:
        return
    failures = 0
    for body, old_name in reversed(restore_list):
        try:
            body.Name = old_name
        except Exception as e:
            failures += 1
            logger.warning("Body name restore failed (%r): %s", old_name, e)
    if failures:
        logger.error(
            "Body disambiguation: %s restore(s) failed — do not save CATIA documents until fixed.",
            failures,
        )


def effective_body_name_for_bom_row(
    resolution_map: ResolutionMap,
    part_scope: Any,
    instance_name: str,
    user_body_name: str,
) -> str:
    """Map UI body name to COM Body.Name after disambiguation rename (original -> __CADM{n})."""
    if not resolution_map or not user_body_name:
        return user_body_name
    try:
        doc = getattr(part_scope, "Parent", None)
        fp = _norm_fp(getattr(doc, "FullName", "") or "")
    except Exception:
        fp = ""
    if not fp:
        return user_body_name
    key = (fp, (instance_name or "").strip(), user_body_name.strip().upper())
    return resolution_map.get(key, user_body_name)
