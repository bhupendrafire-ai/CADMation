"""Unit tests for drafting axis propagation (candidate / skip rules; no CATIA)."""
import os
import sys
from unittest.mock import MagicMock, patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.drafting_axis_propagate import (
    AXIS_DRAFTING_GLOBAL,
    axis_named_exists,
    part_key_from_item,
    skip_reason_for_propagate_target,
)


def test_part_key_prefers_source_row_id():
    assert part_key_from_item({"sourceRowId": "PN|Inst"}, 0) == "PN|Inst"


def test_part_key_fallback():
    k = part_key_from_item({"partNumber": "P1", "instanceName": "I.1"}, 2)
    assert "P1" in k and "I.1" in k


def test_skip_unresolved_document():
    assert skip_reason_for_propagate_target(None, MagicMock(), MagicMock()) == "unresolved_document"


def test_skip_same_document_as_global():
    d = MagicMock()
    assert skip_reason_for_propagate_target(d, d, MagicMock()) == "same_document_as_global_axis"


def test_axis_named_exists_match():
    ax = MagicMock()
    ax.Name = AXIS_DRAFTING_GLOBAL
    coll = MagicMock()
    coll.Count = 1
    coll.Item = lambda i: ax
    part = MagicMock()
    part.AxisSystems = coll
    assert axis_named_exists(part, AXIS_DRAFTING_GLOBAL) is True


def test_axis_named_exists_no_collection():
    part = MagicMock()
    part.AxisSystems = None
    assert axis_named_exists(part, AXIS_DRAFTING_GLOBAL) is False


@patch("app.services.drafting_axis_propagate.catpart_documents_same", return_value=False)
@patch("app.services.drafting_axis_propagate.axis_named_exists", return_value=True)
def test_skip_propagated_name_exists(_mock_named, _mock_same):
    pd = MagicMock()
    gd = MagicMock()
    assert skip_reason_for_propagate_target(pd, gd, MagicMock()) == "axis_already_propagated"


@patch("app.services.drafting_axis_propagate.catpart_documents_same", return_value=False)
@patch("app.services.drafting_axis_propagate.axis_named_exists", return_value=False)
@patch("app.services.drafting_axis_propagate.front_plane_and_axis_from_part")
def test_skip_already_has_usable_axis(mock_fp, _mock_named, _mock_same):
    mock_fp.return_value = ((1.0, 0.0, 0.0, 0.0, 1.0, 0.0), None)
    pd = MagicMock()
    gd = MagicMock()
    assert skip_reason_for_propagate_target(pd, gd, MagicMock()) == "already_has_usable_axis"


@patch("app.services.drafting_axis_propagate.catpart_documents_same", return_value=False)
@patch("app.services.drafting_axis_propagate.axis_named_exists", return_value=False)
@patch("app.services.drafting_axis_propagate.front_plane_and_axis_from_part")
def test_no_skip_when_needs_axis(mock_fp, _mock_named, _mock_same):
    mock_fp.return_value = (None, None)
    pd = MagicMock()
    gd = MagicMock()
    assert skip_reason_for_propagate_target(pd, gd, MagicMock()) is None
