import win32com.client
import win32gui
import win32con
import time
import re
import math
import os
import shutil
import logging
import threading
import pythoncom

from app.debug_agent_log import agent_ndjson

logger = logging.getLogger(__name__)

# Rough Stock iteration tuning (balanced defaults).
MAX_RS_PASSES_PER_PART = 2
EXHAUSTIVE_RS_MEASUREMENT = False

# When set, skip SPA-in-axis path and use legacy dialog scraping only.
_DISABLE_AXIS_FRAME_STOCK = os.environ.get("CADMATION_DISABLE_AXIS_FRAME_STOCK", "").strip() in ("1", "true", "yes")

# When set, measure Rough Stock in the current window (no Open/Close of the CATPart).
_IN_PLACE_ROUGH_STOCK = True # Forced True as per user request to disable new windows

# Delay after Selection.Add(body) before scraping Rough Stock dialog (CATIA compute time).
_SCRAPE_PRE_DELAY_SEC = 4.0

# Re-select / re-wait when WM_GETTEXT on the ListBox is stale ("EdtPartBody") or shows another part\body.
_RS_BODY_LABEL_MATCH_ATTEMPTS = max(1, int(os.environ.get("CADMATION_RS_BODY_LABEL_ATTEMPTS", "5") or "5"))

# Re-read DX/DY/DZ until unchanged (CATIA sometimes updates Z spinners after X/Y).
_RS_DIM_SETTLE_ATTEMPTS = max(1, int(os.environ.get("CADMATION_RS_DIM_SETTLE_ATTEMPTS", "8") or "8"))
_RS_DIM_SETTLE_PAUSE_SEC = float(os.environ.get("CADMATION_RS_DIM_SETTLE_PAUSE", "0.75") or "0.75")

# Poll the "Select part … to offset" line until it shows the BOM part\body (dialog updates after selection).
_RS_PART_OFFSET_POLL_SEC = float(os.environ.get("CADMATION_RS_PART_OFFSET_POLL", "0.22") or "0.22")
_RS_PART_OFFSET_MAX_WAIT = float(os.environ.get("CADMATION_RS_PART_OFFSET_WAIT", "12") or "12")

# Default: Bodies.Item(1), then Item(2), … — first with Shapes/HybridShapes wins (no body-name Search).
_RS_BODY_MODE = os.environ.get("CADMATION_RS_BODY_RESOLUTION", "auto").strip().lower()

# Axis systems matching these names (substring, case-insensitive) are used for stock extents before UI scraping.
_PREFERRED_AXIS_SUBSTRINGS = (
    "INSERTION_AXIS",
    "INSERTION AXIS",
    "INSERTION",
    "MACHINING_AXIS",
    "MACHINING AXIS",
    "STOCK_AXIS",
    "STOCK AXIS",
    "AP_AXIS",
    "PART_AXIS",
)

# Global flag to control the monitor thread
_monitor_active = False
_monitor_thread = None

# COM Search timeout (seconds); CATIA Search can block if recomputing heavy geometry
_COM_SEARCH_TIMEOUT_SEC = 8


def _com_search_with_timeout(sel, pattern: str, timeout: float = _COM_SEARCH_TIMEOUT_SEC):
    """
    Perform a safe, synchronous search with null-checks and error boundaries.
    Reverting to synchronous to maximize stability across different CATIA environments.
    """
    if sel is None:
        logger.warning(f"Rough Stock: Selection is None; cannot search for {pattern}")
        return

    try:
        # Check if selection is stale by accessing a simple property
        _ = sel.Count
    except Exception as e:
        logger.error(f"Rough Stock: Selection is stale or RPC unavailable: {e}")
        return

    try:
        start_t = time.time()
        # We don't use real threading here to avoid Apartment crashes, 
        # but we log the time taken to identify bottlenecks.
        sel.Search(pattern)
        elapsed = time.time() - start_t
        if elapsed > 1.0:
            logger.info("Rough Stock: Search(%r) took %.2fs", pattern, elapsed)
    except Exception as e:
        # Catch typical 'Application Busy' or 'Call Rejected' errors
        err_msg = str(e)
        if "0x8001010A" in err_msg or "0x800706BE" in err_msg:
            logger.warning(f"Rough Stock: CATIA Busy/RPC Error during search ({pattern}): {e}")
        else:
            logger.error(f"Rough Stock: Unexpected search error ({pattern}): {e}")
        # We swallow the error here so the calling measure_body_in_dialog can return None 
        # instead of crashing the main process.

class RoughStockService:
    @staticmethod
    def _body_is_empty_for_rough_stock(body):
        """True if no Part-Design / hybrid content under the body (COM only, not by name)."""
        if body is None:
            return True
        try:
            sh = getattr(body, "Shapes", None)
            if sh is not None and sh.Count > 0:
                return False
        except Exception:
            pass
        try:
            hy = getattr(body, "HybridShapes", None)
            if hy is not None and hy.Count > 0:
                return False
        except Exception:
            pass
        return True

    @staticmethod
    def _ordered_bodies(root_part):
        coll = getattr(root_part, "Bodies", None)
        if coll is None or coll.Count < 1:
            return []
        return [coll.Item(i) for i in range(1, coll.Count + 1)]

    @staticmethod
    def _first_nonempty_body_sequential(root_part):
        """Bodies.Item(1), then Item(2), … — first with Shapes or HybridShapes."""
        ordered = RoughStockService._ordered_bodies(root_part)
        for idx, b in enumerate(ordered, start=1):
            if not RoughStockService._body_is_empty_for_rough_stock(b):
                logger.info(
                    "Rough Stock: using Bodies.Item(%s) — first slot with geometry (scanned upward).",
                    idx,
                )
                return b
        return None

    @staticmethod
    def _preferred_main_body(root_part):
        """Plate/die templates: use MAIN_BODY when it exists and has solid/hybrid content."""
        for b in RoughStockService._ordered_bodies(root_part):
            nm = (getattr(b, "Name", "") or "").strip().upper().replace(" ", "_")
            if nm == "MAIN_BODY" and not RoughStockService._body_is_empty_for_rough_stock(b):
                return b
        return None

    @staticmethod
    def _bodies_for_rough_stock(root_part):
        """Default: sequential scan Item(1), Item(2), … for first non-empty body. Optional CADMATION_RS_BODY_RESOLUTION."""
        out = []
        if root_part is None:
            return out
        try:
            ordered = RoughStockService._ordered_bodies(root_part)
            if not ordered:
                return out
            n = len(ordered)
            non_empty = [b for b in ordered if not RoughStockService._body_is_empty_for_rough_stock(b)]
            mode = _RS_BODY_MODE

            if mode.startswith("index:"):
                try:
                    k = int(mode.split(":", 1)[1].strip())
                except ValueError:
                    k = 1
                k = max(1, min(k, n))
                out.append(ordered[k - 1])
                return out
            if mode == "first_tree":
                out.append(ordered[0])
                return out
            if mode == "last_tree":
                out.append(ordered[-1])
                return out
            if mode == "all":
                use = non_empty if non_empty else ordered
                out.extend(use)
                return out
            if mode in ("last", "last_non_empty", "last_if_multiple"):
                pick = non_empty[-1] if non_empty else ordered[-1]
                out.append(pick)
                return out
            # auto, first, first_non_empty: prefer MAIN_BODY before first sequential non-empty
            if mode in ("auto", "first", "first_non_empty", "first_nonempty"):
                pref = RoughStockService._preferred_main_body(root_part)
                if pref is not None:
                    out.append(pref)
                    logger.info(
                        "Rough Stock: using %r (preferred over first tree slot with geometry).",
                        getattr(pref, "Name", ""),
                    )
                    return out
            # unknown / default → Item(1) then Item(2) … first non-empty
            pick = RoughStockService._first_nonempty_body_sequential(root_part)
            out.append(pick if pick is not None else ordered[0])
        except Exception as e:
            logger.error("Rough Stock: _bodies_for_rough_stock failed: %s", e)
        return out

    @staticmethod
    def _same_catia_document(doc_a, doc_b):
        if doc_a is None or doc_b is None:
            return False
        try:
            fa = RoughStockService._norm_fs_path(getattr(doc_a, "FullName", "") or "")
            fb = RoughStockService._norm_fs_path(getattr(doc_b, "FullName", "") or "")
            return bool(fa and fa == fb)
        except Exception:
            return False

    @staticmethod
    def _search_name_escape(s):
        return (s or "").replace("'", "''")

    @staticmethod
    def _selection_hit_is_wrong_for_rough_stock(hit_value, target_body) -> bool:
        """Reject analysis nodes; when BOM passes a target Body, require same COM object (else MAIN_BODY hits the wrong part)."""
        if hit_value is None:
            return True
        try:
            nm = (getattr(hit_value, "Name", "") or "").upper().replace(" ", "")
            if "INERTIA" in nm or "INERTIAVOLUME" in nm or "MEASURE" in nm:
                return True
        except Exception:
            pass
        if target_body is not None:
            try:
                return not RoughStockService._com_same_object(hit_value, target_body)
            except Exception:
                return True
        return False

    @staticmethod
    def _pick_search_hit_index_for_rough_stock(sel, target_body) -> int:
        """First Selection item acceptable for Rough Stock; scan all hits when Name='MAIN_BODY' matches many parts."""
        try:
            n = int(sel.Count)
        except Exception:
            return 0
        for i in range(1, n + 1):
            try:
                v = sel.Item(i).Value
            except Exception:
                continue
            if RoughStockService._selection_hit_is_wrong_for_rough_stock(v, target_body):
                continue
            # region agent log
            if n > 1:
                try:
                    agent_ndjson(
                        "H18",
                        "rough_stock._pick_search_hit_index_for_rough_stock",
                        "chose hit among multiple Search results",
                        {
                            "picked_index": i,
                            "sel_count": n,
                            "target_body_name": getattr(target_body, "Name", None),
                        },
                    )
                except Exception:
                    pass
            # endregion
            return i
        return 0

    @staticmethod
    def _try_select_body_via_part_reference(sel, root_part, target_body) -> bool:
        """Match manual tree pick: Part body reference, not a global Search hit (avoids InertiaVolume.*)."""
        if sel is None or root_part is None or target_body is None:
            return False
        try:
            sel.Clear()
        except Exception:
            pass
        try:
            ref = root_part.CreateReferenceFromObject(target_body)
            sel.Add(ref)
            if sel.Count >= 1:
                return True
        except Exception:
            pass
        try:
            sel.Clear()
            sel.Add(target_body)
            if sel.Count >= 1:
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _com_same_object(a, b) -> bool:
        if a is None or b is None:
            return False
        if a is b:
            return True
        try:
            oa, ob = getattr(a, "_oleobj_", None), getattr(b, "_oleobj_", None)
            return oa is not None and oa == ob
        except Exception:
            return False

    @staticmethod
    def _root_product_of_tree_node(prod):
        curr = prod
        for _ in range(200):
            try:
                p = curr.Parent
            except Exception:
                break
            if p is None:
                break
            curr = p
        return curr

    @staticmethod
    def _document_containing_product_instance(catia, target_product):
        """CATProduct window that owns this tree node (ActiveDocument is often the wrong tab)."""
        if target_product is None or catia is None:
            return None

        def subtree_has(root, want, depth):
            if depth > 200:
                return False
            if RoughStockService._com_same_object(root, want):
                return True
            try:
                ch = root.Products
                for i in range(1, ch.Count + 1):
                    if subtree_has(ch.Item(i), want, depth + 1):
                        return True
            except Exception:
                pass
            return False

        try:
            tree_root = RoughStockService._root_product_of_tree_node(target_product)
            for di in range(1, catia.Documents.Count + 1):
                d = catia.Documents.Item(di)
                doc_root = getattr(d, "Product", None)
                if doc_root is None:
                    continue
                if RoughStockService._com_same_object(doc_root, tree_root):
                    return d
            for di in range(1, catia.Documents.Count + 1):
                d = catia.Documents.Item(di)
                root = getattr(d, "Product", None)
                if root is None:
                    continue
                if subtree_has(root, target_product, 0):
                    return d
        except Exception:
            pass
        return None

    @staticmethod
    def _apply_rough_stock_body_selection(
        catia, root_part, scope_product, anchor_asm_doc, target_body
    ):
        """
        Body is always chosen by index/emptiness first; CATIA Rough Stock still needs instance-scoped
        Search under the Product for the command field to update (Add alone often leaves 'No Selection').
        """
        if target_body is None:
            return False
        body_nm = getattr(target_body, "Name", "") or ""
        part_nm = (getattr(root_part, "Name", "") or "").strip() if root_part else ""
        part_doc = None
        try:
            if root_part is not None:
                part_doc = root_part.Parent
        except Exception:
            part_doc = None
        if part_doc is None:
            try:
                par = getattr(target_body, "Parent", None)
                if par is not None and getattr(par, "Bodies", None) is not None:
                    part_doc = par.Parent
            except Exception:
                pass
        if part_doc is None:
            logger.warning("Rough Stock: cannot resolve CATPart document for selection.")
            return False

        # 1) Assembly BOM: Add(instance) + Search ,in — only way Rough Stock UI reliably picks up the body
        if scope_product is not None and body_nm:
            doc_owning_tree = None
            try:
                doc_owning_tree = RoughStockService._document_containing_product_instance(
                    catia, scope_product
                )
            except Exception:
                pass
            seen_anchor_fp = set()
            anchors_ordered = []
            for cand in (doc_owning_tree, anchor_asm_doc):
                if cand is None:
                    continue
                fp = RoughStockService._norm_fs_path(getattr(cand, "FullName", "") or "")
                if fp and fp in seen_anchor_fp:
                    continue
                if fp:
                    seen_anchor_fp.add(fp)
                anchors_ordered.append(cand)

            be = RoughStockService._search_name_escape(body_nm)
            for anchor in anchors_ordered:
                try:
                    try:
                        anchor.Activate()
                    except Exception:
                        try:
                            catia.ActiveDocument = anchor
                        except Exception:
                            continue
                    time.sleep(0.18)
                    sel = catia.ActiveDocument.Selection
                    scoped_ok = False
                    logger.info("Rough Stock: starting assembly-scoped Search for body %r...", body_nm)
                    for pattern in (
                        f"Name='{be}',Type=Body,in",
                        f"Name='{be}',in",
                    ):
                        try:
                            sel.Clear()
                            sel.Add(scope_product)
                            _com_search_with_timeout(sel, pattern)
                            pick_i = RoughStockService._pick_search_hit_index_for_rough_stock(
                                sel, target_body
                            )
                            if pick_i > 0:
                                v = sel.Item(pick_i).Value
                                sel.Clear()
                                sel.Add(v)
                                logger.info(
                                    "Rough Stock: assembly-scoped Search bound body to command (under %r).",
                                    getattr(scope_product, "Name", "?"),
                                )
                                scoped_ok = True
                                break
                        except Exception as se:
                            logger.info("Rough Stock: scoped Search failed/skipped %s: %s", pattern, se)
                    if scoped_ok:
                        return True
                except Exception as e:
                    logger.debug("Rough Stock: assembly scoped selection (anchor): %s", e)

        # 2) Target CATPart: under assembly instance, Search in .CATPart updates Rough Stock; Part ref alone often leaves stale dialog.
        if body_nm:
            try:
                try:
                    part_doc.Activate()
                except Exception:
                    try:
                        catia.ActiveDocument = part_doc
                    except Exception:
                        pass
                time.sleep(0.15)
                sel = catia.ActiveDocument.Selection
                be = RoughStockService._search_name_escape(body_nm)
                if scope_product is None and RoughStockService._try_select_body_via_part_reference(
                    sel, root_part, target_body
                ):
                    logger.info(
                        "Rough Stock: Part body reference for Rough Stock UI (%r) (standalone part).",
                        body_nm,
                    )
                    return True
                for pattern in (
                    f"Name='{be}',Type=Body,all",
                    f"Name='{be}',all",
                ):
                    try:
                        sel.Clear()
                        _com_search_with_timeout(sel, pattern)
                        pick_i = RoughStockService._pick_search_hit_index_for_rough_stock(
                            sel, target_body
                        )
                        if pick_i > 0:
                            v = sel.Item(pick_i).Value
                            sel.Clear()
                            sel.Add(v)
                            logger.info(
                                "Rough Stock: in-document body Search bound for Rough Stock UI (%r).",
                                body_nm,
                            )
                            return True
                    except TimeoutError as se:
                        logger.warning("Rough Stock: in-doc body Search TIMED OUT %s: %s", pattern, se)
                    except Exception as se:
                        logger.debug("Rough Stock: in-doc body Search %s: %s", pattern, se)
                if RoughStockService._try_select_body_via_part_reference(
                    sel, root_part, target_body
                ):
                    logger.info(
                        "Rough Stock: Part body reference fallback for Rough Stock UI (%r).",
                        body_nm,
                    )
                    return True
            except Exception as e:
                logger.debug("Rough Stock: in-doc body path: %s", e)

        if part_nm and body_nm:
            try:
                try:
                    part_doc.Activate()
                except Exception:
                    try:
                        catia.ActiveDocument = part_doc
                    except Exception:
                        pass
                time.sleep(0.12)
                sel = catia.ActiveDocument.Selection
                composite = RoughStockService._search_name_escape(f"{part_nm}\\{body_nm}")
                for pattern in (
                    f"Name='{composite}',Type=Body,all",
                    f"Name='{composite}',all",
                ):
                    try:
                        sel.Clear()
                        _com_search_with_timeout(sel, pattern)
                        pick_i = RoughStockService._pick_search_hit_index_for_rough_stock(
                            sel, target_body
                        )
                        if pick_i > 0:
                            v = sel.Item(pick_i).Value
                            sel.Clear()
                            sel.Add(v)
                            logger.info("Rough Stock: composite Search bound body for Rough Stock UI.")
                            return True
                    except TimeoutError as se:
                        logger.warning("Rough Stock: composite Search TIMED OUT %s: %s", pattern, se)
                    except Exception as se:
                        logger.debug("Rough Stock: composite Search %s: %s", pattern, se)
            except Exception as e:
                logger.debug("Rough Stock: composite path: %s", e)

        if scope_product is not None:
            try:
                part_doc.Activate()
            except Exception:
                try:
                    catia.ActiveDocument = part_doc
                except Exception:
                    logger.warning(
                        "Rough Stock: assembly scope set; could not activate target CATPart for last-resort bind."
                    )
                    return False
            time.sleep(0.15)
            try:
                ad = catia.ActiveDocument
            except Exception:
                ad = None
            if ad is None or not RoughStockService._same_catia_document(ad, part_doc):
                logger.warning(
                    "Rough Stock: assembly scope set; active document is not target CATPart — "
                    "skipping Add(body) to avoid stale Rough Stock values."
                )
                return False
            try:
                sel = ad.Selection
                rp = root_part or getattr(target_body, "Parent", None)
                if rp is not None:
                    try:
                        sel.Clear()
                        sel.Add(rp.CreateReferenceFromObject(target_body))
                        if sel.Count >= 1:
                            logger.warning(
                                "Rough Stock: assembly Search failed; Part reference with CATPart active."
                            )
                            return True
                    except Exception:
                        pass
                sel.Clear()
                sel.Add(target_body)
                if sel.Count >= 1:
                    logger.warning(
                        "Rough Stock: assembly Search failed; Add(body) with target CATPart active "
                        "(verify dimensions match this part)."
                    )
                    return True
            except Exception as e:
                logger.warning("Rough Stock: scoped last-resort Add failed: %s", e)
            return False

        # 3) Direct COM (standalone CATPart / no assembly scope — Add may still update the command)
        try:
            try:
                part_doc.Activate()
            except Exception:
                try:
                    catia.ActiveDocument = part_doc
                except Exception as ex:
                    logger.warning("Rough Stock: Part document Activate failed: %s", ex)
            time.sleep(0.12)
            sel = catia.ActiveDocument.Selection
            rp = root_part or getattr(target_body, "Parent", None)
            if rp is not None:
                try:
                    sel.Clear()
                    sel.Add(rp.CreateReferenceFromObject(target_body))
                    if sel.Count >= 1:
                        logger.info("Rough Stock: Selection.Add(Part reference) fallback OK.")
                        return True
                except Exception:
                    pass
            sel.Clear()
            sel.Add(target_body)
            if sel.Count >= 1:
                logger.info("Rough Stock: Selection.Add(body) fallback OK.")
                return True
        except Exception as e:
            logger.warning("Rough Stock: Selection.Add fallback failed: %s", e)
        return False

    @staticmethod
    def start_dialog_monitor(interval=0.5):
        """Starts a background thread to clear CATIA popups."""
        global _monitor_active, _monitor_thread
        if _monitor_active: return
        
        _monitor_active = True
        def monitor_loop():
            pythoncom.CoInitialize()
            logger.info("Background dialog monitor started.")
            while _monitor_active:
                try:
                    hw_err = RoughStockService._find_error_window()
                    if hw_err:
                        msg = win32gui.GetWindowText(hw_err)
                        logger.warning(f"AUTO-CLEARING: {msg}")
                        RoughStockService._close_error_window(hw_err)
                except Exception as e:
                    pass
                time.sleep(interval)
            pythoncom.CoUninitialize()
        
        _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        _monitor_thread.start()

    @staticmethod
    def stop_dialog_monitor():
        global _monitor_active
        _monitor_active = False

    @staticmethod
    def _find_window():
        hw_found = []
        def cb(hwnd, found):
            if not win32gui.IsWindowVisible(hwnd): return
            if win32gui.GetWindowText(hwnd) == "Rough Stock":
                found.append(hwnd)
        win32gui.EnumWindows(cb, hw_found)
        return hw_found[0] if hw_found else 0

    @staticmethod
    def _find_error_window():
        hw_found = []
        def cb(hwnd, found):
            if not win32gui.IsWindowVisible(hwnd): return
            title = win32gui.GetWindowText(hwnd).strip()
            if title in ["Power input message", "New", "CATIA V5"] or "Power input" in title:
                found.append(hwnd)
        win32gui.EnumWindows(cb, hw_found)
        return hw_found[0] if hw_found else 0

    @staticmethod
    def _close_error_window(hw):
        try:
            def btn_cb(h, res):
                if win32gui.GetClassName(h) == "Button":
                    txt = win32gui.GetWindowText(h).upper()
                    if any(x in txt for x in ["OK", "CANCEL", "CLOSE", "YES", "NO"]):
                        res.append(h)
            btns = []
            win32gui.EnumChildWindows(hw, btn_cb, btns)
            for btn in btns:
                win32gui.PostMessage(btn, win32con.BM_CLICK, 0, 0)
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
        except:
            pass

    @staticmethod
    def _vec_norm(v):
        l = math.sqrt(sum(x * x for x in v))
        if l < 1e-18:
            return None
        return [x / l for x in v]

    @staticmethod
    def _vec_cross(a, b):
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]

    @staticmethod
    def _bbox_corners_mm_from_spa_m(bb6):
        """SPA GetBoundaryBox: xmin,xmax, ymin,ymax, zmin,zmax in meters -> 8 corners in mm."""
        sx = bb6[0] * 1000.0
        ex = bb6[1] * 1000.0
        sy = bb6[2] * 1000.0
        ey = bb6[3] * 1000.0
        sz = bb6[4] * 1000.0
        ez = bb6[5] * 1000.0
        corners = []
        for x in (sx, ex):
            for y in (sy, ey):
                for z in (sz, ez):
                    corners.append([x, y, z])
        return corners

    @staticmethod
    def _extent_along_unit_axes(corners_mm, origin_mm, ex, ey, ez):
        """Min/max projection of (corner - origin) onto orthonormal ex,ey,ez; returns (dx,dy,dz) mm."""
        lx, ly, lz = [], [], []
        for c in corners_mm:
            d = [c[i] - origin_mm[i] for i in range(3)]
            lx.append(d[0] * ex[0] + d[1] * ex[1] + d[2] * ex[2])
            ly.append(d[0] * ey[0] + d[1] * ey[1] + d[2] * ey[2])
            lz.append(d[0] * ez[0] + d[1] * ez[1] + d[2] * ez[2])
        return max(lx) - min(lx), max(ly) - min(ly), max(lz) - min(lz)

    @staticmethod
    def _get_axis_orthonormal_basis_mm(axis_obj):
        """Origin + X,Y,Z unit vectors; origin in mm (CATIA Part axis APIs are typically mm)."""
        try:
            o = [0.0, 0.0, 0.0]
            axis_obj.GetOrigin(o)
        except Exception:
            return None
        vx, vy = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        try:
            axis_obj.GetVectors(vx, vy)
        except Exception:
            try:
                axis_obj.XAxis.GetDirection(vx)
                axis_obj.YAxis.GetDirection(vy)
            except Exception:
                return None
        ex = RoughStockService._vec_norm(vx)
        ey0 = RoughStockService._vec_norm(vy)
        if not ex or not ey0:
            return None
        ez = RoughStockService._vec_norm(RoughStockService._vec_cross(ex, ey0))
        if not ez:
            return None
        ey = RoughStockService._vec_norm(RoughStockService._vec_cross(ez, ex))
        if not ey:
            return None
        return (o, ex, ey, ez)

    @staticmethod
    def _axis_name_matches(name, substrings):
        u = (name or "").upper().replace(" ", "_")
        for s in substrings:
            t = s.upper().replace(" ", "_")
            if t in u or u == t:
                return True
        return False

    @staticmethod
    def _find_preferred_axis_system(part):
        """Prefer machining / insertion axis so stock matches Rough Stock with that frame (not absolute)."""
        if part is None:
            return None
        extra = os.environ.get("CADMATION_STOCK_AXIS_SUBSTRING", "").strip().upper()
        subs = list(_PREFERRED_AXIS_SUBSTRINGS)
        if extra:
            subs.insert(0, extra)
        try:
            coll = part.AxisSystems
            for i in range(1, coll.Count + 1):
                ax = coll.Item(i)
                nm = getattr(ax, "Name", "") or ""
                if RoughStockService._axis_name_matches(nm, subs):
                    return ax
        except Exception:
            pass
        try:
            coll = part.AxisSystems
            for i in range(1, coll.Count + 1):
                ax = coll.Item(i)
                nm = (getattr(ax, "Name", "") or "").upper()
                if "INSERTION" in nm and "AXIS" in nm.replace(" ", ""):
                    return ax
        except Exception:
            pass
        return RoughStockService._find_axis_in_hybrid_bodies(part, subs)

    @staticmethod
    def _find_axis_in_hybrid_bodies(part, substrings):
        seen = set()

        def walk_hb(hb, depth):
            if depth > 12 or id(hb) in seen:
                return None
            seen.add(id(hb))
            try:
                for i in range(1, hb.HybridShapes.Count + 1):
                    hs = hb.HybridShapes.Item(i)
                    nm = getattr(hs, "Name", "") or ""
                    if not RoughStockService._axis_name_matches(nm, substrings):
                        if "INSERTION" not in nm.upper() or "AXIS" not in nm.upper().replace(" ", ""):
                            continue
                    try:
                        o = [0.0, 0.0, 0.0]
                        hs.GetOrigin(o)
                        return hs
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                for j in range(1, hb.HybridBodies.Count + 1):
                    r = walk_hb(hb.HybridBodies.Item(j), depth + 1)
                    if r:
                        return r
            except Exception:
                pass
            return None

        try:
            for i in range(1, part.HybridBodies.Count + 1):
                r = walk_hb(part.HybridBodies.Item(i), 0)
                if r:
                    return r
        except Exception:
            pass
        return None

    @staticmethod
    def _try_spa_bbox_in_preferred_axis(catia, root_part, bodies):
        """
        Same extents as Rough Stock when an axis is set: AABB of the body in that axis frame.
        Avoids dialog scraping with an empty axis field (absolute / wrong BOM sizes).
        """
        if _DISABLE_AXIS_FRAME_STOCK or not root_part or not bodies:
            return None
        axis = RoughStockService._find_preferred_axis_system(root_part)
        if not axis:
            logger.info("Rough Stock: no preferred axis system; using dialog scrape (absolute frame).")
            return None
        basis = RoughStockService._get_axis_orthonormal_basis_mm(axis)
        if not basis:
            logger.warning("Rough Stock: could not read axis basis; falling back to dialog scrape.")
            return None
        o_mm, ex, ey, ez = basis
        try:
            part_doc = root_part.Parent
            spa = part_doc.GetWorkbench("SPAWorkbench")
        except Exception as e:
            logger.debug(f"SPA axis-frame path failed opening workbench: {e}")
            return None
        dx_max = dy_max = dz_max = 0.0
        for body in bodies[: max(1, MAX_RS_PASSES_PER_PART)]:
            try:
                sel = part_doc.Selection
                sel.Clear()
                sel.Add(body)
                if sel.Count < 1:
                    continue
                m = spa.GetMeasurable(sel.Item(1).Value)
                bb = [0.0] * 6
                m.GetBoundaryBox(bb)
                corners = RoughStockService._bbox_corners_mm_from_spa_m(bb)
                ddx, ddy, ddz = RoughStockService._extent_along_unit_axes(corners, o_mm, ex, ey, ez)
                if ddx > dx_max:
                    dx_max = ddx
                if ddy > dy_max:
                    dy_max = ddy
                if ddz > dz_max:
                    dz_max = ddz
            except Exception as e:
                logger.debug(f"SPA axis-frame measure failed for body: {e}")
                continue
        if dx_max > 0.001 and dy_max > 0.001 and dz_max > 0.001:
            logger.info(
                f"Rough Stock: SPA extents in axis '{getattr(axis, 'Name', '?')}' "
                f"= {dx_max:.3f} x {dy_max:.3f} x {dz_max:.3f} mm (dialog axis not automated)."
            )
            return dx_max, dy_max, dz_max
        return None

    @staticmethod
    def _try_spa_axis_aligned_bbox_mm(catia, root_part, bodies):
        """
        SPA GetBoundaryBox in document/world order (xmin,xmax, ymin,ymax, zmin,zmax in m).
        Matches flat-plate thickness vs Rough Stock when dialog shows inconsistent Z vs XY.
        """
        if _DISABLE_AXIS_FRAME_STOCK or not root_part or not bodies:
            return None
        try:
            part_doc = root_part.Parent
            spa = part_doc.GetWorkbench("SPAWorkbench")
        except Exception:
            return None
        dx_max = dy_max = dz_max = 0.0
        for body in bodies[: max(1, MAX_RS_PASSES_PER_PART)]:
            try:
                sel = part_doc.Selection
                sel.Clear()
                sel.Add(body)
                if sel.Count < 1:
                    continue
                m = spa.GetMeasurable(sel.Item(1).Value)
                bb = [0.0] * 6
                m.GetBoundaryBox(bb)
                dx = abs(bb[1] - bb[0]) * 1000.0
                dy = abs(bb[3] - bb[2]) * 1000.0
                dz = abs(bb[5] - bb[4]) * 1000.0
                if dx > dx_max:
                    dx_max = dx
                if dy > dy_max:
                    dy_max = dy
                if dz > dz_max:
                    dz_max = dz
            except Exception:
                continue
        if dx_max > 0.001 and dy_max > 0.001 and dz_max > 0.001:
            asc = sorted((dx_max, dy_max, dz_max))
            lo, mid, hi = asc[0], asc[1], asc[2]
            # Cube-like parts: keep dialog scrape (matches LOWER STEEL path).
            if hi / max(lo, 0.01) < 6.0:
                return None
            logger.info(
                "Rough Stock: SPA world extents sorted %.3f ≤ %.3f ≤ %.3f mm → stock L×W×T %.3f × %.3f × %.3f.",
                lo,
                mid,
                hi,
                hi,
                mid,
                lo,
            )
            return hi, mid, lo
        return None

    @staticmethod
    def _norm_fs_path(p):
        if not p:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(p)))
        except Exception:
            return (p or "").strip()

    @staticmethod
    def _resolve_catpart_path_from_target(target_obj):
        """Filesystem path to the CATPart backing this Product/Part, or None."""
        if target_obj is None:
            return None
        # BOM websocket passes ActiveDocument when the window is a .CATPart (see catia.py).
        try:
            if getattr(target_obj, "Part", None) is not None:
                fn = getattr(target_obj, "FullName", "") or ""
                if fn.lower().endswith(".catpart") and os.path.isfile(fn):
                    return os.path.abspath(fn)
        except Exception:
            pass
        try:
            _ = target_obj.Bodies
            doc = target_obj.Parent
            fn = getattr(doc, "FullName", "") or ""
            if fn.lower().endswith(".catpart") and os.path.isfile(fn):
                return os.path.abspath(fn)
        except Exception:
            pass
        # PartDesign Body: Parent is Part → Part.Parent is CATPart document.
        try:
            par = getattr(target_obj, "Parent", None)
            if par is not None and getattr(par, "Bodies", None) is not None:
                doc = getattr(par, "Parent", None)
                if doc is not None:
                    fn = getattr(doc, "FullName", "") or ""
                    if fn.lower().endswith(".catpart") and os.path.isfile(fn):
                        return os.path.abspath(fn)
        except Exception:
            pass
        try:
            ref = getattr(target_obj, "ReferenceProduct", None)
            if ref:
                parent = getattr(ref, "Parent", None)
                fn = getattr(parent, "FullName", "") or ""
                if fn.lower().endswith(".catpart") and os.path.isfile(fn):
                    return os.path.abspath(fn)
        except Exception:
            pass
        return None

    @staticmethod
    def _find_open_document_by_path(catia, path):
        want = RoughStockService._norm_fs_path(path)
        if not want:
            return None
        try:
            for i in range(1, catia.Documents.Count + 1):
                d = catia.Documents.Item(i)
                fn = RoughStockService._norm_fs_path(getattr(d, "FullName", "") or "")
                if fn == want:
                    return d
        except Exception:
            pass
        return None

    @staticmethod
    def _run_rough_stock_measurement(
        catia,
        target_obj,
        stay_open=False,
        scope_product=None,
        anchor_asm_doc=None,
        bom_specific_body=False,
    ):
        """Core path: resolve bodies, optional SPA-in-axis, then Creates rough stock + scrape."""
        logger.info("Rough Stock: resolving targets...")
        root_part, selection_targets = RoughStockService._resolve_targets_via_selection(
            catia, target_obj
        )
        logger.info(f"Rough Stock: resolved {len(selection_targets)} target(s)")

        if len(selection_targets) > 10:
            selection_targets = selection_targets[:10]

        # BOM picked a PartDesign body: axis/world SPA uses root_part axis and can match tool-scale stock, not that body.
        if not bom_specific_body:
            axis_dims = RoughStockService._try_spa_bbox_in_preferred_axis(
                catia, root_part, selection_targets
            )
            if axis_dims is not None:
                logger.info("Rough Stock: using axis-aligned SPA extents (preferred over unset dialog axis).")
                return axis_dims

            world_dims = RoughStockService._try_spa_axis_aligned_bbox_mm(
                catia, root_part, selection_targets
            )
            if world_dims is not None:
                logger.info("Rough Stock: using SPA world AABB (skips unreliable dialog Z for plates).")
                return world_dims
        else:
            logger.info(
                "Rough Stock: skipping SPA axis/world shortcuts (BOM body leaf — use dialog scrape)."
            )

        RoughStockService.start_dialog_monitor()
        hw = RoughStockService._find_window()
        if not hw:
            logger.info("Triggering command 'c:Creates rough stock'...")
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("CATIA")
            time.sleep(0.5)
            shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)

            for _ in range(10):
                time.sleep(0.5)
                hw = RoughStockService._find_window()
                if hw:
                    break

            if not hw:
                logger.info("Fallback: Triggering 'c:Rough Stock'...")
                shell.SendKeys("{ESC}{ESC}c:Rough Stock{ENTER}", 0)
                for _ in range(10):
                    time.sleep(0.5)
                    hw = RoughStockService._find_window()
                    if hw:
                        break

            if not hw:
                logger.warning("Rough Stock window did not appear.")
                return None, None, None

        dx_max, dy_max, dz_max = 0.0, 0.0, 0.0
        passes = 0
        pass_cap = max(MAX_RS_PASSES_PER_PART, len(selection_targets))

        logger.info(
            "Measuring %s body slot(s) (index policy=%s, no body-name Search).",
            len(selection_targets),
            _RS_BODY_MODE,
        )
        for slot_idx, target in enumerate(selection_targets, start=1):
            try:
                if not EXHAUSTIVE_RS_MEASUREMENT and passes >= pass_cap:
                    logger.info(
                        "Reached pass_cap=%s; stopping further Rough Stock passes for this part.",
                        pass_cap,
                    )
                    break

                try:
                    win32gui.ShowWindow(hw, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hw)
                    time.sleep(0.1)
                except Exception:
                    pass

                logger.info("Rough Stock: body slot %s/%s", slot_idx, len(selection_targets))
                ok = RoughStockService._apply_rough_stock_body_selection(
                    catia,
                    root_part,
                    scope_product,
                    anchor_asm_doc,
                    target,
                )
                if not ok:
                    logger.warning(
                        "Rough Stock: could not select body slot %s/%s; skipping.",
                        slot_idx,
                        len(selection_targets),
                    )
                    continue

                # BOM body: scrape "Select part … to offset" until it matches (dialog updates after selection; poll, don't block 4s once).
                if bom_specific_body:
                    label_ok = False
                    shown = ""
                    wait_cap = min(
                        _RS_PART_OFFSET_MAX_WAIT,
                        max(6.0, _SCRAPE_PRE_DELAY_SEC * 2.5),
                    )
                    for body_try in range(_RS_BODY_LABEL_MATCH_ATTEMPTS):
                        if body_try > 0:
                            RoughStockService._apply_rough_stock_body_selection(
                                catia,
                                root_part,
                                scope_product,
                                anchor_asm_doc,
                                target,
                            )
                            time.sleep(max(0.35, _SCRAPE_PRE_DELAY_SEC * 0.25))
                        deadline = time.time() + wait_cap
                        poll_n = 0
                        while time.time() < deadline:
                            shown = RoughStockService._scrape_part_body_to_offset_text(hw)
                            label_ok = RoughStockService._part_body_label_matches(
                                shown, root_part, target
                            )
                            poll_n += 1
                            if label_ok:
                                break
                            time.sleep(_RS_PART_OFFSET_POLL_SEC)
                        # region agent log
                        try:
                            agent_ndjson(
                                "H19",
                                "rough_stock._run_rough_stock_measurement:part_to_offset_verified",
                                "scraped select-part-to-offset line until match or timeout",
                                {
                                    "body_try": body_try,
                                    "poll_n": poll_n,
                                    "shown_tail": (shown or "")[-120:],
                                    "label_ok": label_ok,
                                    "root_part_name": getattr(root_part, "Name", None),
                                    "target_name": getattr(target, "Name", None),
                                },
                            )
                        except Exception:
                            pass
                        # endregion
                        if label_ok:
                            break
                        logger.warning(
                            "Rough Stock: Part-to-offset %r ≠ %s\\%s — re-select (%s/%s).",
                            shown,
                            getattr(root_part, "Name", "?"),
                            getattr(target, "Name", "?"),
                            body_try + 1,
                            _RS_BODY_LABEL_MATCH_ATTEMPTS,
                        )
                    if not label_ok:
                        logger.warning(
                            "Rough Stock: Part-to-offset line never matched; scraping dims anyway (verify BOM row)."
                        )
                else:
                    time.sleep(_SCRAPE_PRE_DELAY_SEC)

                logger.info("Rough Stock: scraping after slot %s/%s...", slot_idx, len(selection_targets))
                # Single scrape can read prior row's L/W/H while the dialog updates (BOM 203 matched 202 until settle).
                dx, dy, dz = RoughStockService._scrape_dims_until_settled(hw)
                logger.info(f"Rough Stock: dimensions settled successfully: DX/DY/DZ=[{dx}, {dy}, {dz}]")
                # region agent log
                try:
                    agent_ndjson(
                        "H17",
                        "rough_stock._run_rough_stock_measurement:after_settled_scrape",
                        "dims after body select",
                        {
                            "bom_specific_body": bool(bom_specific_body),
                            "root_part_name": getattr(root_part, "Name", None),
                            "target_name": getattr(target, "Name", None),
                            "dx": dx,
                            "dy": dy,
                            "dz": dz,
                        },
                    )
                except Exception:
                    pass
                # endregion

                if dx and dx > dx_max:
                    dx_max = dx
                if dy and dy > dy_max:
                    dy_max = dy
                if dz and dz > dz_max:
                    dz_max = dz

                passes += 1

                if (
                    not EXHAUSTIVE_RS_MEASUREMENT
                    and passes >= pass_cap
                    and (dx_max + dy_max + dz_max) > 0.1
                ):
                    logger.info(
                        "Collected non-zero Rough Stock dimensions within pass limit; "
                        "short-circuiting remaining targets."
                    )
                    break

            except Exception as e:
                logger.error(f"Error measuring target: {e}")

        if not stay_open and hw:
            try:
                logger.info("Rough Stock: attempting to close dialog...")
                win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
                logger.info("Rough Stock: close message posted successfully.")
            except Exception as ex:
                logger.warning(f"Rough Stock: dialog close failed: {ex}")

        return (
            dx_max if dx_max > 0.001 else None,
            dy_max if dy_max > 0.001 else None,
            dz_max if dz_max > 0.001 else None,
        )

    @staticmethod
    def _meas_target_for_isolated_part(iso_part, source_target):
        """Map assembly BOM Body (or Part) to the matching body inside an opened CATPart copy."""
        if source_target is None or iso_part is None:
            return iso_part
        try:
            if getattr(source_target, "ReferenceProduct", None) is not None:
                return iso_part
            sn = (getattr(source_target, "Name", None) or "").strip()
            pn = (getattr(iso_part, "Name", None) or "").strip()
            if sn and pn and sn == pn:
                return iso_part
            if not sn:
                return iso_part
            bodies = getattr(iso_part, "Bodies", None)
            if bodies is None or bodies.Count < 1:
                return iso_part
            for i in range(1, bodies.Count + 1):
                b = bodies.Item(i)
                if (getattr(b, "Name", "") or "").strip() == sn:
                    return b
        except Exception:
            pass
        return iso_part

    @staticmethod
    def _measure_in_isolated_catpart_window(
        catia,
        target_obj,
        path,
        stay_open=False,
        scope_product=None,
        anchor_asm_doc=None,
        bom_specific_body=False,
    ):
        """Same isolation as STL: temp copy + Open so CATIA always uses a fresh document window."""
        prev_doc = None
        we_opened = False
        iso_doc = None
        temp_file_copy = ""
        try:
            try:
                prev_doc = catia.ActiveDocument
            except Exception:
                pass

            try:
                temp_dir = str(os.environ.get("TEMP", "C:\\Temp"))
                os.makedirs(temp_dir, exist_ok=True)
                ts = int(time.time() * 1000)
                temp_file_copy = os.path.join(temp_dir, f"cadm_rs_{ts}.CATPart")
                shutil.copy2(path, temp_file_copy)
                logger.info(f"Rough Stock: opening temp CATPart (STL-style isolation): {temp_file_copy}")
                iso_doc = catia.Documents.Open(temp_file_copy)
                we_opened = True
            except Exception as copy_err:
                logger.warning(
                    f"Rough Stock: temp copy/open failed ({copy_err}); trying direct Open."
                )
                temp_file_copy = ""
                iso_doc = RoughStockService._find_open_document_by_path(catia, path)
                if iso_doc is None:
                    iso_doc = catia.Documents.Open(path)
                    we_opened = True
                else:
                    logger.info("Rough Stock: reusing already-open CATPart.")

            try:
                catia.ActiveDocument = iso_doc
            except Exception:
                pass
            time.sleep(0.35)

            meas_leaf = RoughStockService._meas_target_for_isolated_part(
                iso_doc.Part, target_obj
            )
            res = RoughStockService._run_rough_stock_measurement(
                catia,
                meas_leaf,
                stay_open,
                scope_product=None,
                anchor_asm_doc=None,
                bom_specific_body=bom_specific_body,
            )

            if res == (None, None, None):
                logger.warning(
                    "Rough Stock: isolated document produced no dimensions; falling back to original window."
                )
                if we_opened and iso_doc is not None:
                    try:
                        iso_doc.Close(False)
                    except Exception:
                        pass
                    we_opened = False
                    iso_doc = None
                if prev_doc is not None:
                    try:
                        catia.ActiveDocument = prev_doc
                    except Exception:
                        pass
                prev_skip = prev_doc
                prev_doc = None
                res = RoughStockService._run_rough_stock_measurement(
                    catia,
                    target_obj,
                    stay_open,
                    scope_product=scope_product,
                    anchor_asm_doc=anchor_asm_doc,
                    bom_specific_body=bom_specific_body,
                )
                prev_doc = prev_skip

            return res
        except Exception as e:
            logger.warning(f"Rough Stock isolated-window path failed: {e}; falling back to in-place.")
            return RoughStockService._run_rough_stock_measurement(
                catia,
                target_obj,
                stay_open,
                scope_product=scope_product,
                anchor_asm_doc=anchor_asm_doc,
                bom_specific_body=bom_specific_body,
            )
        finally:
            # region agent log
            try:
                agent_ndjson(
                    "H12",
                    "rough_stock._measure_in_isolated_catpart_window:finally",
                    "isolated RS cleanup",
                    {"stay_open": bool(stay_open), "will_close_dialog": not bool(stay_open)},
                )
            except Exception:
                pass
            # endregion
            if not stay_open:
                RoughStockService.close_window()
            if we_opened and not stay_open and iso_doc is not None:
                try:
                    iso_doc.Close(False)
                except Exception as e:
                    logger.warning(f"Rough Stock: could not close isolated document: {e}")
            if temp_file_copy and os.path.isfile(temp_file_copy):
                try:
                    os.remove(temp_file_copy)
                except Exception:
                    pass
            if prev_doc is not None:
                try:
                    catia.ActiveDocument = prev_doc
                except Exception:
                    pass

    @staticmethod
    def get_rough_stock_dims(
        catia=None,
        target_obj=None,
        stay_open=False,
        isolate_part_window=None,
        scope_product=None,
        bom_specific_body=False,
    ):
        """
        DX, DY, DZ from Rough Stock (and SPA-in-axis shortcut when applicable).

        Body solids: default scans Bodies.Item(1), Item(2), … and uses the first with geometry
        (Shapes/HybridShapes). Override via CADMATION_RS_BODY_RESOLUTION. Set CADMATION_ROUGH_STOCK_IN_PLACE=1
        to skip isolated CATPart open/close when that path is enabled.
        """
        try:
            if not catia:
                from app.services.catia_bridge import catia_bridge
                catia = catia_bridge.catia_bridge.get_application()

            anchor_asm_doc = None
            if scope_product is not None:
                try:
                    anchor_asm_doc = catia.ActiveDocument
                except Exception:
                    pass

            if isolate_part_window is None:
                isolate_part_window = not _IN_PLACE_ROUGH_STOCK

            path = None
            if isolate_part_window and target_obj is not None:
                path = RoughStockService._resolve_catpart_path_from_target(target_obj)

            if isolate_part_window and path and os.path.isfile(path):
                return RoughStockService._measure_in_isolated_catpart_window(
                    catia,
                    target_obj,
                    path,
                    stay_open,
                    scope_product=scope_product,
                    anchor_asm_doc=anchor_asm_doc,
                    bom_specific_body=bom_specific_body,
                )

            if isolate_part_window and (not path or not os.path.isfile(path or "")):
                logger.info(
                    "Rough Stock: no on-disk CATPart path (or file missing); measuring in current window."
                )
            return RoughStockService._run_rough_stock_measurement(
                catia,
                target_obj,
                stay_open,
                scope_product=scope_product,
                anchor_asm_doc=anchor_asm_doc,
                bom_specific_body=bom_specific_body,
            )
        except Exception as e:
            logger.error(f"Rough Stock process failed: {e}")
            return None, None, None

    @staticmethod
    def _resolve_targets_via_selection(catia, target_obj, max_targets=10):
        """
        Resolve root Part, then pick body via sequential Item(1), Item(2), … first non-empty (default).
        """
        selection_targets = []
        root_part = None

        if target_obj is None:
            logger.warning("No target_obj provided to _resolve_targets_via_selection; falling back to ActiveDocument.Part.")
        target_name = "Unknown"
        try:
            target_name = target_obj.Name
        except Exception:
            pass

        try:
            doc = catia.ActiveDocument
            sel = doc.Selection
        except Exception as e:
            logger.error(f"Unable to access ActiveDocument.Selection: {e}")
            return None, [target_obj] if target_obj is not None else []

        logger.info(f"Rough Stock _resolve_targets: input={target_name}")

        # Body under Part: CATIA often has Body.Parent = Bodies collection, not Part — walk up to Part.Bodies.
        try:
            if getattr(target_obj, "Bodies", None) is None and getattr(
                target_obj, "ReferenceProduct", None
            ) is None:
                tn = (getattr(target_obj, "Name", "") or "").strip()
                if tn:
                    seen = set()
                    cur = target_obj
                    for _ in range(40):
                        if cur is None or id(cur) in seen:
                            break
                        seen.add(id(cur))
                        par = getattr(cur, "Parent", None)
                        if par is None:
                            break
                        try:
                            bc = getattr(par, "Bodies", None)
                            if bc is not None and bc.Count > 0:
                                for i in range(1, bc.Count + 1):
                                    try:
                                        b = bc.Item(i)
                                        if (getattr(b, "Name", "") or "").strip() == tn:
                                            logger.info(
                                                "Rough Stock: using caller Body %r under Part %r (parent walk).",
                                                tn,
                                                getattr(par, "Name", "?"),
                                            )
                                            # region agent log
                                            try:
                                                agent_ndjson(
                                                    "H13",
                                                    "rough_stock._resolve_targets_via_selection:body_under_part",
                                                    "matched body after parent walk",
                                                    {
                                                        "body_name": tn,
                                                        "part_name": getattr(par, "Name", None),
                                                    },
                                                )
                                            except Exception:
                                                pass
                                            # endregion
                                            return par, [target_obj]
                                    except Exception:
                                        continue
                                slots = RoughStockService._bodies_for_rough_stock(par)
                                if slots:
                                    logger.info(
                                        "Rough Stock: Part %r after walk; %s slot(s) by index (name match miss).",
                                        getattr(par, "Name", "?"),
                                        len(slots),
                                    )
                                    return par, slots[:max_targets]
                        except Exception:
                            pass
                        cur = par
        except Exception:
            pass

        # Try to add the object to the selection, but do not depend on this working.
        sel.Clear()
        if target_obj is not None:
            try:
                sel.Add(target_obj)
            except Exception:
                logger.info(f"Selection.Add failed for input '{target_name}', continuing with search-only resolution.")

        # 1. If target is already a Part (has Bodies), use it.
        try:
            _ = target_obj.Bodies  # noqa: B018 - COM attribute probe
            root_part = target_obj
            logger.info("Target appears to be a Part (Bodies attribute accessible).")
        except Exception:
            pass

        # 2. If target is a Product, resolve to its Part via ReferenceProduct first (per-instance Part).
        if root_part is None and target_obj is not None:
            try:
                ref = getattr(target_obj, "ReferenceProduct", None)
                if ref:
                    part_doc = getattr(ref, "Parent", None)
                    if part_doc and getattr(part_doc, "Part", None):
                        root_part = part_doc.Part
                        logger.info(
                            f"Resolved Part via ReferenceProduct.Parent.Part: {getattr(root_part, 'Name', 'Unknown')}"
                        )
            except Exception as e:
                logger.debug(f"ReferenceProduct resolution failed: {e}")

        # 3. If still no part, try name-based search (avoid Type=Part,all so we don't pick first Part in doc).
        if root_part is None and target_name != "Unknown":
            try:
                sel.Clear()
                pattern = f"Name='{target_name}',Type=Part,all"
                logger.info(f"Part resolution search pattern: {pattern}")
                sel.Search(pattern)
                if sel.Count > 0:
                    root_part = sel.Item(1).Value
                    logger.info(f"Part resolution search returned {sel.Count} result(s).")
            except Exception as e:
                logger.error(f"Selection-based part resolution failed: {e}")

        # 4. Last resort: ActiveDocument.Part only when no specific target or ReferenceProduct/name failed.
        if root_part is None:
            try:
                root_part = catia.ActiveDocument.Part
                logger.warning(
                    f"Using ActiveDocument.Part (may be wrong in assembly): {getattr(root_part, 'Name', 'Unknown')}"
                )
            except Exception:
                logger.warning("Failed to resolve root Part via ActiveDocument.Part.")

        if root_part is not None:
            try:
                bodies = root_part.Bodies
                if bodies is not None and bodies.Count > 0:
                    slots = RoughStockService._bodies_for_rough_stock(root_part)
                    if slots:
                        logger.info(
                            "Rough Stock: %s body slot(s) on Part (mode=%s).",
                            len(slots),
                            _RS_BODY_MODE,
                        )
                        return root_part, slots[:max_targets]
                logger.warning("Rough Stock: Part has no Bodies.")
            except Exception as e:
                logger.error(f"Rough Stock: failed to read Part.Bodies: {e}")

        if not selection_targets:
            logger.info("Falling back to literal target object for rough stock measurement.")
            if target_obj is not None:
                selection_targets = [target_obj]
            else:
                selection_targets = []

        if len(selection_targets) > max_targets:
            selection_targets = selection_targets[:max_targets]
            logger.info(f"Clamped selection_targets to {max_targets} items.")

        return root_part, selection_targets

    @staticmethod
    def open_rough_stock_dialog(catia=None):
        """Phase 1: Just triggers the command and waits for the window."""
        try:
            if not catia:
                from app.services.catia_bridge import catia_bridge
                catia = catia_bridge.catia_bridge.get_application()
            
            hw = RoughStockService._find_window()
            if not hw:
                logger.info("Rough Stock dialog not detected. Waiting for user to open it manually (interactive mode)...")
                # Removed SendKeys to satisfy 'disable opening new windows' request.
                # Use a smaller loop just in case the user opens it while we check.
                for _ in range(5):
                    time.sleep(1)
                    hw = RoughStockService._find_window()
                    if hw: break
            
            if hw:
                win32gui.SetForegroundWindow(hw)
                return hw
            return None
        except Exception as e:
            logger.error(f"Failed to open Rough Stock dialog: {e}")
            return None

    @staticmethod
    def _norm_rs_body_label(s):
        if not s:
            return ""
        t = s.strip().replace("/", "\\")
        while "\\\\" in t:
            t = t.replace("\\\\", "\\")
        return " ".join(t.upper().split())

    @staticmethod
    def _expected_part_body_labels(root_part, target_body):
        part_nm = (getattr(root_part, "Name", "") or "").strip()
        body_nm = (getattr(target_body, "Name", "") or "").strip()
        raw = []
        if part_nm and body_nm:
            raw.append(f"{part_nm}\\{body_nm}")
            raw.append(f"{part_nm.replace(' ', '_')}\\{body_nm}")
        elif body_nm:
            raw.append(body_nm)
        return [RoughStockService._norm_rs_body_label(x) for x in raw if x]

    @staticmethod
    def _part_body_truncated_garbage(shown):
        """LB_GETTEXT sometimes returns '20' or 'LO'; never treat as a real path."""
        s = (shown or "").strip()
        if not s or s == "EdtPartBody":
            return False
        return len(s) <= 4 and "\\" not in s and "/" not in s

    @staticmethod
    def _part_body_label_matches(shown, root_part, target_body):
        if RoughStockService._part_body_truncated_garbage(shown):
            return True
        if not shown or (shown.strip() == "EdtPartBody"):
            return False
        exp = RoughStockService._expected_part_body_labels(root_part, target_body)
        if not exp:
            return True
        norm = RoughStockService._norm_rs_body_label(shown)
        if norm in exp:
            return True
        for e in exp:
            if e and (norm.endswith(e) or e.endswith(norm)):
                return True
        body_u = RoughStockService._norm_rs_body_label(getattr(target_body, "Name", "") or "")
        return bool(body_u and body_u in norm and "\\" in norm)

    @staticmethod
    def _wm_gettext_upto(hwnd, max_chars=2048):
        try:
            text = RoughStockService._safe_get_text(hwnd, max_chars=max_chars, timeout_ms=5000)
            if text:
                return text
        except Exception:
            pass
        try:
            return (win32gui.GetWindowText(hwnd) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _enum_rough_stock_dialog_children(hw):
        out = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            cls = win32gui.GetClassName(hwnd)
            st = ""
            if cls == "Static":
                st = (
                    RoughStockService._wm_gettext_upto(hwnd, 512)
                    or win32gui.GetWindowText(hwnd)
                    or ""
                ).strip()
            out.append((hwnd, cls, st))
            return True

        try:
            win32gui.EnumChildWindows(hw, cb, None)
        except Exception:
            pass
        return out

    @staticmethod
    def _pick_best_part_path_lines(candidates):
        cands = [c.strip() for c in candidates if c and str(c).strip() not in ("EdtPartBody", "")]
        if not cands:
            return ""
        path_like = [c for c in cands if "\\" in c or "/" in c or "BODY" in c.upper()]
        pool = path_like if path_like else cands
        return max(pool, key=len)

    @staticmethod
    def _read_listbox_part_path(hwnd):
        import ctypes
        import ctypes.wintypes

        LB_GETCOUNT = 0x018B
        LB_GETTEXT = 0x0189
        LB_GETTEXTLEN = 0x019A
        LB_GETCURSEL = 0x0188
        SMTO_ABORTIFHUNG = 0x0002
        _TIMEOUT_MS = 3000

        def _lb_err(v):
            return v in (-1, 0xFFFFFFFF)

        def _send_timeout(h, msg, wp, lp):
            """SendMessageTimeout wrapper that returns 0 on timeout instead of hanging."""
            result = ctypes.wintypes.DWORD(0)
            ret = ctypes.windll.user32.SendMessageTimeoutW(
                h, msg, wp, lp, SMTO_ABORTIFHUNG, _TIMEOUT_MS, ctypes.byref(result)
            )
            if ret == 0:
                return -1  # treat timeout as error
            return result.value

        def listbox_all_lines(h):
            out = []
            try:
                cnt = _send_timeout(h, LB_GETCOUNT, 0, 0)
                if _lb_err(cnt) or cnt <= 0:
                    return out
                for i in range(int(cnt)):
                    ln = _send_timeout(h, LB_GETTEXTLEN, i, 0)
                    if _lb_err(ln) or ln > 4096:
                        continue
                    buf = ctypes.create_unicode_buffer(ln + 1)
                    _send_timeout(h, LB_GETTEXT, i, buf)
                    t = (buf.value or "").strip()
                    if t:
                        out.append(t)
            except Exception:
                pass
            return out

        def listbox_cur_line(h):
            try:
                sel_i = _send_timeout(h, LB_GETCURSEL, 0, 0)
                if _lb_err(sel_i):
                    sel_i = 0
                cnt = _send_timeout(h, LB_GETCOUNT, 0, 0)
                if _lb_err(cnt) or cnt <= 0 or sel_i >= cnt:
                    return ""
                ln = _send_timeout(h, LB_GETTEXTLEN, sel_i, 0)
                if _lb_err(ln):
                    return ""
                buf = ctypes.create_unicode_buffer(max(ln + 1, 512))
                _send_timeout(h, LB_GETTEXT, sel_i, buf)
                return (buf.value or "").strip()
            except Exception:
                return ""

        try:
            big = RoughStockService._wm_gettext_upto(hwnd, 2048)
            if big and big != "EdtPartBody" and ("\\" in big or "/" in big):
                return big.strip()
            merged = listbox_all_lines(hwnd)
            s = (
                RoughStockService._pick_best_part_path_lines(merged)
                or listbox_cur_line(hwnd)
                or big
            )
            if s and s != "EdtPartBody" and ("\\" in s or "/" in s or "BODY" in s.upper()):
                return s
        except Exception:
            pass
        return ""

    @staticmethod
    def _read_combobox_part_path(hwnd):
        import ctypes
        import ctypes.wintypes
        CB_GETCURSEL = 0x0147
        CB_GETLBTEXT = 0x0148
        CB_GETLBTEXTLEN = 0x0149
        SMTO_ABORTIFHUNG = 0x0002
        _TIMEOUT_MS = 3000

        def _lb_err(v):
            return v in (-1, 0xFFFFFFFF)

        def _send_timeout(h, msg, wp, lp):
            result = ctypes.wintypes.DWORD(0)
            ret = ctypes.windll.user32.SendMessageTimeoutW(
                h, msg, wp, lp, SMTO_ABORTIFHUNG, _TIMEOUT_MS, ctypes.byref(result)
            )
            if ret == 0:
                return -1
            return result.value

        try:
            sel_i = _send_timeout(hwnd, CB_GETCURSEL, 0, 0)
            if _lb_err(sel_i):
                sel_i = 0
            ln = _send_timeout(hwnd, CB_GETLBTEXTLEN, sel_i, 0)
            if _lb_err(ln):
                return ""
            buf = ctypes.create_unicode_buffer(max(ln + 1, 512))
            _send_timeout(hwnd, CB_GETLBTEXT, sel_i, buf)
            s = (buf.value or "").strip()
            if s:
                return s
            return (RoughStockService._wm_gettext_upto(hwnd, 2048) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _scrape_select_part_to_offset_row(hw):
        """Prefer the ListBox/ComboBox next to the Static that mentions part/body and offset (CATIA Rough Stock)."""
        rows = RoughStockService._enum_rough_stock_dialog_children(hw)
        for i, (hwnd, cls, st) in enumerate(rows):
            if cls != "Static":
                continue
            tl = (st or "").lower()
            if "offset" not in tl:
                continue
            if "part" not in tl and "body" not in tl:
                continue
            for j in range(i + 1, len(rows)):
                chwnd, ccls, _ = rows[j]
                if ccls == "ListBox":
                    p = RoughStockService._read_listbox_part_path(chwnd)
                    if p:
                        return p
                elif ccls == "ComboBox":
                    p = RoughStockService._read_combobox_part_path(chwnd)
                    if p and ("\\" in p or "/" in p or "BODY" in p.upper()):
                        return p
        return ""

    @staticmethod
    def _scrape_part_body_to_offset_text(hw):
        """Part\\body path for the \"Select part … to offset\" row; then heuristic scan of the dialog."""
        import ctypes

        s_row = RoughStockService._scrape_select_part_to_offset_row(hw)
        if s_row:
            return s_row

        LB_GETCOUNT = 0x018B
        LB_GETTEXT = 0x0189
        LB_GETTEXTLEN = 0x019A
        LB_GETCURSEL = 0x0188
        CB_GETCURSEL = 0x0147
        CB_GETLBTEXT = 0x0148
        CB_GETLBTEXTLEN = 0x0149

        def _lb_err(v):
            return v in (-1, 0xFFFFFFFF)

        def listbox_all_lines(hwnd):
            out = []
            try:
                cnt = win32gui.SendMessage(hwnd, LB_GETCOUNT, 0, 0)
                if _lb_err(cnt) or cnt <= 0:
                    return out
                for i in range(int(cnt)):
                    ln = win32gui.SendMessage(hwnd, LB_GETTEXTLEN, i, 0)
                    if _lb_err(ln) or ln > 4096:
                        continue
                    buf = ctypes.create_unicode_buffer(ln + 1)
                    win32gui.SendMessage(hwnd, LB_GETTEXT, i, buf)
                    t = (buf.value or "").strip()
                    if t:
                        out.append(t)
            except Exception:
                pass
            return out

        def listbox_cur_line(hwnd):
            try:
                sel_i = win32gui.SendMessage(hwnd, LB_GETCURSEL, 0, 0)
                if _lb_err(sel_i):
                    sel_i = 0
                cnt = win32gui.SendMessage(hwnd, LB_GETCOUNT, 0, 0)
                if _lb_err(cnt) or cnt <= 0 or sel_i >= cnt:
                    return ""
                ln = win32gui.SendMessage(hwnd, LB_GETTEXTLEN, sel_i, 0)
                if _lb_err(ln):
                    return ""
                buf = ctypes.create_unicode_buffer(max(ln + 1, 512))
                win32gui.SendMessage(hwnd, LB_GETTEXT, sel_i, buf)
                return (buf.value or "").strip()
            except Exception:
                return ""

        def combobox_line(hwnd):
            try:
                sel_i = win32gui.SendMessage(hwnd, CB_GETCURSEL, 0, 0)
                if _lb_err(sel_i):
                    sel_i = 0
                ln = win32gui.SendMessage(hwnd, CB_GETLBTEXTLEN, sel_i, 0)
                if _lb_err(ln):
                    return ""
                buf = ctypes.create_unicode_buffer(max(ln + 1, 512))
                win32gui.SendMessage(hwnd, CB_GETLBTEXT, sel_i, buf)
                return (buf.value or "").strip()
            except Exception:
                return ""

        def pick_best(candidates):
            return RoughStockService._pick_best_part_path_lines(candidates)

        best = ""
        controls = []

        def callback(hwnd, results):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            results.append((hwnd, win32gui.GetClassName(hwnd)))
            return True

        try:
            win32gui.EnumChildWindows(hw, callback, controls)
        except Exception:
            return ""

        for hwnd, cls in controls:
            if cls == "Static":
                st = RoughStockService._wm_gettext_upto(hwnd, 1024)
                if st and ("\\" in st or "/" in st) and len(st) > 6:
                    return st.strip()

        for hwnd, cls in controls:
            if cls == "ListBox":
                big = RoughStockService._wm_gettext_upto(hwnd, 2048)
                if big and big != "EdtPartBody" and ("\\" in big or "/" in big):
                    return big.strip()
                merged = listbox_all_lines(hwnd)
                s = pick_best(merged) or listbox_cur_line(hwnd) or big
                if s and s != "EdtPartBody" and ("\\" in s or "/" in s or "BODY" in s.upper()):
                    return s
                if s and s != "EdtPartBody" and len(s) > len(best):
                    best = s
            elif cls == "ComboBox":
                s = combobox_line(hwnd) or RoughStockService._wm_gettext_upto(hwnd, 2048)
                if s and ("\\" in s or "/" in s or "BODY" in s.upper()):
                    return s
                if len(s) > len(best):
                    best = s
        return best

    @staticmethod
    def measure_body_in_dialog(
        catia,
        target_obj,
        hw,
        scope_product=None,
        anchor_asm_doc=None,
        skip_axis_spa_shortcuts=False,
    ):
        """Phase 2: Selects the target body in the active dialog and scrapes dimensions."""
        import pythoncom
        pythoncom.CoInitialize()
        try:
            # 1. Resolve window handles
            if not hw or not win32gui.IsWindow(hw):
                hw = RoughStockService._find_window() or hw
            if not hw or not win32gui.IsWindow(hw):
                return None, None, None

            # 2. Resolve internal CATIA target bodies
            root_part, selection_targets = RoughStockService._resolve_targets_via_selection(
                catia, target_obj
            )
            if not selection_targets:
                return None, None, None
            target = selection_targets[0]

            # 3. Final window restoration check
            try:
                win32gui.ShowWindow(hw, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hw)
                time.sleep(0.1)
            except Exception:
                pass

            # 4. Perform the "Rough Stock" body selection
            if not RoughStockService._apply_rough_stock_body_selection(
                catia, root_part, scope_product, anchor_asm_doc, target
            ):
                return None, None, None

            # 5. SURVIVAL CHECK: Is window still alive after heavy COM call?
            if not win32gui.IsWindow(hw):
                return None, None, None

            # 6. Optimized SPA shortcut (if requested)
            if not skip_axis_spa_shortcuts:
                axis_dims = RoughStockService._try_spa_bbox_in_preferred_axis(catia, root_part, selection_targets)
                if axis_dims is not None: return axis_dims
                world_dims = RoughStockService._try_spa_axis_aligned_bbox_mm(catia, root_part, selection_targets)
                if world_dims is not None: return world_dims

            # 7. Match retry loop
            for body_try in range(_RS_BODY_LABEL_MATCH_ATTEMPTS):
                if not win32gui.IsWindow(hw): break
                if body_try > 0:
                    RoughStockService._apply_rough_stock_body_selection(
                        catia, root_part, scope_product, anchor_asm_doc, target
                    )
                time.sleep(_SCRAPE_PRE_DELAY_SEC)
                shown = RoughStockService._scrape_part_body_to_offset_text(hw)
                if RoughStockService._part_body_label_matches(shown, root_part, target):
                    break

            # 8. Final Scrape
            if not win32gui.IsWindow(hw):
                return None, None, None
            return RoughStockService._scrape_dims_until_settled(hw)

        except Exception as e:
            logger.error(f"Armor measurement failed: {e}")
            return None, None, None
        finally:
            # 9. Guaranteed Cleanup
            try:
                if hw and win32gui.IsWindow(hw):
                    RoughStockService._close_rough_stock_dialog(catia, hw)
            except Exception:
                pass
            pythoncom.CoUninitialize()

    @staticmethod
    def _dx_dy_dz_from_edit_window_positions(edit_hw_text):
        """
        Stock grid is 3×3 (min/max/delta per axis). Child enum order is not row-major — use (top,left).
        """
        if len(edit_hw_text) < 9:
            return None
        scored = []
        for h, txt in edit_hw_text:
            try:
                left, top, _r, _b = win32gui.GetWindowRect(h)
                scored.append((top, left, txt))
            except Exception:
                continue
        if len(scored) < 9:
            return None
        scored.sort(key=lambda x: (x[0], x[1]))
        span = max(s[0] for s in scored) - min(s[0] for s in scored)
        y_tol = max(22, min(45, int(span / 4) + 10)) if span > 0 else 28
        rows = []
        cur = []
        row_anchor = None
        for top, l, txt in scored:
            if row_anchor is None or abs(top - row_anchor) <= y_tol:
                cur.append((l, top, txt))
                row_anchor = top if row_anchor is None else (row_anchor + top) / 2.0
            else:
                cur.sort(key=lambda x: x[0])
                rows.append(cur)
                cur = [(l, top, txt)]
                row_anchor = top
        if cur:
            cur.sort(key=lambda x: x[0])
            rows.append(cur)
        if len(rows) < 3:
            return None
        # Three stock bands ordered by vertical position; take the lowest three (X/Y/Z block).
        rows.sort(key=lambda r: sum(c[1] for c in r) / max(len(r), 1))
        use = rows[-3:]
        texts = []
        for row in use:
            if len(row) < 3:
                return None
            row = sorted(row, key=lambda x: x[0])
            if len(row) > 3:
                row = row[-3:]
            texts.append([c[2] for c in row])
        try:
            dx = RoughStockService._parse_mm(texts[0][2])
            dy = RoughStockService._parse_mm(texts[1][2])
            dz = RoughStockService._parse_mm(texts[2][2])
        except Exception:
            return None
        if dx is None or dy is None or dz is None:
            return None
        return float(dx), float(dy), float(dz)

    @staticmethod
    def _safe_get_text(hwnd, max_chars=2048, timeout_ms=5000):
        """Read window text using SendMessageTimeout to prevent deadlocks."""
        import ctypes
        import ctypes.wintypes
        SMTO_ABORTIFHUNG = 0x0002
        WM_GETTEXTLENGTH = 0x000E
        WM_GETTEXT = 0x000D
        result = ctypes.wintypes.DWORD(0)
        try:
            # Get text length with timeout
            ret = ctypes.windll.user32.SendMessageTimeoutW(
                hwnd, WM_GETTEXTLENGTH, 0, 0,
                SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result)
            )
            if ret == 0:
                # Timed out or window hung
                return ""
            length = result.value
            if length <= 0:
                return ""
            length = min(length, max_chars)
            buf = ctypes.create_unicode_buffer(length + 1)
            result2 = ctypes.wintypes.DWORD(0)
            ret2 = ctypes.windll.user32.SendMessageTimeoutW(
                hwnd, WM_GETTEXT, length + 1, buf,
                SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result2)
            )
            if ret2 == 0:
                return ""
            return (buf.value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _scrape_current_window_dims(hw, read_passes=5, log_controls=True):
        """Helper to scrape the Edit controls of an open Rough Stock window."""
        import ctypes
        try:
            win32gui.ShowWindow(hw, win32con.SW_RESTORE)
            win32gui.ShowWindow(hw, win32con.SW_SHOW)
            time.sleep(0.1)
        except: pass

        read_passes = max(1, int(read_passes or 1))
        for attempt in range(read_passes):
            controls = []
            def callback(hwnd, results):
                if not win32gui.IsWindowVisible(hwnd): return True
                cls = win32gui.GetClassName(hwnd)
                try:
                    text = RoughStockService._safe_get_text(hwnd, timeout_ms=5000)
                except:
                    text = ""
                results.append((hwnd, cls, text))
                return True

            try:
                win32gui.EnumChildWindows(hw, callback, controls)
            except Exception as e:
                logger.warning(f"Rough Stock: EnumChildWindows failed: {e}")
                continue
            if log_controls:
                # Silenced to prevent flooding.
                pass
            edits_hw = [(h, t) for h, c, t in controls if c == "Edit"]
            edits = [t for _h, t in edits_hw]

            if edits and log_controls:
                # Silenced RAW Edits list to prevent flooding.
                pass
                
            if len(edits) >= 9:
                all_vals = [RoughStockService._parse_mm(e) for e in edits]
                if log_controls:
                    logger.info(f"Rough Stock Edits Parsed: {all_vals}")

                spatial = RoughStockService._dx_dy_dz_from_edit_window_positions(edits_hw)
                if spatial is not None and sum(spatial) > 0.1:
                    if log_controls:
                        logger.info(
                            "Captured dimensions from 3x3 edit layout (screen order): %s",
                            list(spatial),
                        )
                    return spatial[0], spatial[1], spatial[2]

                # Legacy: enum order (often wrong on newer CATIA layouts)
                vals = [all_vals[2], all_vals[5], all_vals[8]]
                vals = [v if v is not None else 0.0 for v in vals]
                
                if sum(vals) > 0.1:
                    if log_controls:
                        logger.info(f"Captured dimensions from indices 2,5,8: {vals}")
                    return vals[0], vals[1], vals[2]
                
                non_zero = sorted([v for v in all_vals if v is not None and v > 0.001], reverse=True)
                if len(non_zero) >= 3:
                    if log_controls:
                        logger.info(f"Captured dimensions from max sorted edits: {non_zero[:3]}")
                    return non_zero[0], non_zero[1], non_zero[2]

            time.sleep(0.4)
        return None, None, None

    @staticmethod
    def _scrape_dims_until_settled(hw):
        """Repeat dimension scrape until two consecutive reads match (Z often lags X/Y).
        Hard 60-second global deadline prevents infinite hang if CATIA dialog is unresponsive."""
        _HARD_DEADLINE_SEC = 60.0
        deadline = time.time() + _HARD_DEADLINE_SEC
        last = None
        chosen = None
        for i in range(_RS_DIM_SETTLE_ATTEMPTS):
            if time.time() > deadline:
                logger.warning(
                    "Rough Stock: hit hard %ss deadline in settlement loop; returning best available dims.",
                    _HARD_DEADLINE_SEC,
                )
                break
            if i > 0:
                time.sleep(_RS_DIM_SETTLE_PAUSE_SEC)
            quiet = i > 0
            try:
                cur = RoughStockService._scrape_current_window_dims(
                    hw, read_passes=1 if quiet else 5, log_controls=not quiet
                )
            except Exception as e:
                logger.warning(f"Rough Stock: scrape attempt {i} raised exception: {e}")
                continue
            if cur is None or cur[0] is None:
                continue
            if last is not None:
                deltas = (
                    abs(cur[0] - last[0]),
                    abs(cur[1] - last[1]),
                    abs(cur[2] - last[2]),
                )
                if max(deltas) < 0.05:
                    logger.info(
                        "Rough Stock: dimensions settled after %s read(s): DX/DY/DZ=%s",
                        i + 1,
                        list(cur),
                    )
                    return cur
            last = cur
            chosen = cur
        if chosen is not None:
            logger.info(
                "Rough Stock: dimensions did not fully settle; using last read DX/DY/DZ=%s",
                list(chosen),
            )
        return chosen if chosen is not None else (None, None, None)

    @staticmethod
    def close_window():
        """Forcefully finds and closes the Rough Stock window."""
        hw = RoughStockService._find_window()
        if hw:
            win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
            logger.info("Rough Stock window closed.")

    @staticmethod
    def _parse_mm(text):
        if not text: return None
        try:
            # CLEANING: Remove all whitespace and nulls which are common in MFC UTF-16 strings
            # This turns "1 4 5 . 0 m m" into "145.0mm"
            clean_text = "".join(text.split()).replace("\x00", "")
            
            # Prefer signed number as one token (old pattern let \d+ match after '-' and drop the sign).
            match = re.search(r"([-+]?(?:\d+\.\d+|\d+))", clean_text)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

