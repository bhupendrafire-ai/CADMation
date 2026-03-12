"""
tree_extractor.py — Parses the CATIA V5 specification tree into JSON.

Iterates through Part.Bodies, Sketches, and Parameters to create a
hierarchical representation of the model for LLM context injection.
"""

from typing import Any, Dict, List
from pycatia.mec_mod_interfaces.part import Part
from app.services.catia_bridge import catia_bridge

class TreeExtractor:
    def get_full_tree(self) -> Dict[str, Any] | None:
        """EntryPoint: Extracts the active document's tree."""
        caa = catia_bridge.get_application()
        if not caa:
            return None
        
        try:
            doc = caa.active_document
            # Handle CATPart
            if doc.name.endswith(".CATPart"):
                part = doc.part
                return {
                    "name": doc.name,
                    "type": "Part",
                    "children": self._parse_part(part)
                }
            # Handle CATProduct
            elif doc.name.endswith(".CATProduct"):
                product = doc.product
                return {
                    "name": doc.name,
                    "type": "Product",
                    "children": self._parse_product(product)
                }
            else:
                return {"name": doc.name, "type": "Document", "children": []}
        except Exception as e:
            return {"error": str(e)}

    def _parse_part(self, part: Part) -> List[Dict[str, Any]]:
        # Handle both pycatia Part and COM Part
        com_part = part.com_object if hasattr(part, "com_object") else part
        children = []

        # 1. Parse Parameters
        params = []
        try:
            for i in range(1, com_part.Parameters.Count + 1):
                p = com_part.Parameters.Item(i)
                params.append({"name": p.Name, "type": "Parameter", "value": str(p.Value)})
            if params:
                children.append({"name": "Parameters", "type": "Folder", "children": params})
        except: pass

        # 2. Parse Bodies
        bodies = []
        try:
            for i in range(1, com_part.Bodies.Count + 1):
                b = com_part.Bodies.Item(i)
                bodies.append(self._parse_body(b))
            if bodies:
                children.append({"name": "Bodies", "type": "Folder", "children": bodies})
        except: pass

        # 3. Parse Geometric Sets (HybridBodies)
        gs = []
        try:
            for i in range(1, com_part.HybridBodies.Count + 1):
                hb = com_part.HybridBodies.Item(i)
                gs.append(self._parse_hybrid_body(hb))
            if gs:
                children.append({"name": "Geometric Sets", "type": "Folder", "children": gs})
        except: pass

        return children

    def _parse_body(self, body) -> Dict[str, Any]:
        """Parses a Body and its features."""
        # Use COM for depth
        com_body = body.com_object if hasattr(body, "com_object") else body
        elements = []
        try:
            for i in range(1, com_body.Shapes.Count + 1):
                s = com_body.Shapes.Item(i)
                # Improve type labels
                t_name = type(s).__name__
                if t_name == "CDispatch":
                    t_name = "Shape"
                elements.append({"name": s.Name, "type": t_name})
            
            for i in range(1, com_body.Sketches.Count + 1):
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
        elements = []
        try:
            for i in range(1, com_hb.HybridBodies.Count + 1):
                elements.append(self._parse_hybrid_body(com_hb.HybridBodies.Item(i)))
            
            for i in range(1, com_hb.HybridShapes.Count + 1):
                hs = com_hb.HybridShapes.Item(i)
                elements.append({"name": hs.Name, "type": "HybridShape"})
        except: pass

        return {
            "name": com_hb.Name,
            "type": "GeometricSet",
            "children": elements
        }

    def _parse_product_parameters(self, product) -> List[Dict[str, Any]]:
        """Parses parameters at the Product/Assembly level."""
        params = []
        try:
            com_prod = product.com_object if hasattr(product, "com_object") else product
            for i in range(1, com_prod.Parameters.Count + 1):
                p = com_prod.Parameters.Item(i)
                params.append({"name": p.Name, "type": "Parameter", "value": str(p.Value)})
        except: pass
        return params

    def _parse_product(self, product) -> List[Dict[str, Any]]:
        """Traverses the Product structure recursively with Part bridge."""
        com_prod = product.com_object if hasattr(product, "com_object") else product
        children = []
        
        # 1. Parse Product-level Parameters
        prod_params = self._parse_product_parameters(product)
        if prod_params:
            children.append({"name": "Assembly Parameters", "type": "Folder", "children": prod_params})

        # 2. Parse Child Components/Products
        try:
            for i in range(1, com_prod.Products.Count + 1):
                child = com_prod.Products.Item(i)
                
                # Recursive children (Sub-products)
                sub_children = self._parse_product(child)
                
                # BRIDGE to internal Part if it exists
                try:
                    ref_doc = child.ReferenceProduct.Parent
                    if ".CATPart" in ref_doc.Name:
                        part_content = self._parse_part(ref_doc.Part)
                        sub_children.extend(part_content)
                except: pass

                children.append({
                    "name": child.Name,
                    "type": "Component",
                    "children": sub_children
                })
        except: pass
        return children

# Singleton
tree_extractor = TreeExtractor()
