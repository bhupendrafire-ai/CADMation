"""Live CATIA check: scan bodies, apply disambiguation rename. Default leaves names changed; use --restore to undo."""
from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.body_name_disambiguation_service import (  # noqa: E402
    _body_identity,
    _collect_body_records,
    apply_temporary_disambiguation,
    clear_disambiguation_server_state,
    restore_temporary_body_names,
)
from app.services.catia_bridge import catia_bridge  # noqa: E402


def _duplicate_summary(records: list) -> dict:
    by_name: dict = {}
    for r in records:
        by_name.setdefault(r["original_name"], []).append(r)
    out = {}
    for name, group in by_name.items():
        seen = set()
        distinct = []
        for r in group:
            bid = _body_identity(r["body"])
            if bid in seen:
                continue
            seen.add(bid)
            distinct.append(r)
        if len(distinct) >= 2:
            out[name] = len(distinct)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--restore",
        action="store_true",
        help="After listing renames, revert body names in this CATIA session (does not save).",
    )
    args = p.parse_args()

    clear_disambiguation_server_state()
    caa = catia_bridge.get_application()
    if not caa:
        print("FAIL: CATIA not connected (get_application returned None).")
        return 1

    try:
        doc = caa.ActiveDocument
        doc_hint = getattr(doc, "Name", None) or getattr(doc, "FullName", "?")
    except Exception:
        doc_hint = "?"

    records = _collect_body_records(caa)
    dups = _duplicate_summary(records)
    print(f"Active document: {doc_hint}")
    print(f"Body records collected: {len(records)}")
    if dups:
        print(f"Duplicate names (distinct COM bodies per name): {dups}")
    else:
        print("No cross-assembly duplicate body display names — expect 0 renames.")

    restore_list, resolution_map = apply_temporary_disambiguation(caa)
    print(f"Applied: {len(restore_list)} rename(s), {len(resolution_map)} resolution map entr(y/ies).")
    for body, old in restore_list[:30]:
        try:
            new = body.Name
            print(f"  {old!r} -> {new!r}")
        except Exception as e:
            print(f"  {old!r} -> (could not read new name: {e})")

    if args.restore:
        restore_temporary_body_names(restore_list)
        print("Restored original names in session (not saved).")
    else:
        print("Left new names in CATIA (Save document to persist; re-run with --restore to undo in session).")

    if dups and not restore_list:
        print("WARN: Duplicates detected in scan but apply renamed 0 — investigate collection/grouping.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
