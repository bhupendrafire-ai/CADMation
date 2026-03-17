import os
import sys
import tempfile
import unittest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import app.services.bom_service as bom_service_module
from app.services.bom_rules import canonicalize_row
from app.services.bom_schema import derive_rm_size
from workbook_compare import semantic_compare_rows, validate_workbook_structure


class BomPipelineTests(unittest.TestCase):
    def test_standard_part_normalization(self):
        row = canonicalize_row(
            {
                "partNumber": "900-MAIN_WEAR_PLATE",
                "instanceName": "MWF150-150.2",
                "size": "150 x 100 x 20",
                "methodUsed": "STL",
                "qty": 2,
            }
        )
        self.assertTrue(row["isStd"])
        self.assertEqual(row["catalogCode"], "MWF150-150")
        self.assertEqual(row["sheetCategory"], "STD")
        self.assertEqual(row["description"], "Wear Plate")

    def test_rm_size_derivation(self):
        rm_size = derive_rm_size("205 x 45 x 15", machining_stock=5, rounding_mm=5)
        self.assertEqual(rm_size, "210 x 50 x 20")

    def test_flagged_row_stays_in_selected_sheet(self):
        row = canonicalize_row(
            {
                "partNumber": "LOWER PAD STD PARTS",
                "instanceName": "LOWER PAD STD PARTS",
                "originType": "assembly_container",
                "sheetCategory": "Steel",
                "size": "980 x 650 x 205",
                "methodUsed": "SPA",
            }
        )
        self.assertEqual(row["sheetCategory"], "Steel")
        self.assertIn("assembly_container", row["validationFlags"])

    def test_explicit_casting_keeps_blank_material(self):
        row = canonicalize_row(
            {
                "partNumber": "CAST-HOUSING",
                "instanceName": "CAST-HOUSING.1",
                "sheetCategory": "Casting",
                "material": "",
                "size": "200 x 150 x 75",
                "methodUsed": "ROUGH_STOCK",
            }
        )
        self.assertEqual(row["sheetCategory"], "Casting")
        self.assertEqual(row["material"], "")

    def test_block_like_round_inference_is_forced_rectangular(self):
        row = canonicalize_row(
            {
                "partNumber": "LOWER_FLANGE_STEEL_01",
                "instanceName": "LOWER_FLANGE_STEEL_01.1",
                "description": "Lower Flange Steel",
                "size": "DIA 80 x 40",
                "rawDims": [80, 80, 40],
                "orderedDims": [80, 80, 40],
                "methodUsed": "ROUGH_STOCK",
            }
        )
        self.assertEqual(row["sizeKind"], "box")
        self.assertEqual(row["stockForm"], "rectangular")
        self.assertEqual(row["millingSize"], "80 x 80 x 40")

    def test_workbook_template_structure(self):
        rows = [
            canonicalize_row(
                {
                    "partNumber": "208_STOPPER_PLATE",
                    "instanceName": "208_STOPPER_PLATE.1",
                    "material": "MS",
                    "size": "205 x 45 x 15",
                    "machiningStock": 5,
                    "roundingMm": 5,
                    "methodUsed": "ROUGH_STOCK",
                    "qty": 2,
                }
            ),
            canonicalize_row(
                {
                    "partNumber": "900-MAIN_WEAR_PLATE",
                    "instanceName": "MWF150-150.2",
                    "size": "150 x 100 x 20",
                    "methodUsed": "STL",
                    "qty": 4,
                }
            ),
            canonicalize_row(
                {
                    "partNumber": "LOWER PAD STD PARTS",
                    "instanceName": "LOWER PAD STD PARTS",
                    "originType": "assembly_container",
                    "size": "980 x 650 x 205",
                    "methodUsed": "SPA",
                }
            ),
            canonicalize_row(
                {
                    "partNumber": "CAST-HOUSING",
                    "instanceName": "CAST-HOUSING.1",
                    "sheetCategory": "Casting",
                    "material": "FG260",
                    "size": "200 x 150 x 75",
                    "methodUsed": "ROUGH_STOCK",
                }
            ),
        ]
        metadata = {
            "title": "CADMation Production BOM",
            "date": "17/03/2026",
            "woNo": "TEST-WO",
            "customer": "Regression",
            "toolType": "PRESS TOOL",
            "toolSize": "1500",
            "projectName": "TEST_BOM",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            old_output_dir = bom_service_module.OUTPUT_DIR
            bom_service_module.OUTPUT_DIR = tmpdir
            try:
                file_path = bom_service_module.bom_service._write_excel(rows, metadata)
            finally:
                bom_service_module.OUTPUT_DIR = old_output_dir

            self.assertTrue(file_path and os.path.exists(file_path))
            errors = validate_workbook_structure(file_path)
            self.assertEqual(errors, [])

    def test_semantic_compare_detects_dimension_mismatch(self):
        reference_rows = [
            {"sheet": "Steel", "description": "Transportation Strap", "milling_dims": [200, 40, 10], "catalog": ""},
        ]
        candidate_rows = [
            {"sheet": "Steel", "description": "Transportation Strap", "part_number": "614-TRANSPORTAION STRAP", "milling_dims": [980, 650, 205], "catalog": ""},
        ]
        analysis = semantic_compare_rows(reference_rows, candidate_rows)
        self.assertEqual(len(analysis["dimension_mismatches"]), 1)
        self.assertEqual(len(analysis["extra_rows"]), 0)


if __name__ == "__main__":
    unittest.main()
