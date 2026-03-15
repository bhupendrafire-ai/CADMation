import logging
from typing import Any, Dict, List
import win32com.client
from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

logger = logging.getLogger(__name__)

class TreeExtractor:
    def get_full_tree(self, include_props=False, check_visibility=False) -> Dict[str, Any] | None:
        """EntryPoint: Extracts the active document's tree."""
        logger.info(f"TreeExtractor: Starting full tree extraction (visibility={check_visibility})...")
        caa = catia_bridge.get_application()
        if not caa:
            return None
        
        try:
            doc = caa.ActiveDocument
            display_name = catia_bridge.get_active_document_name() or doc.Name
            
            # Use property existence for robust type detection
            is_product = False
            try:
                doc.Product
                is_product = True
            except: pass
            
            is_part = False
            try:
                doc.Part
                is_part = True
            except: pass

            if is_part:
                part = doc.Part
                props = self._get_part_properties(part) if include_props else {}
                return {
                    "name": display_name, "type": "Part", "properties": props,
                    "children": self._parse_part(part, doc, check_visibility=check_visibility)
                }
            elif is_product:
                product = doc.Product
                return {
                    "name": display_name, "type": "Product",
                    "children": self._parse_product(product, doc, include_props=include_props, check_visibility=check_visibility)
                }
            else:
                return {"name": display_name, "type": "Document", "children": []}
        except Exception as e:
            logger.error(f"TreeExtractor: Failed: {e}")
            return {"error": str(e)}

    def _get_part_properties(self, part) -> Dict[str, Any]:
        """Extracts properties for a CATPart."""
        props = {}
        try:
            bbox_data = geometry_service.get_bounding_box(part)
            props["stock_size"] = bbox_data.get("stock_size", "Not Measurable")
            props["material"] = "STEEL"
            props["heat_treatment"] = "NONE"
            
            # Param check
            try:
                for param in part.Parameters:
                    n = param.Name.upper()
                    if "MATERIAL" in n: props["material"] = param.ValueAsString()
                    elif "TREATMENT" in n: props["heat_treatment"] = param.ValueAsString()
            except: pass
        except:
            props["stock_size"] = "Not Measurable"
        return props

    def _get_product_properties(self, product) -> Dict[str, Any]:
        """Extracts properties for a sub-assembly."""
        props = {}
        try:
            bbox_data = geometry_service.get_product_bounding_box(product)
            props["stock_size"] = bbox_data.get("stock_size", "Not Measurable")
            props["material"] = "N/A"
            props["heat_treatment"] = "N/A"
        except:
            props["stock_size"] = "Not Measurable"
        return props

    def _is_hidden(self, sel, obj) -> bool:
        """Check if a CATIA object is in No-Show mode.
        GetShow() returns a tuple (status, value) where value 1 = hidden."""
        try:
            sel.Clear()
            sel.Add(obj)
            result = sel.VisProperties.GetShow()
            # Unpack tuple: (0, 1) means hidden, (0, 0) means visible
            if isinstance(result, tuple):
                return result[1] == 1
            return result == 1
        except:
            return False  # If we can't check, assume visible

    def _parse_part(self, part, doc, check_visibility=False) -> List[Dict[str, Any]]:
        bodies = []
        try:
            sel = doc.Selection
            for b in part.Bodies:
                if check_visibility and self._is_hidden(sel, b):
                    continue
                bodies.append({"name": b.Name, "type": "Body"})
        except:
            return [{"name": b.Name, "type": "Body"} for b in part.Bodies]
        return bodies

    def _parse_product(self, product, doc, depth=0, max_depth=15, include_props=False, check_visibility=False) -> List[Dict[str, Any]]:
        """Recursive traversal with higher item limit for large assemblies."""
        if depth > max_depth: return []
        
        children = []
        try:
            com_prod = product.com_object if hasattr(product, "com_object") else product
            count = com_prod.Products.Count
            
            sel = doc.Selection
            
            # Increase limit for large dies
            max_p = 1000 
            for i in range(1, min(count, max_p) + 1):
                child = com_prod.Products.Item(i)
                
                # Visibility check (Only if requested - this is slow/invasive)
                if check_visibility and self._is_hidden(sel, child):
                    continue

                item_props = {}
                
                # Recursive children
                sub = self._parse_product(child, doc, depth + 1, max_depth, include_props, check_visibility)
                
                try:
                    ref_doc = child.ReferenceProduct.Parent
                    is_p = bool(hasattr(ref_doc, "Part") or ".CATPART" in getattr(ref_doc, "Name", "").upper())
                    
                    if is_p:
                        if include_props: item_props = self._get_part_properties(ref_doc.Part)
                        sub.extend(self._parse_part(ref_doc.Part, doc, check_visibility))
                    else:
                        if include_props: item_props = self._get_product_properties(child)
                except:
                    item_props = {"stock_size": "Not Measurable"}

                # Part Number (Reference Name) resolution
                try: 
                    pn = child.PartNumber.strip()
                    if not pn:
                         # Try to get from filename if property is empty
                         try: pn = child.ReferenceProduct.Parent.Name.split(".")[0].strip()
                         except: pn = ""
                except: 
                    try: pn = child.ReferenceProduct.Parent.Name.split(".")[0].strip()
                    except: pn = child.Name.split(".")[0].strip()

                if not pn:
                     pn = child.Name.split(".")[0].strip()

                children.append({
                    "name": child.Name,
                    "partNumber": pn,
                    "type": "Component",
                    "properties": item_props,
                    "children": sub
                })
        except: pass
        return children

tree_extractor = TreeExtractor()
