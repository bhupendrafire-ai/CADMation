import logging
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
from app.services.catia_bridge import catia_bridge
from app.services.tree_extractor import tree_extractor

logger = logging.getLogger(__name__)

# STD part name keywords for classification
STD_KEYWORDS = ("MISUMI", "FIBRO", "DIN", "ISO", "STANDARD", "PUNCH", "PILLAR")


class BOMService:
    def _log_op(self, msg: str):
        """Logs an operation with timestamp to a dedicated file."""
        output_dir = r"H:\CADMation\BOM_Outputs"
        os.makedirs(output_dir, exist_ok=True)
        log_file = os.path.join(output_dir, "operations.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}\n"
        try:
            with open(log_file, "a") as f:
                f.write(line)
        except: pass
        logger.info(f"BOM_OP: {msg}")

    def get_bom_items(self) -> List[Dict[str, Any]]:
        """Returns a flat list of BOM items from the active CATIA tree for the editor."""
        self._log_op("Starting full BOM scan (properties included)...")
        tree = tree_extractor.get_full_tree(include_props=True, check_visibility=True)
        if not tree or "error" in tree:
            return []

        items = []
        self._collect_items(tree, items)
        return items

    def get_bom_fast_list(self) -> List[Dict[str, Any]]:
        """Returns a fast list of and parts/components from the tree, grouped by Part Number."""
        self._log_op("Starting fast BOM scan (selectable list)...")
        tree = tree_extractor.get_full_tree(include_props=False, check_visibility=True)
        if not tree or "error" in tree:
            return []
            
        # Grouped by Part Number (Reference Name)
        grouped_items = {}
        self._collect_fast_items(tree, grouped_items)
        
        # Convert to list for frontend
        return list(grouped_items.values())

    def _collect_fast_items(self, node: Dict[str, Any], out: Dict[str, Dict[str, Any]]):
        """Builds a lightweight grouped list for selection."""
        name = node.get("name", "")
        node_type = node.get("type")
        # Use formal partNumber if available, else heuristic
        part_number = node.get("partNumber", name.split(".")[0]).strip()
        
        if node_type in ("Part", "Component"):
            if part_number in out:
                out[part_number]["qty"] += 1
                if name not in out[part_number]["instances"]:
                    out[part_number]["instances"].append(name)
            else:
                out[part_number] = {
                    "id": part_number,
                    "name": part_number,
                    "instanceName": name, # Representative name
                    "type": node_type,
                    "qty": 1,
                    "selected": True,
                    "instances": [name]
                }
            
        for child in node.get("children", []):
            self._collect_fast_items(child, out)

    def _collect_items(self, node: Dict[str, Any], out: List[Dict[str, Any]]):
        """Flattens tree into a single list; includes components even with default props."""
        name = node.get("name", "")
        node_type = node.get("type")
        props = node.get("properties") or {}

        if node_type in ("Part", "Component"):
            # Extract Part Number and Instance Name
            instance_name = name
            part_number = node.get("partNumber", name.split(".")[0]).strip()
            
            is_std = any(x in name.upper() for x in STD_KEYWORDS)
            item = {
                "id": len(out) + 1,
                "name": name,
                "partNumber": part_number,
                "instanceName": instance_name,
                "material": props.get("material", "STEEL"),
                "size": props.get("stock_size", "Not Measurable"),
                "heatTreatment": props.get("heat_treatment", "NONE"),
                "qty": 1,
                "isStd": is_std,
                "manufacturer": "MISUMI" if is_std else "",
            }
            out.append(item)

        for child in node.get("children", []):
            self._collect_items(child, out)

    def generate_excel_bom(self, edited_items: List[Dict[str, Any]] | None = None) -> str | None:
        """
        Generates Excel BOM: from edited_items if provided, else from current CATIA tree.
        Returns the absolute path to the generated file.
        """
        if edited_items is not None:
            return self._write_excel_from_edited(edited_items)

        logger.info("BOMService: Starting Excel BOM generation from tree...")
        tree = tree_extractor.get_full_tree(include_props=True)
        if not tree or "error" in tree:
            logger.error(f"BOMService: Failed to get tree data: {tree.get('error')}")
            return None

        mfg_items = []
        std_items = []
        self._process_node(tree, mfg_items, std_items)
        return self._write_excel(mfg_items, std_items, tree.get("name", "BOM"))

    def save_excel_bom(self, items: List[Dict[str, Any]]) -> str | None:
        """Saves BOM from designer-edited items (selected only); uses RM Size when provided."""
        return self._write_excel_from_edited(items)

    def _write_excel_from_edited(self, items: List[Dict[str, Any]]) -> str | None:
        """Builds MFG/STD lists from edited items (selected only) and writes Excel."""
        selected = [i for i in items if i.get("selected", True)]
        if not selected:
            logger.warning("BOMService: No items selected for export.")
            return None

        mfg_items = []
        std_items = []
        for idx, row in enumerate(selected, start=100):
            base = {
                "ITEM NO.": idx,
                "INSTANCE NAME": row.get("instanceName", row.get("name", "")),
                "PART NUMBER": row.get("partNumber", row.get("name", "").split(".")[0]),
                "QTY": int(row.get("qty", 1)),
            }
            if row.get("isStd"):
                base["MANUFACTURER"] = row.get("manufacturer", "MISUMI")
                std_items.append(base)
            else:
                base["MATERIAL"] = row.get("material", "STEEL")
                base["SIZE"] = row.get("rmSize", row.get("size", "Not Measurable"))
                base["HEAT TREATMENT"] = row.get("heatTreatment", "NONE")
                mfg_items.append(base)

        project_name = "BOM"
        return self._write_excel(mfg_items, std_items, project_name)

    def _write_excel(
        self,
        mfg_items: List[Dict[str, Any]],
        std_items: List[Dict[str, Any]],
        project_name: str,
    ) -> str | None:
        """Writes professionally formatted MFG and STD sheets to Excel."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        mfg_cols = ["ITEM NO.", "INSTANCE NAME", "PART NUMBER", "MATERIAL", "SIZE", "HEAT TREATMENT", "QTY"]
        std_cols = ["ITEM NO.", "INSTANCE NAME", "PART NUMBER", "MANUFACTURER", "QTY"]

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        name_base = project_name.split(".")[0]
        filename = f"{name_base}_BOM_{timestamp}.xlsx"
        output_dir = r"H:\CADMation\BOM_Outputs"
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        # ── Style definitions ──
        thin_border = Border(
            left=Side(style="thin", color="B0B0B0"),
            right=Side(style="thin", color="B0B0B0"),
            top=Side(style="thin", color="B0B0B0"),
            bottom=Side(style="thin", color="B0B0B0"),
        )
        # Title row: large, bold, dark background
        title_font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
        title_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        title_align = Alignment(horizontal="center", vertical="center")

        # Column header row: medium bold, slightly lighter blue
        header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
        header_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Data rows
        data_font = Font(name="Calibri", size=10)
        data_align_left = Alignment(horizontal="left", vertical="center")
        data_align_center = Alignment(horizontal="center", vertical="center")
        # Alternating row stripe (very light blue-gray)
        stripe_fill = PatternFill(start_color="EDF2F9", end_color="EDF2F9", fill_type="solid")
        # Columns that should be center-aligned
        center_cols_mfg = {"ITEM NO.", "QTY"}
        center_cols_std = {"ITEM NO.", "QTY"}

        try:
            wb = Workbook()
            # Remove default sheet
            wb.remove(wb.active)

            for sheet_label, columns, items in [
                ("MFG ITEM", mfg_cols, mfg_items),
                ("STD ITEM", std_cols, std_items),
            ]:
                ws = wb.create_sheet(title=sheet_label)
                num_cols = len(columns)
                center_set = center_cols_mfg if sheet_label == "MFG ITEM" else center_cols_std

                # ── Row 1: Title row (merged across all columns) ──
                ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
                title_cell = ws.cell(row=1, column=1, value=f"{name_base}  —  {sheet_label}")
                title_cell.font = title_font
                title_cell.fill = title_fill
                title_cell.alignment = title_align
                ws.row_dimensions[1].height = 32

                # ── Row 2: Column headers ──
                for col_idx, col_name in enumerate(columns, start=1):
                    cell = ws.cell(row=2, column=col_idx, value=col_name)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_align
                    cell.border = thin_border
                ws.row_dimensions[2].height = 24

                # ── Data rows ──
                for row_idx, item in enumerate(items, start=3):
                    is_striped = (row_idx - 3) % 2 == 1
                    for col_idx, col_name in enumerate(columns, start=1):
                        value = item.get(col_name, "")
                        cell = ws.cell(row=row_idx, column=col_idx, value=value)
                        cell.font = data_font
                        cell.border = thin_border
                        cell.alignment = data_align_center if col_name in center_set else data_align_left
                        if is_striped:
                            cell.fill = stripe_fill
                    ws.row_dimensions[row_idx].height = 20

                # ── Auto-fit column widths ──
                for col_idx in range(1, num_cols + 1):
                    col_letter = get_column_letter(col_idx)
                    # Measure header + all data values
                    max_len = len(columns[col_idx - 1])
                    for row in ws.iter_rows(min_row=3, min_col=col_idx, max_col=col_idx):
                        for cell in row:
                            if cell.value:
                                max_len = max(max_len, len(str(cell.value)))
                    ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

                # Freeze panes below the header row
                ws.freeze_panes = "A3"

            wb.save(file_path)
            self._log_op(f"BOM exported successfully to: {file_path}")
            logger.info(f"BOMService: Professional BOM written to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"BOMService: Failed to write Excel: {e}")
            return None

    def _process_node(self, node: Dict[str, Any], mfg: List[Dict], std: List[Dict]):
        """Recursively flattens the tree into MFG and STD lists."""
        name = node.get("name", "")
        props = node.get("properties") or {}

        if node.get("type") in ["Part", "Component"]:
            instance_name = name
            part_number = node.get("partNumber", name.split(".")[0]).strip()
            
            item_data = {
                "ITEM NO.": len(mfg) + len(std) + 100,
                "INSTANCE NAME": instance_name,
                "PART NUMBER": part_number,
                "QTY": 1,
            }
            is_std = any(x in name.upper() for x in STD_KEYWORDS)
            if is_std:
                item_data["MANUFACTURER"] = "MISUMI"
                std.append(item_data)
            else:
                item_data["MATERIAL"] = props.get("material", "STEEL")
                item_data["SIZE"] = props.get("stock_size", "Not Measurable")
                item_data["HEAT TREATMENT"] = props.get("heat_treatment", "NONE")
                mfg.append(item_data)

        for child in node.get("children", []):
            self._process_node(child, mfg, std)

# Singleton
bom_service = BOMService()
