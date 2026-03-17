import logging
from typing import Any, Dict, List
import win32com.client
from app.services.catia_bridge import catia_bridge
from app.services.geometry_service import geometry_service

logger = logging.getLogger(__name__)

class TreeExtractor:
    def _safe_attr(self, obj, attr: str, default=""):
        try:
            value = getattr(obj, attr, default)
            return value if value not in (None, "") else default
        except Exception:
            return default

    def _get_reference_doc_info(self, child) -> Dict[str, Any]:
        info = {
            "referenceKey": "",
            "sourceDocPath": "",
            "sourceDocumentName": "",
            "isPartDocument": False,
            "referenceDoc": None,
        }
        try:
            ref_doc = child.ReferenceProduct.Parent
            info["referenceDoc"] = ref_doc
            info["sourceDocumentName"] = self._safe_attr(ref_doc, "Name", "")
            info["sourceDocPath"] = self._safe_attr(ref_doc, "FullName", "")
            info["isPartDocument"] = bool(
                hasattr(ref_doc, "Part") or ".CATPART" in info["sourceDocumentName"].upper()
            )
            info["referenceKey"] = info["sourceDocPath"] or info["sourceDocumentName"]
        except Exception:
            pass
        return info

    def _extract_document_metadata(self, doc, display_name: str) -> Dict[str, Any]:
        metadata = {
            "projectName": display_name,
            "documentName": getattr(doc, "Name", display_name),
            "woNo": display_name,
            "customer": "",
            "toolType": "",
            "toolSize": "",
        }
        try:
            product = getattr(doc, "Product", None)
            if product is not None:
                metadata["projectName"] = getattr(product, "PartNumber", "") or display_name
                params = getattr(product, "Parameters", None)
                if params:
                    for param in params:
                        pname = getattr(param, "Name", "").upper()
                        getter = getattr(param, "ValueAsString", None)
                        value = getter() if callable(getter) else ""
                        if not value:
                            continue
                        if "CUSTOMER" in pname:
                            metadata["customer"] = value
                        elif "TOOL" in pname and "TYPE" in pname:
                            metadata["toolType"] = value
                        elif "TOOL" in pname and "SIZE" in pname:
                            metadata["toolSize"] = value
                        elif "WO" in pname:
                            metadata["woNo"] = value
        except Exception:
            pass
        return metadata

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
                    "metadata": self._extract_document_metadata(doc, display_name),
                    "children": self._parse_part(part, doc, check_visibility=check_visibility)
                }
            elif is_product:
                product = doc.Product
                return {
                    "name": display_name, "type": "Product",
                    "metadata": self._extract_document_metadata(doc, display_name),
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
            # Tree/export scans must avoid Rough Stock UI to stay deterministic.
            bbox_data = geometry_service.get_bounding_box(part, method="SPA")
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
        return {
            "stock_size": "Not Measurable",
            "material": "N/A",
            "heat_treatment": "N/A",
            "measurement_confidence": "low",
        }

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
                ref_info = self._get_reference_doc_info(child)
                is_leaf_part = ref_info["isPartDocument"]
                child_name = self._safe_attr(child, "Name", "")
                child_part_number = self._safe_attr(child, "PartNumber", "").strip()
                if not child_part_number:
                    child_part_number = (ref_info["sourceDocumentName"] or child_name).split(".")[0].strip()

                parent_name = self._safe_attr(product, "Name", "")
                sub = []

                if is_leaf_part and ref_info["referenceDoc"] is not None:
                    try:
                        part_obj = ref_info["referenceDoc"].Part
                        if include_props:
                            item_props = self._get_part_properties(part_obj)
                        sub = self._parse_part(part_obj, doc, check_visibility)
                    except Exception:
                        item_props = {"stock_size": "Not Measurable"}
                else:
                    if include_props:
                        item_props = self._get_product_properties(child)
                    sub = self._parse_product(child, doc, depth + 1, max_depth, include_props, check_visibility)

                # Part Number (Reference Name) resolution
                pn = child_part_number or child_name.split(".")[0].strip()

                node_type = "Component" if is_leaf_part else "Assembly"
                origin_type = "leaf_part" if is_leaf_part else "assembly_container"

                children.append({
                    "name": child_name,
                    "partNumber": pn,
                    "type": node_type,
                    "originType": origin_type,
                    "isLeaf": is_leaf_part,
                    "referenceKey": ref_info["referenceKey"] or f"{pn}|{child_name}",
                    "sourceDocPath": ref_info["sourceDocPath"],
                    "sourceDocumentName": ref_info["sourceDocumentName"],
                    "parentAssembly": parent_name,
                    "properties": item_props,
                    "children": sub
                })
        except: pass
        return children

tree_extractor = TreeExtractor()
