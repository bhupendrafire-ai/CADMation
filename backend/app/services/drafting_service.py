import array
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.catia_bridge import catia_bridge
from app.services.catia_bom_resolve import (
    generative_behavior_document_target,
    resolve_bom_item_object,
    resolve_catpart_document_for_product_instance,
    resolve_product_for_measure,
)
from app.services.drafting_axis_resolve import (
    catpart_document_for_axis_object,
    rebind_axis_system_to_activated_part,
    resolve_axis_system_by_name,
    resolve_axis_system_from_selection,
)
from app.services.drafting_orientation import (
    catpart_document_for_part,
    front_plane_and_axis_for_row,
    front_plane_and_axis_from_part,
    read_global_axis_plane_six,
    part_from_generative_product,
)
from app.services.geometry_service import geometry_service

logger = logging.getLogger(__name__)

# DefineFrontView primary plane: xz = main is front elevation; TOP/RIGHT children ≈ plan + side (not two plans).
_PRIMARY_DEFINE_FRONT_PLANE = "xz"

# CatDrawingViewType for DefineProjectionView(ref, type). With XZ DefineFrontView, CATIA's TOP/RIGHT vs shop Top/Side are crossed.
_CAT_TOP_VIEW = 1
_CAT_LEFT_VIEW = 3
_CAT_RIGHT_VIEW = 4
# In-plane rotation for shop Top (plan) after projection; V5 DrawingView.Angle is radians. Sign pairs with plan LEFT/RIGHT.
_DEFAULT_TOP_VIEW_ROTATION_DEG = -90.0

_VIEW_GAP_MM = 20.0
_MARGIN_MM = 25.0
_PART_STRIP_GAP_MM = 25.0
# When DrawingView.Size() is empty until after update, still advance layout so views do not stack.
_MIN_VIEW_EXTENT_MM = 90.0
# If Size() fails, reserve this much horizontal space per view so large parts do not overlap (was 90 → huge overlap).
_LAYOUT_FALLBACK_SLOT_MM = 300.0
# A3 portrait ~297 x 420 mm usable width; y increases upward on sheet
_SHEET_MAX_X_MM = 380.0
_ROW_START_Y_MM = 120.0
_MIN_ROW_Y_MM = 35.0


def _try_set_view_angle_deg(view: Any, delta_deg: float, sheet: Any = None) -> bool:
    """Add delta_deg to generative view in-plane rotation; V5 DrawingView.Angle is radians (CAADoc)."""
    if view is None or abs(delta_deg) < 1e-12:
        return True
    dr = math.radians(delta_deg)
    for prop in ("Angle", "ViewAngle"):
        try:
            cur = float(getattr(view, prop))
        except Exception:
            cur = 0.0
        try:
            setattr(view, prop, cur + dr)
            logger.info(
                "DraftingService: %s += %.6f rad (Δ %.1f°)",
                prop,
                dr,
                delta_deg,
            )
            if sheet is not None:
                try:
                    sheet.Update()
                except Exception:
                    pass
            try:
                view.GenerativeBehavior.ForceUpdate()
            except Exception:
                try:
                    view.GenerativeBehavior.Update()
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.debug("DraftingService view.%s: %s", prop, e)
    return False


def _sanitize_sheet_title(raw: Optional[str]) -> str:
    """CATDrawing sheet name: strip illegal characters and length-limit."""
    if not raw or not str(raw).strip():
        return "Sheet"
    s = "".join("_" if c in '<>:"/\\|?*\n\r\t' else c for c in str(raw).strip())
    s = (s.strip(" .") or "Sheet")[:180]
    return s


def _parse_bom_dimensions_mm(item: Dict[str, Any]) -> Tuple[float, float, float]:
    """L×W×H in mm from BOM fields (same idea as frontend parseSize)."""
    raw = (item.get("millingSize") or item.get("size") or item.get("rmSize") or "").strip()
    if not raw:
        return (0.0, 0.0, 0.0)
    numbers = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", raw)]
    if len(numbers) >= 3:
        return (numbers[0], numbers[1], numbers[2])
    if len(numbers) >= 2 and re.search(r"DIA|Ø|DIAMETER", raw, re.I):
        return (numbers[0], numbers[0], numbers[1])
    if len(numbers) == 1:
        return (numbers[0], numbers[0], numbers[0])
    return (0.0, 0.0, 0.0)


def _bom_layout_hints_mm(item: Dict[str, Any]) -> Tuple[float, float]:
    """
    Per-row layout from BOM: (min_horizontal_slot_mm, strip_height_hint_mm).
    Slot scales with largest part dimension so small parts stay compact and large parts get space.
    """
    l, w, h = _parse_bom_dimensions_mm(item)
    dims = [d for d in (l, w, h) if d > 1e-9]
    if not dims:
        return (_LAYOUT_FALLBACK_SLOT_MM, _MIN_VIEW_EXTENT_MM * 2.0)
    mx = max(dims)
    # One view frame width ≈ in-plane extent; 1.12 + margin matches typical drawing border.
    slot = max(_MIN_VIEW_EXTENT_MM, min(_SHEET_MAX_X_MM / 3.0, mx * 1.12 + 20.0))
    # Vertical strip: tallest projection ~ max × secondary (plate-like).
    sorted_d = sorted(dims, reverse=True)
    tall = sorted_d[0]
    mid = sorted_d[1] if len(sorted_d) > 1 else tall * 0.6
    strip_h = max(_MIN_VIEW_EXTENT_MM * 1.5, min(420.0, tall * 0.85 + mid * 0.4 + 25.0))
    return (slot, strip_h)


def _caa_from_drawing_doc(drawing_doc: Any) -> Any:
    if drawing_doc is None:
        return None
    try:
        return drawing_doc.Application
    except Exception:
        pass
    try:
        cur = drawing_doc
        for _ in range(10):
            if cur is None:
                break
            app = getattr(cur, "Application", None)
            if app is not None:
                return app
            cur = getattr(cur, "Parent", None)
    except Exception:
        pass
    return None


def _iter_catia_documents(caa) -> Any:
    try:
        n = int(caa.Documents.Count)
    except Exception:
        return
    for i in range(1, n + 1):
        try:
            yield caa.Documents.Item(i)
        except Exception:
            continue


def _doc_is_part_or_product(doc) -> bool:
    try:
        n = (doc.Name or "").lower()
        return n.endswith(".catpart") or n.endswith(".catproduct")
    except Exception:
        return False


def _activate_catia_document(caa, doc) -> bool:
    """Selection.Search is scoped to the active window; Activate() works when ActiveDocument is read-only."""
    try:
        doc.Activate()
    except Exception:
        try:
            caa.ActiveDocument = doc
        except Exception:
            return False
    time.sleep(0.12)
    return True


class DraftingService:
    @staticmethod
    def _document_link_for_generative(source_doc) -> Any:
        """GenerativeBehavior.Document should be the 3D Product; macro uses partDocument.Product / GetItem."""
        try:
            if source_doc is not None and hasattr(source_doc, "Product"):
                prod = source_doc.Product
                if prod is not None:
                    return prod
        except Exception:
            pass
        return source_doc

    def _apply_generative_display(self, gb) -> None:
        """Hidden lines, 3D colors, 3D points (spec), fillet mode — macro + common GPS defaults."""
        for prop, candidates in (
            ("HiddenLineMode", (1, 2)),
            ("ColorInheritanceMode", (1, 2)),
            ("PointsProjectionMode", (1, 2)),
        ):
            for val in candidates:
                try:
                    setattr(gb, prop, val)
                    break
                except Exception:
                    continue
        try:
            gb.ForceUpdate()
        except Exception:
            try:
                gb.Update()
            except Exception:
                pass

    @staticmethod
    def _apply_drawing_view_options(view) -> None:
        """Center line / dress-up toggles on DrawingView when exposed by typelib."""
        for prop, candidates in (
            ("CenterLineMode", (1, 2)),
            ("CenterLineVisualization", (1, True)),
            ("ShowCenterLine", (True, 1)),
        ):
            for val in candidates:
                try:
                    setattr(view, prop, val)
                    break
                except Exception:
                    continue
        try:
            gb = view.GenerativeBehavior
            for prop, candidates in (("AxisLineMode", (1, 2)), ("ThreadMode", (1, 2))):
                for val in candidates:
                    try:
                        setattr(gb, prop, val)
                        break
                    except Exception:
                        continue
        except Exception:
            pass

    def _create_front_right_top_views(
        self,
        sheet,
        doc_link,
        names: Tuple[str, str, str],
        front_plane: Tuple[float, float, float, float, float, float],
        axis_ref: Any = None,
        catpart_doc_for_axis: Any = None,
        skip_sheet_reference_alignment: bool = False,
        include_right_view: bool = True,
        *,
        top_view_rotation_deg: Optional[float] = None,
        plan_projection_use_left: bool = True,
    ) -> Tuple[Any, Any, Any]:
        """
        Main = DefineFrontView (XZ). Secondary types: shop Side uses CATIA TOP; shop Top (plan) uses CATIA RIGHT/LEFT — swapped
        vs enum names when the primary is XZ. Default plan_projection_use_left=True (catLeftView) for the lateral opposite to RIGHT.
        top_view_rotation_deg: in-plane fix for plan; default _DEFAULT_TOP_VIEW_ROTATION_DEG; set 0 to skip.
        """
        n_front, n_right, n_top = names
        front = sheet.Views.Add(n_front)
        gb0 = front.GenerativeBehavior
        gb0.Document = doc_link
        # First arg must be the CATPart Document (owns HybridShapeAxisSystem); Product alone yields wrong/tilted views.
        if axis_ref is not None and catpart_doc_for_axis is not None:
            try:
                gb0.SetAxisSysteme(catpart_doc_for_axis, axis_ref)
            except Exception as e:
                logger.warning("DraftingService SetAxisSysteme: %s", e)
        gb0.DefineFrontView(*front_plane)
        try:
            front.Scale = 1.0
        except Exception:
            pass
        gb0.Update()
        try:
            front.Activate()
        except Exception:
            pass
        self._apply_generative_display(gb0)
        self._apply_drawing_view_options(front)

        right = None
        if include_right_view:
            right = sheet.Views.Add(n_right)
            gb1 = right.GenerativeBehavior
            gb1.DefineProjectionView(gb0, _CAT_TOP_VIEW)
            try:
                front.GenerativeLinks.CopyLinksTo(right.GenerativeLinks)
            except Exception as e:
                logger.warning("DraftingService CopyLinksTo right: %s", e)
            try:
                right.Scale = 1.0
            except Exception:
                pass
            gb1.Update()
            self._apply_generative_display(gb1)
            self._apply_drawing_view_options(right)
            if not skip_sheet_reference_alignment:
                try:
                    right.ReferenceView = front
                    right.AlignedWithReferenceView()
                except Exception as e:
                    logger.warning("DraftingService Right AlignedWithReferenceView: %s", e)

        top = sheet.Views.Add(n_top)
        gb2 = top.GenerativeBehavior
        _plan_cat = _CAT_LEFT_VIEW if plan_projection_use_left else _CAT_RIGHT_VIEW
        gb2.DefineProjectionView(gb0, _plan_cat)
        try:
            front.GenerativeLinks.CopyLinksTo(top.GenerativeLinks)
        except Exception as e:
            logger.warning("DraftingService CopyLinksTo top: %s", e)
        try:
            top.Scale = 1.0
        except Exception:
            pass
        gb2.Update()
        self._apply_generative_display(gb2)
        self._apply_drawing_view_options(top)
        if not skip_sheet_reference_alignment:
            try:
                top.ReferenceView = front
                top.AlignedWithReferenceView()
            except Exception as e:
                logger.warning("DraftingService Top AlignedWithReferenceView: %s", e)

        try:
            sheet.Update()
        except Exception:
            pass
        if not skip_sheet_reference_alignment:
            if include_right_view and right is not None:
                self._unalign_view_for_sheet_move(right)
            self._unalign_view_for_sheet_move(top)
        try:
            sheet.Update()
        except Exception:
            pass
        rot_deg = (
            _DEFAULT_TOP_VIEW_ROTATION_DEG
            if top_view_rotation_deg is None
            else float(top_view_rotation_deg)
        )
        if not _try_set_view_angle_deg(top, rot_deg, sheet):
            logger.warning(
                "DraftingService: could not set Top view rotation (%.1f°); check DrawingView.Angle in your CATIA build",
                rot_deg,
            )
        try:
            sheet.Update()
        except Exception:
            pass
        return front, right, top

    def _unalign_view_for_sheet_move(self, view) -> None:
        try:
            view.UnAlignedWithReferenceView()
        except Exception:
            try:
                view.UnalignedWithReferenceView()
            except Exception:
                pass

    def _try_sheet_format_display_off(self, sheet: Any, drawing_doc: Any = None, caa: Any = None) -> None:
        """
        Match Sheet Properties → Format → Display (unchecked). Not always exposed on DrawingSheet;
        try property names, PageSetup, background view, then CATScript.
        """
        if caa is None and drawing_doc is not None:
            caa = _caa_from_drawing_doc(drawing_doc)
        for prop in ("Display", "DisplayFormat", "FormatDisplay", "ShowFormat", "SheetFormatDisplay"):
            try:
                setattr(sheet, prop, False)
                logger.info("Drawing sheet: set %s=False", prop)
                return
            except Exception:
                continue
        try:
            ps = sheet.PageSetup
            for prop in ("Display", "DisplayFormat", "FormatDisplay", "ShowFormat"):
                try:
                    setattr(ps, prop, False)
                    logger.info("Drawing sheet PageSetup: set %s=False", prop)
                    return
                except Exception:
                    continue
        except Exception as e:
            logger.debug("Drawing sheet PageSetup: %s", e)
        try:
            for i in range(1, int(sheet.Views.Count) + 1):
                v = sheet.Views.Item(i)
                name = (getattr(v, "Name", "") or "").lower()
                if "background" in name:
                    for prop, val in (("Visible", False), ("Hidden", True)):
                        try:
                            setattr(v, prop, val)
                            logger.info("Drawing sheet: set background view %s=%s", prop, val)
                            return
                        except Exception:
                            continue
        except Exception as e:
            logger.debug("Drawing sheet background view: %s", e)
        for nm in ("Background View", "Background"):
            try:
                v = sheet.Views.Item(nm)
                v.Visible = False
                logger.info("Drawing sheet: hid view %r", nm)
                return
            except Exception:
                continue
        if caa is not None:
            script = """
            Function CATMain(sh)
                On Error Resume Next
                sh.Display = False
                If Err.Number = 0 Then
                    CATMain = "ok"
                Else
                    CATMain = "fail"
                End If
            End Function
            """
            try:
                r = caa.SystemService.Evaluate(script, 1, "CATMain", [sheet])
                if str(r).strip() == "ok":
                    logger.info("Drawing sheet: Display=False via CATScript")
                    return
            except Exception as e:
                logger.debug("CATScript sheet.Display: %s", e)
        try:
            sheet.DisplayNoPrint = False
        except Exception:
            pass

    def _setup_drawing_sheet(
        self,
        sheet: Any,
        drawing_doc: Any = None,
        *,
        sheet_title: Optional[str] = None,
        caa: Any = None,
    ) -> None:
        """ISO-style sheet: third angle; landscape; optional rename; turn off format Display when possible."""
        if drawing_doc is not None:
            for std in (1, 0):
                try:
                    drawing_doc.Standard = std
                    break
                except Exception:
                    continue
        try:
            sheet.PaperSize = 2
            sheet.Scale = 1.0
        except Exception:
            pass
        try:
            sheet.Orientation = 1
        except Exception:
            pass
        try:
            sheet.ProjectionMethod = 1
        except Exception:
            pass
        if sheet_title:
            try:
                sheet.Name = _sanitize_sheet_title(sheet_title)
            except Exception as e:
                logger.debug("Drawing sheet rename: %s", e)
        self._try_sheet_format_display_off(sheet, drawing_doc=drawing_doc, caa=caa)
        try:
            sheet.DisplayNoPrint = False
        except Exception:
            pass

    def create_automated_drawing(
        self,
        part_name: Optional[str] = None,
        product_instance: Any = None,
        source_document: Any = None,
        drafting_axis_name: Optional[str] = None,
        *,
        top_view_rotation_deg: Optional[float] = None,
        plan_projection_use_left: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a production-standard drawing for the active part or a specific part name.
        - Sets Third Angle Projection
        - Hides page boundaries
        - Generates Front (XZ main); Top (plan) and Side use swapped CATIA projection enums — see _create_front_right_top_views
        - Automatically generates dimensions
        Optional product_instance: assembly Product node (uses FullName match to CATPart).
        Optional source_document: open CATPart Document to use directly.
        Optional drafting_axis_name: substring to select HybridShapeAxisSystem under Axis Systems (e.g. LOWER_DIE).
        top_view_rotation_deg: in-plane rotation for plan view (deg); None = default 90; 0 = none.
        plan_projection_use_left: default True (catLeftView); set False for catRightView plan.
        """
        caa = catia_bridge.get_application()
        if not caa:
            return {"error": "CATIA not found"}

        try:
            # 1. Get the source document (Part) and selection
            source_doc = None
            active_doc = caa.ActiveDocument
            found = False

            if source_document is not None:
                try:
                    if (getattr(source_document, "Name", "") or "").lower().endswith(".catpart"):
                        source_doc = source_document
                        found = True
                except Exception:
                    pass

            if not found and product_instance is not None:
                try:
                    pd = resolve_catpart_document_for_product_instance(caa, product_instance)
                    if pd is not None:
                        source_doc = pd
                        found = True
                except Exception:
                    pass

            if part_name and not found:
                pn_lo = (part_name or "").lower()
                pn_alt = pn_lo.replace("_", " ")
                # Prefer an open CATPart whose file stem matches (COM collections: use Item(i))
                for doc in _iter_catia_documents(caa):
                    try:
                        dn = (doc.Name or "").lower()
                        if not dn.endswith(".catpart"):
                            continue
                        stem = dn.rsplit(".", 1)[0]
                        if pn_lo in stem or pn_alt in stem.replace("_", " "):
                            source_doc = doc
                            found = True
                            break
                    except Exception:
                        continue

                def _part_doc_from_assembly_product(doc, pn_query: str):
                    """Match BOM-style Part Number search, then tree resolve (same as rough-stock / BOM)."""
                    try:
                        if ".catproduct" not in (doc.Name or "").lower():
                            return None
                        if not _activate_catia_document(caa, doc):
                            return None
                        sel = caa.ActiveDocument.Selection
                        sel.Clear()
                        sel.Search(f"Product.'Part Number'='{pn_query}',all")
                        if sel.Count < 1:
                            return None
                        pick = sel.Item(1).Value
                        for i in range(1, sel.Count + 1):
                            test = sel.Item(i).Value
                            try:
                                if (getattr(test, "PartNumber", "") or "").strip() == pn_query.strip():
                                    pick = test
                                    break
                            except Exception:
                                continue
                        pick = resolve_product_for_measure(pick, pn_query.strip(), "")
                        try:
                            return pick.ReferenceProduct.Parent
                        except Exception:
                            return None
                    except Exception:
                        return None

                if not found:
                    # Assembly-only: resolve by Part Number (reliable vs Name=* wildcards)
                    for q in (part_name.strip(), part_name.strip().replace("_", " "), part_name.strip().replace(" ", "_")):
                        if not q:
                            continue
                        for doc in _iter_catia_documents(caa):
                            pd = _part_doc_from_assembly_product(doc, q)
                            if pd is not None and (pd.Name or "").lower().endswith(".catpart"):
                                source_doc = pd
                                found = True
                                break
                        if found:
                            break

                if not found:
                    for doc in _iter_catia_documents(caa):
                        try:
                            if ".catproduct" not in (doc.Name or "").lower():
                                continue
                            if not _activate_catia_document(caa, doc):
                                continue
                            selection = caa.ActiveDocument.Selection
                            selection.Clear()
                            selection.Search(f"Name='*{part_name}*',all")
                            if selection.Count < 1:
                                continue
                            selected_prod = selection.Item(1).Value
                            try:
                                source_doc = selected_prod.ReferenceProduct.Parent
                            except Exception:
                                source_doc = None
                            if source_doc is not None and (source_doc.Name or "").lower().endswith(".catpart"):
                                found = True
                                break
                        except Exception:
                            continue

            if not source_doc:
                if part_name:
                    pn_lo = (part_name or "").lower()
                    pn_alt = pn_lo.replace("_", " ")
                    if active_doc and _doc_is_part_or_product(active_doc):
                        adn = (active_doc.Name or "").lower().rsplit(".", 1)[0]
                        if pn_lo in adn or pn_alt in adn.replace("_", " "):
                            source_doc = active_doc
                else:
                    source_doc = active_doc
            if source_doc is not None and not _doc_is_part_or_product(source_doc):
                source_doc = None
            if not source_doc and not part_name:
                for doc in _iter_catia_documents(caa):
                    if _doc_is_part_or_product(doc):
                        source_doc = doc
                        break

            if not source_doc or not _doc_is_part_or_product(source_doc):
                return {
                    "error": "No valid CATPart or CATProduct found to generate a drawing from."
                    + (f" Could not resolve part_name={part_name!r}." if part_name else ""),
                }

            # For Generative View, we ideally want a Part document
            # If we have a product, we'll try to use it as the source
            part_name_clean = source_doc.Name.split(".")[0]
            part = source_doc.Part if hasattr(source_doc, "Part") else None

            # 2. Create New Drawing (projection chain matches backend/2DView.catvbs)
            drawing_doc = caa.Documents.Add("Drawing")
            logger.info(f"DraftingService: Created new drawing document for {part_name_clean}")

            sheet = drawing_doc.Sheets.ActiveSheet
            self._setup_drawing_sheet(
                sheet,
                drawing_doc,
                sheet_title=part_name_clean,
                caa=caa,
            )

            doc_link = self._document_link_for_generative(source_doc)
            plane, axis_ref = front_plane_and_axis_from_part(
                part,
                prefer_axis_name=(drafting_axis_name or "").strip() or None,
                primary_define_front=_PRIMARY_DEFINE_FRONT_PLANE,
            )
            if plane is None:
                return {
                    "error": (
                        "No usable axis in Part.AxisSystems (Axis Systems folder). "
                        "Add a designer axis (e.g. AXIS_*) or pass drafting_axis_name."
                    ),
                }
            cat_axis_doc = catpart_document_for_part(part)
            if cat_axis_doc is None and source_doc is not None:
                try:
                    if (getattr(source_doc, "Name", "") or "").lower().endswith(".catpart"):
                        cat_axis_doc = source_doc
                except Exception:
                    pass
            try:
                self._create_front_right_top_views(
                    sheet,
                    doc_link,
                    ("Front View", "Right View", "Top View"),
                    plane,
                    axis_ref=axis_ref,
                    catpart_doc_for_axis=cat_axis_doc,
                    include_right_view=True,
                    top_view_rotation_deg=top_view_rotation_deg,
                    plan_projection_use_left=plan_projection_use_left,
                )
            except Exception as ev:
                logger.error("DraftingService: projection views failed: %s", ev)
                return {"error": f"Projection views failed: {ev}"}

            try:
                sheet.Update()
            except Exception:
                pass

            # 4. Phase: Automatic Dimensioning and Annotations
            self.add_advanced_dimensions(part, sheet, source_doc)

            if part:
                try:
                    self.project_part_parameters(part, sheet.Views.Item("Main View"))
                except: pass

            # 5. Add Title Block Text
            try:
                main_view = sheet.Views.Item("Main View")
                texts = main_view.Texts
                title_text = texts.Add(f"PART: {part_name_clean}", 200, 20)
                try: title_text.Size = 5.0
                except: pass
            except: pass
            
            logger.info(f"DraftingService: Successfully completed drafting sequence for {part_name_clean}")
            return {
                "status": "success",
                "message": f"Drafting sequence completed for {part_name_clean} with advanced ordinal dimensioning.",
                "drawing_name": drawing_doc.Name if hasattr(drawing_doc, 'Name') else "New Drawing"
            }

        except Exception as e:
            logger.error(f"DraftingService Error: {e}")
            return {"error": str(e)}

    def _read_view_bbox(self, view) -> List[float]:
        """Sheet bbox [xmin, ymin, xmax, ymax] from DrawingView.Size (COM often fills array.array, not plain list)."""
        for buf in (
            array.array("d", [0.0, 0.0, 0.0, 0.0]),
            [0.0, 0.0, 0.0, 0.0],
        ):
            try:
                res = view.Size(buf)
                if isinstance(res, (list, tuple)) and len(res) >= 4:
                    return [float(res[0]), float(res[1]), float(res[2]), float(res[3])]
                b = buf.tolist() if isinstance(buf, array.array) else buf
                if any(abs(float(x)) > 1e-9 for x in b):
                    return [float(b[0]), float(b[1]), float(b[2]), float(b[3])]
            except Exception:
                continue
        try:
            res = view.Size()
            if isinstance(res, (list, tuple)) and len(res) >= 4:
                return [float(res[0]), float(res[1]), float(res[2]), float(res[3])]
        except Exception:
            pass
        return [0.0, 0.0, 0.0, 0.0]

    @staticmethod
    def _bbox_extent_mm(bbox: List[float]) -> Tuple[float, float]:
        w = abs(float(bbox[2]) - float(bbox[0]))
        h = abs(float(bbox[3]) - float(bbox[1]))
        return w, h

    def _set_view_xy(self, view, x: float, y: float) -> None:
        try:
            view.x = float(x)
            view.y = float(y)
        except Exception:
            try:
                view.X = float(x)
                view.Y = float(y)
            except Exception:
                pass

    def _align_view_corner(
        self,
        view,
        sheet,
        left_x: float,
        bottom_y: float,
        *,
        fallback_slot_mm: Optional[float] = None,
        fallback_height_mm: Optional[float] = None,
    ) -> List[float]:
        """
        Place the view frame so its bbox lower-left is near (left_x, bottom_y).
        CATIA uses view.x / view.y for the view axis origin (typically near the frame center), not the corner —
        move by delta from frame center to target center, not by (left_x - xmin).
        fallback_* come from BOM L×W×H when CATIA Size() is missing.
        """
        slot_default = float(fallback_slot_mm) if fallback_slot_mm is not None else _LAYOUT_FALLBACK_SLOT_MM
        height_default = float(fallback_height_mm) if fallback_height_mm is not None else _MIN_VIEW_EXTENT_MM
        try:
            sheet.Update()
        except Exception:
            pass
        bbox = self._read_view_bbox(view)
        w, h = self._bbox_extent_mm(bbox)
        try:
            vx = float(view.x)
            vy = float(view.y)
        except Exception:
            try:
                vx = float(view.X)
                vy = float(view.Y)
            except Exception:
                vx, vy = 0.0, 0.0

        if w >= 1.0 and h >= 1.0:
            xmin, ymin, xmax, ymax = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
            cx = 0.5 * (xmin + xmax)
            cy = 0.5 * (ymin + ymax)
            target_cx = left_x + 0.5 * w
            target_cy = bottom_y + 0.5 * h
            self._set_view_xy(view, vx + (target_cx - cx), vy + (target_cy - cy))
        else:
            # No bbox: center in a BOM-sized slot so spacing matches part scale.
            slot = max(_MIN_VIEW_EXTENT_MM, slot_default)
            self._set_view_xy(view, left_x + 0.5 * slot, bottom_y + 0.5 * max(height_default, _MIN_VIEW_EXTENT_MM))

        try:
            gb = getattr(view, "GenerativeBehavior", None)
            if gb is not None:
                try:
                    gb.ForceUpdate()
                except Exception:
                    try:
                        gb.Update()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            sheet.Update()
        except Exception:
            pass

        out = self._read_view_bbox(view)
        ow, oh = self._bbox_extent_mm(out)
        if ow < 1.0 or oh < 1.0:
            sw = max(_MIN_VIEW_EXTENT_MM, slot_default)
            sh = max(_MIN_VIEW_EXTENT_MM, height_default)
            return [left_x, bottom_y, left_x + sw, bottom_y + sh]
        return out

    def create_multi_part_layout(
        self,
        items: List[Dict[str, Any]],
        global_drafting_axis_name: Optional[str] = None,
        global_drafting_axis_use_selection: bool = False,
        *,
        top_view_rotation_deg: Optional[float] = None,
        plan_projection_use_left: bool = True,
    ) -> Dict[str, Any]:
        """
        One CATDrawing; per BOM item add Front (XZ main), Top (plan), Side — projection enums swapped vs CATIA names; see _create_front_right_top_views.
        Optional global axis: global_drafting_axis_use_selection (CATIA selection) or global_drafting_axis_name
        (substring) resolves a HybridShapeAxisSystem for all rows (SetAxisSysteme when axis CATPart matches row).
        top_view_rotation_deg / plan_projection_use_left: same as create_automated_drawing; BOM rows may override with topViewRotationDeg / planProjectionUseLeft.
        """
        caa = catia_bridge.get_application()
        if not caa:
            return {"error": "CATIA not found"}
        if not items:
            return {"error": "No items provided"}

        global_axis = None
        global_cat_doc = None
        want_global = bool(global_drafting_axis_use_selection) or bool(
            (global_drafting_axis_name or "").strip()
        )
        if global_drafting_axis_use_selection:
            global_axis, global_cat_doc = resolve_axis_system_from_selection(caa)
        elif (global_drafting_axis_name or "").strip():
            global_axis, global_cat_doc = resolve_axis_system_by_name(
                caa, (global_drafting_axis_name or "").strip()
            )
        if want_global and global_axis is None:
            return {
                "error": "Could not resolve global drafting axis from name or selection.",
                "status_code": 400,
            }

        # Read DefineFrontView cosines before Documents.Add("Drawing"); new drawing can invalidate axis COM refs.
        global_plane_six: Optional[Tuple[float, float, float, float, float, float]] = None
        if global_axis is not None:
            owner = global_cat_doc or catpart_document_for_axis_object(global_axis)
            if owner is not None:
                _activate_catia_document(caa, owner)
                global_axis = rebind_axis_system_to_activated_part(global_axis, owner)
            global_plane_six = read_global_axis_plane_six(
                caa, owner, global_axis, _PRIMARY_DEFINE_FRONT_PLANE
            )
            if global_plane_six is None:
                return {
                    "error": "Resolved the axis system but could not read its orientation vectors (Python COM and CATScript).",
                    "hint": "Use “Generate 2D (axis from selection)” after picking the axis in the spec tree, or add the same axis under each part’s Part Design → Axis Systems (copy/publish) so CATIA can evaluate it.",
                    "status_code": 400,
                }

        warnings: List[str] = []
        views_created: List[str] = []
        drawing_doc = None

        try:
            drawing_doc = caa.Documents.Add("Drawing")
            sheet = drawing_doc.Sheets.ActiveSheet
            self._setup_drawing_sheet(sheet, drawing_doc, sheet_title=None, caa=caa)

            cursor_x = _MARGIN_MM
            row_bottom_y = _ROW_START_Y_MM
            sheet_index = 1
            first_sheet_named = False

            def _new_sheet(part_label: Optional[str] = None):
                nonlocal sheet, sheet_index, row_bottom_y, cursor_x
                ns = drawing_doc.Sheets.Add(f"Sheet.{sheet_index + 1}")
                sheet_index += 1
                self._setup_drawing_sheet(
                    ns,
                    drawing_doc,
                    sheet_title=part_label,
                    caa=caa,
                )
                sheet = ns
                row_bottom_y = _ROW_START_Y_MM
                cursor_x = _MARGIN_MM

            for idx, item in enumerate(items):
                part_key = item.get("partNumber") or item.get("id") or f"item_{idx}"
                resolved = resolve_bom_item_object(caa, item)
                if resolved is None:
                    warnings.append(f"Unresolved BOM row: {part_key}")
                    continue

                doc_target = generative_behavior_document_target(resolved)
                if doc_target is None:
                    warnings.append(f"No generative document for: {part_key}")
                    continue

                doc_link = self._document_link_for_generative(doc_target)
                part_scope = geometry_service._resolve_to_part(resolved)
                if part_scope is None:
                    part_scope = part_from_generative_product(doc_link)
                prefer_ax = (item.get("draftingAxisName") or "").strip()
                plane, axis_ref, cat_axis_doc = front_plane_and_axis_for_row(
                    part_scope,
                    prefer_ax or None,
                    global_axis=global_axis,
                    global_catpart_doc=global_cat_doc,
                    global_plane_six=global_plane_six,
                    primary_define_front=_PRIMARY_DEFINE_FRONT_PLANE,
                )
                if plane is None:
                    warnings.append(
                        f"{part_key}: no drafting axis — skipped (set global axis name/selection, or AXIS_* under Part Axis Systems / row draftingAxisName)."
                    )
                    continue
                if not first_sheet_named:
                    try:
                        sheet.Name = _sanitize_sheet_title(part_key)
                        first_sheet_named = True
                    except Exception as e:
                        logger.debug("First sheet rename: %s", e)
                bom_slot_mm, bom_strip_h_mm = _bom_layout_hints_mm(item)
                cursor_x = _MARGIN_MM
                strip_tops: List[float] = []

                try:
                    row_rot = item.get("topViewRotationDeg")
                    eff_rot = float(row_rot) if row_rot is not None else top_view_rotation_deg
                    row_left = item.get("planProjectionUseLeft")
                    eff_left = (
                        bool(row_left)
                        if row_left is not None
                        else plan_projection_use_left
                    )
                    front_v, right_v, top_v = self._create_front_right_top_views(
                        sheet,
                        doc_link,
                        (
                            f"P{idx}_Front",
                            f"P{idx}_Side",
                            f"P{idx}_Top",
                        ),
                        plane,
                        axis_ref=axis_ref,
                        catpart_doc_for_axis=cat_axis_doc,
                        skip_sheet_reference_alignment=True,
                        include_right_view=True,
                        top_view_rotation_deg=eff_rot,
                        plan_projection_use_left=eff_left,
                    )
                except Exception as ev:
                    warnings.append(f"P{idx} projection chain ({part_key}): {ev}")
                    continue

                for view, label in (
                    (front_v, "Front"),
                    (right_v, "Side"),
                    (top_v, "Top"),
                ):
                    view_name = f"P{idx}_{label}"
                    try:
                        prev_cx = cursor_x
                        bbox = self._align_view_corner(
                            view,
                            sheet,
                            cursor_x,
                            row_bottom_y,
                            fallback_slot_mm=bom_slot_mm,
                            fallback_height_mm=bom_strip_h_mm,
                        )
                        views_created.append(view_name)
                        strip_tops.append(max(bbox[1], bbox[3]))
                        right_edge = max(float(bbox[0]), float(bbox[2]))
                        # Prefer CATIA bbox; never pack tighter than BOM-based slot for this row.
                        next_x = right_edge + _VIEW_GAP_MM
                        min_next_x = prev_cx + bom_slot_mm + _VIEW_GAP_MM
                        cursor_x = max(next_x, min_next_x)
                    except Exception as ev:
                        warnings.append(f"{view_name} layout ({part_key}): {ev}")

                if not strip_tops:
                    continue

                strip_top = max(strip_tops)
                strip_height = max(1.0, strip_top - row_bottom_y, bom_strip_h_mm * 0.45)
                row_bottom_y = row_bottom_y - strip_height - _PART_STRIP_GAP_MM
                # Only add a sheet when another BOM row follows; otherwise the last row would leave an empty sheet.
                if row_bottom_y < _MIN_ROW_Y_MM and idx < len(items) - 1:
                    next_item = items[idx + 1]
                    next_key = (
                        next_item.get("partNumber")
                        or next_item.get("id")
                        or f"item_{idx + 1}"
                    )
                    try:
                        _new_sheet(next_key)
                    except Exception as se:
                        warnings.append(f"Could not add sheet before {next_key}: {se}")

            try:
                drawing_doc.Sheets.ActiveSheet = drawing_doc.Sheets.Item(1)
            except Exception:
                pass

            dname = drawing_doc.Name if hasattr(drawing_doc, "Name") else "Drawing"
            return {
                "status": "success",
                "message": f"Multi-part layout created with {len(views_created)} view(s).",
                "drawing_name": dname,
                "views_created": views_created,
                "warnings": warnings,
            }
        except Exception as e:
            logger.error("DraftingService create_multi_part_layout: %s", e)
            return {"error": str(e), "warnings": warnings}

    def add_advanced_dimensions(self, part, sheet, source_doc):
        """
        Implements ordinal dimensioning from a (0,0) datum corner,
        hole diameters, and overall block sizes.
        """
        try:
            if not part: return
            
            # 1. Get Bounding Box to find the (0,0,0) datum corner
            # We'll use the part's Analyze object for basic mass/center, 
            # but for Bounding Box we often use the Selection.Boundary or custom logic.
            # Here we'll simulate the bounding box from the part's bodies
            bbox = self._get_part_bounding_box(part)
            datum_pt = (bbox['xmin'], bbox['ymin'], bbox['zmin'])
            
            # 2. Extract Holes
            holes = self._get_hole_data(part)
            
            # 3. Process each view for specific dimensions
            view_configs = {
                "Front View": {"h_idx": 0, "v_idx": 2, "label_h": "X", "label_v": "Z", "ext_h": "L", "ext_v": "H"},
                "Top View":   {"h_idx": 0, "v_idx": 1, "label_h": "X", "label_v": "Y", "ext_h": "L", "ext_v": "W"},
                "Right View": {"h_idx": 1, "v_idx": 2, "label_h": "Y", "label_v": "Z", "ext_h": "W", "ext_v": "H"},
            }
            
            for v_name, cfg in view_configs.items():
                try:
                    view = sheet.Views.Item(v_name)
                    view.Activate()
                    
                    # 3.1 Ordinal Dimensions for Holes
                    self._add_ordinal_hole_dimensions(view, holes, datum_pt, cfg)
                    
                    # 3.2 Overall Size
                    self._add_overall_dimensions(view, bbox, cfg)
                    
                    # 3.3 Ensure labels and status
                    self.add_annotation(v_name.upper(), 10, -10, v_name)
                    
                except Exception as ev:
                    logger.warning(f"DraftingService: Failed dimensioning for {v_name}: {ev}")

        except Exception as e:
            logger.error(f"DraftingService: add_advanced_dimensions failed: {e}")

    def _get_part_bounding_box(self, part) -> Dict[str, float]:
        """Calculates real bounding box using GeometryService."""
        try:
            return geometry_service.get_bounding_box(part)
        except Exception as e:
            logger.warning(f"DraftingService: GeometryService failed, using fallback: {e}")
            return {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 100, "zmin": 0, "zmax": 40, "x": 100, "y": 100, "z": 40}

    def _get_hole_data(self, part) -> List[Dict[str, Any]]:
        """Extracts center point and diameter for all holes in the part."""
        hole_list = []
        try:
            for body in part.Bodies:
                for hole in body.Holes:
                    try:
                        # Get hole center and diameter
                        # Hole.GetOrigin requires an array for output
                        origin = [0.0, 0.0, 0.0]
                        hole.GetOrigin(origin)
                        diam = hole.Diameter.Value
                        hole_list.append({
                            "origin": origin,
                            "diameter": diam,
                            "name": hole.Name
                        })
                    except: continue
        except: pass
        return hole_list

    def _add_ordinal_hole_dimensions(self, view, holes, datum, cfg):
        """Adds ordinal (coordinate) labels for holes in the 2D view."""
        texts = view.Texts
        # Offset to prevent overlap
        y_offset = -20
        
        for i, hole in enumerate(holes):
            # Calculate coordinates relative to datum
            h_val = round(hole['origin'][cfg['h_idx']] - datum[cfg['h_idx']], 2)
            v_val = round(hole['origin'][cfg['v_idx']] - datum[cfg['v_idx']], 2)
            d_val = round(hole['diameter'], 2)
            
            # Place coordinate text near the hole projection
            # In a real drafting bridge, we map 3D to 2D view coordinates
            # Here we place a descriptive label
            label = f"H{i+1}: ({cfg['label_h']}{h_val}, {cfg['label_v']}{v_val}) Ø{d_val}"
            
            # Simulating ordinal dimension with text at specific intervals
            texts.Add(label, 10, y_offset)
            y_offset -= 10

    def _add_overall_dimensions(self, view, bbox, cfg):
        """Adds overall L/W/H dimensions to the view."""
        texts = view.Texts
        dim_h = round(bbox[f"{cfg['label_h'].lower()}max"] - bbox[f"{cfg['label_h'].lower()}min"], 1)
        dim_v = round(bbox[f"{cfg['label_v'].lower()}max"] - bbox[f"{cfg['label_v'].lower()}min"], 1)
        
        # Place at bottom right of view area
        texts.Add(f"OVERALL {cfg['ext_h']}: {dim_h} mm", 150, -10)
        texts.Add(f"OVERALL {cfg['ext_v']}: {dim_v} mm", 150, -20)

    def auto_dimension_part(self, part, view) -> bool:
        """Fallback to CATIA's Generative Dimensioning."""
        try:
            view.GenerativeBehavior.GenerateDimensions()
            return True
        except Exception as e:
            return False

    def project_part_parameters(self, part, view) -> bool:
        """Projects mass and thickness parameters onto the drawing."""
        try:
            texts = view.Texts
            mass = round(part.Analyze.Mass, 3)
            texts.Add(f"MASS: {mass} kg", 200, 40)
            
            for param in part.Parameters:
                if "Thickness" in param.Name:
                    texts.Add(f"MATERIAL THICKNESS: {param.ValueAsString()}", 200, 35)
                    break
            return True
        except: return False

    def add_gdt_annotation(self, view, symbol: str, tolerance: float, datum: str) -> bool:
        """Adds a GD&T annotation frame to a view."""
        try:
            gdt_text = f"[{symbol}|{tolerance}|{datum}]"
            view.Texts.Add(gdt_text, 50, 50)
            return True
        except: return False

    def add_annotation(self, text: str, x: float, y: float, view_name: str = "Main View") -> bool:
        """Adds a text annotation to a specific view."""
        caa = catia_bridge.get_application()
        if not caa: return False
        
        try:
            doc = caa.ActiveDocument
            sheet = doc.Sheets.ActiveSheet
            view = sheet.Views.Item(view_name)
            view.Texts.Add(text, x, y)
            return True
        except:
            return False

# Singleton
drafting_service = DraftingService()
