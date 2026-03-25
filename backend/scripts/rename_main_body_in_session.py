"""Rename every PartDesign body named MAIN_BODY in the active CATIA tree to MAIN_BODY__CADM{n}. Run: python scripts/rename_main_body_in_session.py"""
from __future__ import annotations

import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.body_name_disambiguation_service import (  # noqa: E402
    _body_identity,
    _collect_body_records,
)
from app.services.catia_bridge import catia_bridge  # noqa: E402

TARGET = "MAIN_BODY"


def main() -> int:
    caa = catia_bridge.get_application()
    if not caa:
        print("FAIL: CATIA not connected.")
        return 1
    try:
        doc = caa.ActiveDocument
        doc_hint = getattr(doc, "Name", None) or getattr(doc, "FullName", "?")
    except Exception:
        doc_hint = "?"
    records = _collect_body_records(caa)
    candidates = [r for r in records if (r.get("original_name") or "").strip().upper() == TARGET]
    seen = set()
    distinct = []
    for r in candidates:
        bid = _body_identity(r["body"])
        if bid in seen:
            continue
        seen.add(bid)
        distinct.append(r)
    distinct.sort(
        key=lambda x: (x["fp"], x["instance_name"], x["part_number"], _body_identity(x["body"]))
    )
    print(f"Document: {doc_hint}")
    print(f"Distinct bodies named {TARGET!r}: {len(distinct)}")
    if len(distinct) < 2:
        print("Nothing to disambiguate (need at least two MAIN_BODY bodies in the tree).")
        return 0
    for idx, r in enumerate(distinct):
        new_name = f"{TARGET}__CADM{idx}"
        body = r["body"]
        old = (getattr(body, "Name", None) or "").strip()
        try:
            body.Name = new_name
            print(f"  {old!r} @ instance={r['instance_name']!r} -> {new_name!r}")
        except Exception as e:
            print(f"  FAIL {old!r} instance={r['instance_name']!r}: {e}")
            return 2
    print("OK: Save in CATIA if you want these names on disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
