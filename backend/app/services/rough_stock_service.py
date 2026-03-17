import win32com.client
import win32gui
import win32con
import time
import re
import logging
import threading
import pythoncom

logger = logging.getLogger(__name__)

# Rough Stock iteration tuning (balanced defaults).
MAX_RS_PASSES_PER_PART = 2
EXHAUSTIVE_RS_MEASUREMENT = False
BODY_NAME_TOOL_PATTERNS = ("TOOL", "CUT", "DIE", "STAMP", "PUNCH")

# Global flag to control the monitor thread
_monitor_active = False
_monitor_thread = None

class RoughStockService:
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
    def get_rough_stock_dims(catia=None, target_obj=None, stay_open=False):
        """
        Extracts DX, DY, DZ from CATIA's 'Rough Stock' dialog.
        High-reliability version: Performs selection BEFORE triggering the command.
        """
        try:
            if not catia:
                from app.services.catia_bridge import catia_bridge
                catia = catia_bridge.catia_bridge.get_application()

            logger.info("Rough Stock: resolving targets...")
            # 1. Resolve target objects (Selection-first structural detection)
            root_part, selection_targets = RoughStockService._resolve_targets_via_selection(
                catia, target_obj
            )
            logger.info(f"Rough Stock: resolved {len(selection_targets)} target(s)")

            if len(selection_targets) > 10:
                selection_targets = selection_targets[:10]

            # 2. Trigger the command
            RoughStockService.start_dialog_monitor()
            hw = RoughStockService._find_window()
            if not hw:
                logger.info("Triggering command 'c:Creates rough stock'...")
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("CATIA")
                time.sleep(0.5)
                shell.SendKeys("{ESC}{ESC}c:Creates rough stock{ENTER}", 0)

                for i in range(10):
                    time.sleep(0.5)
                    hw = RoughStockService._find_window()
                    if hw: break
                
                if not hw:
                    logger.info("Fallback: Triggering 'c:Rough Stock'...")
                    shell.SendKeys("{ESC}{ESC}c:Rough Stock{ENTER}", 0)
                    for i in range(10):
                        time.sleep(0.5)
                        hw = RoughStockService._find_window()
                        if hw: break

                if not hw:
                    logger.warning("Rough Stock window did not appear.")
                    return None, None, None

            # 3. Iterate and Search Targets
            dx_max, dy_max, dz_max = 0.0, 0.0, 0.0
            passes = 0

            logger.info(f"Measuring {len(selection_targets)} targets via Search...")
            for target in selection_targets:
                try:
                    if not EXHAUSTIVE_RS_MEASUREMENT and passes >= MAX_RS_PASSES_PER_PART:
                        logger.info(
                            f"Reached MAX_RS_PASSES_PER_PART={MAX_RS_PASSES_PER_PART}; "
                            "stopping further Rough Stock passes for this part."
                        )
                        break

                    # Rule 4: Window Restore
                    try:
                        win32gui.ShowWindow(hw, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hw)
                        time.sleep(0.1)
                    except: pass

                    sel = catia.ActiveDocument.Selection
                    sel.Clear()
                    
                    target_name = getattr(target, 'Name', 'Unknown')

                    logger.info(f"Triggering Rough Stock via Search for: {target_name}")
                    # Prefer searching by both name and type to avoid hitting products,
                    # but always finish with a name-only pattern as a fallback.
                    search_patterns = []
                    if root_part is not None:
                        search_patterns.append(f"Name='{target_name}',Type=Body,all")
                        search_patterns.append(f"Name='{target_name}',Type=Part,all")
                    # Always include a loose, name-only pattern last as a safety net.
                    search_patterns.append(f"Name='{target_name}',all")

                    match_count = 0
                    for pattern in search_patterns:
                        try:
                            sel.Clear()
                            logger.info(f"Selection.Search pattern: {pattern}")
                            sel.Search(pattern)
                            match_count = sel.Count
                            logger.info(f"Selection.Search pattern '{pattern}' returned {match_count} result(s).")
                            if match_count > 0:
                                first_match = sel.Item(1).Value
                                sel.Clear()
                                sel.Add(first_match)
                                match_count = 1
                                break
                        except Exception as se:
                            logger.error(f"Selection.Search failed for pattern '{pattern}': {se}")

                    if match_count == 0:
                        logger.warning(f"No selection results for target '{target_name}'. Skipping measurement for this target.")
                        continue
                    
                    # Rule 3: Wait at least 2.0s
                    time.sleep(2.5) 
                    logger.info(f"Scraping dimensions for {target_name}...")
                    dx, dy, dz = RoughStockService._scrape_current_window_dims(hw)
                    logger.info(f"Scrape results: {dx} x {dy} x {dz}")

                    if dx and dx > dx_max:
                        dx_max = dx
                    if dy and dy > dy_max:
                        dy_max = dy
                    if dz and dz > dz_max:
                        dz_max = dz

                    passes += 1

                    # Early exit once we have a stable, non-trivial box in balanced mode.
                    if (
                        not EXHAUSTIVE_RS_MEASUREMENT
                        and passes >= MAX_RS_PASSES_PER_PART
                        and (dx_max + dy_max + dz_max) > 0.1
                    ):
                        logger.info(
                            "Collected non-zero Rough Stock dimensions within pass limit; "
                            "short-circuiting remaining targets."
                        )
                        break

                except Exception as e:
                    logger.error(f"Error measuring target: {e}")

            # 4. Finalize
            if not stay_open:
                try:
                    win32gui.PostMessage(hw, win32con.WM_CLOSE, 0, 0)
                except: pass

            return dx_max if dx_max > 0.001 else None, dy_max if dy_max > 0.001 else None, dz_max if dz_max > 0.001 else None
        except Exception as e:
            logger.error(f"Rough Stock process failed: {e}")
            return None, None, None

    @staticmethod
    def _resolve_targets_via_selection(catia, target_obj, max_targets=10):
        """Resolve a CATIA target into a root part and measurement targets using Selection.Search."""
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

        # 4. Resolve candidate bodies. Prefer anti-operand rule, but fall back to simpler heuristics and search.
        if root_part is not None:
            try:
                all_bodies = []
                body_names = set()
                try:
                    bodies = root_part.Bodies
                    for i in range(1, bodies.Count + 1):
                        b = bodies.Item(i)
                        all_bodies.append(b)
                        body_names.add(b.Name)
                except Exception as e:
                    logger.error(f"Failed to enumerate Bodies on root_part: {e}")

                consumed = set()
                if all_bodies:
                    for b in all_bodies:
                        try:
                            shapes = b.Shapes
                        except Exception:
                            continue
                        for j in range(1, getattr(shapes, "Count", 0) + 1):
                            try:
                                s = shapes.Item(j)
                            except Exception:
                                continue
                            for prop in ["Body", "Operand", "TargetBody", "FirstOperand", "SecondOperand"]:
                                try:
                                    op = getattr(s, prop)
                                    if getattr(op, "Name", None) in body_names:
                                        consumed.add(op.Name)
                                except Exception:
                                    continue

                for b in all_bodies:
                    name = getattr(b, "Name", "")
                    if name in consumed:
                        continue
                    # Skip obvious tool/operand bodies by name in balanced mode.
                    if not EXHAUSTIVE_RS_MEASUREMENT and any(
                        pat in name.upper() for pat in BODY_NAME_TOOL_PATTERNS
                    ):
                        continue
                    selection_targets.append(b)

                if selection_targets:
                    logger.info(
                        f"Anti-operand body resolution selected bodies: "
                        f"{[getattr(b, 'Name', 'Unknown') for b in selection_targets]}"
                    )
            except Exception as e:
                logger.error(f"Anti-operand body resolution failed: {e}")

            # Heuristic fallbacks if anti-operand did not yield anything.
            if not selection_targets:
                logger.info("Anti-operand rule produced no bodies; applying heuristic body selection.")
                # Try root_part.MainBody if available.
                try:
                    main_body = getattr(root_part, "MainBody", None)
                    if main_body is not None:
                        selection_targets.append(main_body)
                        logger.info(
                            f"Using MainBody as selection target: "
                            f"{getattr(main_body, 'Name', 'Unknown')}"
                        )
                except Exception:
                    pass

            if not selection_targets:
                # Fallback: first body, if any.
                try:
                    bodies = root_part.Bodies
                    if bodies.Count > 0:
                        b = bodies.Item(1)
                        selection_targets.append(b)
                        logger.info(
                            f"Using first body as selection target: "
                            f"{getattr(b, 'Name', 'Unknown')}"
                        )
                except Exception as e:
                    logger.error(f"Failed to select first body as fallback: {e}")

            if not selection_targets:
                logger.warning(
                    "No bodies selected from resolved Part; skipping document-wide body search to avoid clubbing multiple parts."
                )

        # 5. Narrow and de-duplicate targets in balanced mode.
        if selection_targets and not EXHAUSTIVE_RS_MEASUREMENT:
            part_name = getattr(root_part, "Name", "") if root_part is not None else ""
            primary = []
            secondary = []
            for b in selection_targets:
                name = getattr(b, "Name", "")
                if hasattr(root_part, "MainBody") and b is getattr(root_part, "MainBody", None):
                    primary.append(b)
                    continue
                if part_name and part_name.upper() in name.upper():
                    secondary.append(b)

            narrowed = primary or secondary
            if narrowed:
                logger.info(
                    "Balanced mode: narrowing selection_targets to primary bodies: "
                    f"{[getattr(b, 'Name', 'Unknown') for b in narrowed]}"
                )
                selection_targets = narrowed

            # De-duplicate by (part_name, body_name).
            seen = set()
            deduped = []
            for b in selection_targets:
                name = getattr(b, "Name", "")
                key = (part_name, name)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(b)
            if len(deduped) != len(selection_targets):
                logger.info(
                    f"De-duplicated selection_targets from {len(selection_targets)} to {len(deduped)}."
                )
            selection_targets = deduped

        # 6. As a last resort, use the literal input.
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
    def _scrape_current_window_dims(hw):
        """Helper to scrape the Edit controls of an open Rough Stock window."""
        import ctypes
        try:
            win32gui.ShowWindow(hw, win32con.SW_RESTORE)
            win32gui.ShowWindow(hw, win32con.SW_SHOW)
            time.sleep(0.1)
        except: pass

        for attempt in range(5):
            controls = []
            def callback(hwnd, results):
                if not win32gui.IsWindowVisible(hwnd): return True
                cls = win32gui.GetClassName(hwnd)
                try:
                    length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
                    text = buffer.value
                except:
                    text = ""
                results.append((hwnd, cls, text))
                return True

            win32gui.EnumChildWindows(hw, callback, controls)
            edits = [t for h, c, t in controls if c == "Edit"]
            
            if edits:
                # Log RAW results with repr to see hidden characters
                logger.info(f"Scrape Attempt {attempt}: RAW Edits: {[repr(e) for e in edits]}")
                
            if len(edits) >= 9:
                all_vals = [RoughStockService._parse_mm(e) for e in edits]
                logger.info(f"Rough Stock Edits Parsed: {all_vals}")
                
                # Check default indices 2, 5, 8 (DX, DY, DZ usually)
                vals = [all_vals[2], all_vals[5], all_vals[8]]
                vals = [v if v is not None else 0.0 for v in vals]
                
                if sum(vals) > 0.1:
                    logger.info(f"Captured dimensions from indices 2,5,8: {vals}")
                    return vals[0], vals[1], vals[2]
                
                # Fallback: check all for non-zero values
                non_zero = sorted([v for v in all_vals if v is not None and v > 0.001], reverse=True)
                if len(non_zero) >= 3:
                    logger.info(f"Captured dimensions from max sorted edits: {non_zero[:3]}")
                    return non_zero[0], non_zero[1], non_zero[2]

            time.sleep(0.4)
        return None, None, None

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
            
            match = re.search(r"([-+]?\d*\.\d+|\d+)", clean_text)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

