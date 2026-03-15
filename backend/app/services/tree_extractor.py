import logging
from typing import Any, Dict, List
import win32com.client
from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

logger = logging.getLogger(__name__)

class TreeExtractor:
    def get_full_tree(self, include_props=False) -> Dict[str, Any] | None:
        """EntryPoint: Extracts the active document's tree."""
        logger.info("TreeExtractor: Starting full tree extraction...")
        caa = catia_bridge.get_application()
        if not caa:
            logger.warning("TreeExtractor: No CATIA application found.")
            return None
        
        try:
            doc = caa.ActiveDocument
            name = doc.Name
            logger.info(f"TreeExtractor: Active document is {name}")
            
            # Handle CATPart
            if name.lower().endswith(".catpart"):
                part = doc.Part
                logger.info("TreeExtractor: Parsing CATPart...")
                props = self._get_part_properties(part) if include_props else {}
                return {
                    "name": name,
                    "type": "Part",
                    "properties": props,
                    "children": self._parse_part(part)
                }
            # Handle CATProduct
            elif name.lower().endswith(".catproduct"):
                product = doc.Product
                logger.info("TreeExtractor: Parsing CATProduct...")
                return {
                    "name": name,
                    "type": "Product",
                    "children": self._parse_product(product, include_props=include_props)
                }
            else:
                logger.info(f"TreeExtractor: Unsupported document type for {name}")
                return {"name": name, "type": "Document", "children": []}
        except Exception as e:
            logger.error(f"TreeExtractor: Failed to get active document: {e}")
            return {"error": str(e)}

    def _get_part_properties(self, part) -> Dict[str, Any]:
        """Extracts mass, material, and bounding box for a CATPart."""
        props = {}
        try:
            # Mass in kg
            if hasattr(part.Parent, "Product"):
                product = part.Parent.Product
                props["mass"] = round(product.Analyze.Mass, 3)
                props["volume"] = round(product.Analyze.Volume, 6)
            else:
                props["mass"] = 0.0
                props["volume"] = 0.0
            
            # Use GeometryService for multi-body accurate bounding box
            bbox_data = geometry_service.get_bounding_box(part)
            
            x_size = bbox_data.get("x", 0.0)
            y_size = bbox_data.get("y", 0.0)
            z_size = bbox_data.get("z", 0.0)
            
            props["stock_size"] = f"{x_size} x {y_size} x {z_size}"
            props["dimensions"] = {"x": x_size, "y": y_size, "z": z_size}
            
            # Default material and heat treatment
            props["material"] = "STEEL"
            props["heat_treatment"] = "NONE"
            
            # Check for Custom Parameters (user-defined material/heat data)
            try:
                for param in part.Parameters:
                    name = param.Name.upper()
                    if "MATERIAL" in name:
                        props["material"] = param.ValueAsString()
                    elif "HEAT" in name or "TREATMENT" in name:
                        props["heat_treatment"] = param.ValueAsString()
            except: pass

            # Infer from part name if custom params not found
            part_name = part.Parent.Name.upper()
            if "STEEL" in part_name: props["material"] = "STEEL"
            if "HRC" in part_name: props["heat_treatment"] = "HARDENED"

        except Exception as e:
            logger.debug(f"TreeExtractor: Property extraction partially failed for {getattr(part, 'Name', 'Unknown')}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            props["stock_size"] = "Unknown"
        
        return props

    def _get_product_properties(self, product) -> Dict[str, Any]:
        """
        Extracts properties for a CATProduct (sub-assembly).
        Uses product-level bounding box that unions all children.
        """
        props = {}
        try:
            com_prod = product.com_object if hasattr(product, "com_object") else product

            # Mass: try to get from Analyze
            try:
                ref_prod = com_prod.ReferenceProduct if hasattr(com_prod, "ReferenceProduct") else com_prod
                props["mass"] = round(ref_prod.Analyze.Mass, 3)
            except:
                props["mass"] = 0.0

            # Bounding box: product-level (union of children)
            bbox_data = geometry_service.get_product_bounding_box(com_prod)

            x_size = bbox_data.get("x", 0.0)
            y_size = bbox_data.get("y", 0.0)
            z_size = bbox_data.get("z", 0.0)

            props["stock_size"] = f"{x_size} x {y_size} x {z_size}"
            props["dimensions"] = {"x": x_size, "y": y_size, "z": z_size}
            props["material"] = "STEEL"
            props["heat_treatment"] = "NONE"

        except Exception as e:
            logger.debug(f"TreeExtractor: Product property extraction failed: {e}")
            props["stock_size"] = "Unknown"
            props["material"] = "STEEL"
            props["heat_treatment"] = "NONE"

        return props

    def _parse_part(self, part, include_params=False) -> List[Dict[str, Any]]:
        com_part = part.com_object if hasattr(part, "com_object") else part
        children = []

        # 1. Parse Bodies
        bodies = []
        try:
            count = com_part.Bodies.Count
            for i in range(1, count + 1):
                b = com_part.Bodies.Item(i)
                bodies.append(self._parse_body(b))
            if bodies:
                children.append({"name": "Bodies", "type": "Folder", "children": bodies})
        except Exception as e:
            logger.debug(f"TreeExtractor: Body extraction failed: {e}")

        # 2. Geometric Sets
        gs = []
        try:
            count = com_part.HybridBodies.Count
            for i in range(1, count + 1):
                hb = com_part.HybridBodies.Item(i)
                gs.append(self._parse_hybrid_body(hb))
            if gs:
                children.append({"name": "Geometric Sets", "type": "Folder", "children": gs})
        except Exception as e:
            logger.debug(f"TreeExtractor: Geometric set extraction failed: {e}")

        return children

    def _parse_body(self, body) -> Dict[str, Any]:
        """Parses a Body and its features."""
        com_body = body.com_object if hasattr(body, "com_object") else body
        elements = []
        try:
            skc = com_body.Sketches.Count
            for i in range(1, min(skc, 10) + 1):
                sk = com_body.Sketches.Item(i)
                elements.append({"name": sk.Name, "type": "Sketch"})
        except: pass

        return {
            "name": com_body.Name,
            "type": "Body",
            "children": elements
        }

    def _parse_hybrid_body(self, hb) -> Dict[str, Any]:
        """Parses a HybridBody (Geometric Set)."""
        com_hb = hb.com_object if hasattr(hb, "com_object") else hb
        return {
            "name": com_hb.Name,
            "type": "GeometricSet",
            "children": [] 
        }

    def _parse_product(self, product, depth=0, max_depth=15, include_props=False) -> List[Dict[str, Any]]:
        """
        Traverses the Product structure recursively.
        Properly handles both CATPart and CATProduct children for BOM extraction.
        """
        if depth > max_depth:
            return []

        com_prod = product.com_object if hasattr(product, "com_object") else product
        children = []
        max_products = 200

        try:
            count = com_prod.Products.Count
            for i in range(1, min(count, max_products) + 1):
                child = com_prod.Products.Item(i)
                sub_children = self._parse_product(child, depth + 1, max_depth, include_props)
                item_props = {}

                try:
                    ref_doc = child.ReferenceProduct.Parent
                    is_part = bool(hasattr(ref_doc, "Part") or ".CATPART" in getattr(ref_doc, "Name", "").upper())

                    if is_part:
                        # CATPart child: measure the part directly (all bodies)
                        if include_props:
                            item_props = self._get_part_properties(ref_doc.Part)
                        part_content = self._parse_part(ref_doc.Part, include_params=False)
                        sub_children.extend(part_content)
                    else:
                        # CATProduct child (sub-assembly): use product-level measurement
                        if include_props:
                            item_props = self._get_product_properties(child)
                except Exception as e:
                    logger.debug(f"TreeExtractor: Failed to extract part data for {child.Name}: {e}")
                    if include_props:
                        item_props = {"stock_size": "Unknown", "material": "STEEL", "heat_treatment": "NONE"}

                children.append({
                    "name": child.Name,
                    "type": "Component",
                    "properties": item_props,
                    "children": sub_children,
                })
        except Exception:
            pass
        return children

# Singleton
tree_extractor = TreeExtractor()
