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
    def get_bom_items(self) -> List[Dict[str, Any]]:
        """Returns a flat list of BOM items from the active CATIA tree for the editor."""
        tree = tree_extractor.get_full_tree(include_props=True)
        if not tree or "error" in tree:
            return []

        items = []
        self._collect_items(tree, items)
        return items

    def _collect_items(self, node: Dict[str, Any], out: List[Dict[str, Any]]):
        """Flattens tree into a single list; includes components even with default props."""
        name = node.get("name", "")
        node_type = node.get("type")
        props = node.get("properties") or {}

        if node_type in ("Part", "Component"):
            desc = name.split(".")[0]
            is_std = any(x in name.upper() for x in STD_KEYWORDS)
            item = {
                "id": len(out) + 1,
                "name": name,
                "partNumber": desc,
                "description": desc,
                "material": props.get("material", "STEEL"),
                "size": props.get("stock_size", "Unknown"),
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
                "DESCRIPTION": row.get("description", row.get("partNumber", row.get("name", "").split(".")[0])),
                "PART NUMBER": row.get("partNumber", row.get("name", "").split(".")[0]),
                "QTY": int(row.get("qty", 1)),
            }
            if row.get("isStd"):
                base["MANUFACTURER"] = row.get("manufacturer", "MISUMI")
                std_items.append(base)
            else:
                base["MATERIAL"] = row.get("material", "STEEL")
                base["SIZE"] = row.get("rmSize", row.get("size", "Unknown"))
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
        """Writes MFG and STD DataFrames to Excel."""
        mfg_cols = ["ITEM NO.", "DESCRIPTION", "PART NUMBER", "MATERIAL", "SIZE", "HEAT TREATMENT", "QTY"]
        std_cols = ["ITEM NO.", "DESCRIPTION", "PART NUMBER", "MANUFACTURER", "QTY"]

        df_mfg = pd.DataFrame(mfg_items)
        df_std = pd.DataFrame(std_items)
        for col in mfg_cols:
            if col not in df_mfg.columns:
                df_mfg[col] = ""
        for col in std_cols:
            if col not in df_std.columns:
                df_std[col] = ""

        df_mfg = df_mfg[mfg_cols]
        df_std = df_std[std_cols]

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        name_base = project_name.split(".")[0]
        filename = f"{name_base}_BOM_{timestamp}.xlsx"
        output_dir = r"H:\CADMation\BOM_Outputs"
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        try:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                df_mfg.to_excel(writer, sheet_name="MFG ITEM", index=False)
                df_std.to_excel(writer, sheet_name="STD ITEM", index=False)
                for sheet in writer.sheets.values():
                    for col in sheet.columns:
                        max_length = max((len(str(cell.value or "")) for cell in col), default=0)
                        sheet.column_dimensions[col[0].column_letter].width = max_length + 2
            logger.info(f"BOMService: BOM written to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"BOMService: Failed to write Excel: {e}")
            return None

    def _process_node(self, node: Dict[str, Any], mfg: List[Dict], std: List[Dict]):
        """Recursively flattens the tree into MFG and STD lists."""
        name = node.get("name", "")
        props = node.get("properties") or {}

        if node.get("type") in ["Part", "Component"]:
            desc = name.split(".")[0]
            item_data = {
                "ITEM NO.": len(mfg) + len(std) + 100,
                "DESCRIPTION": desc,
                "PART NUMBER": desc,
                "QTY": 1,
            }
            is_std = any(x in name.upper() for x in STD_KEYWORDS)
            if is_std:
                item_data["MANUFACTURER"] = "MISUMI"
                std.append(item_data)
            else:
                item_data["MATERIAL"] = props.get("material", "STEEL")
                item_data["SIZE"] = props.get("stock_size", "Unknown")
                item_data["HEAT TREATMENT"] = props.get("heat_treatment", "NONE")
                mfg.append(item_data)

        for child in node.get("children", []):
            self._process_node(child, mfg, std)

# Singleton
bom_service = BOMService()
