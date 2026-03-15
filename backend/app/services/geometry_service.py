import logging
import math
from typing import Dict, Any, List
from app.services.catia_bridge import catia_bridge

logger = logging.getLogger(__name__)

# CATIA SPA GetBoundaryBox returns meters; we report mm
MM_PER_M = 1000.0


class GeometryService:
    def get_bounding_box(self, part_or_product: Any) -> Dict[str, float]:
        """
        Computes AABB for a Part by unioning ALL bodies (not just MainBody).
        Falls back to OOBB then volume estimate.
        """
        caa = catia_bridge.get_application()
        if not caa:
            return self._get_fallback_bbox()

        try:
            part = part_or_product
            if hasattr(part_or_product, "Part"):
                part = part_or_product.Part

            doc = part.Parent
            while doc and not hasattr(doc, "GetWorkbench"):
                doc = getattr(doc, "Parent", None)

            if not doc:
                return self._get_fallback_bbox(part)

            spa_service = doc.GetWorkbench("SPAWorkbench")

            # Primary: union AABB across ALL bodies (MainBody + any extra bodies)
            union_aabb = self._get_union_aabb_all_bodies(spa_service, part)
            if union_aabb is not None:
                return union_aabb

            # Fallback: single MainBody AABB
            measurable = spa_service.GetMeasurable(part.MainBody)
            aabb = self._get_aabb_from_measurable(measurable)
            if aabb is not None:
                return aabb

            # Fallback: OOBB + volume-derived third dimension
            oobb = self._get_oobb_from_measurable(measurable, part)
            if oobb is not None:
                return oobb

        except Exception as e:
            logger.debug(f"GeometryService: bbox failed: {e}")

        return self._get_fallback_bbox(part)

    def get_product_bounding_box(self, product: Any) -> Dict[str, float]:
        """
        Computes AABB for an entire CATProduct (assembly) by unioning
        bounding boxes of all child products and parts.
        Uses Selection.Search to find all bodies, or falls back to
        recursively measuring each child component.
        """
        caa = catia_bridge.get_application()
        if not caa:
            return self._get_fallback_bbox()

        try:
            com_prod = product.com_object if hasattr(product, "com_object") else product

            # Strategy 1: Try to get the product's own document bbox via SPA
            try:
                ref_prod = com_prod.ReferenceProduct if hasattr(com_prod, "ReferenceProduct") else com_prod
                doc = ref_prod.Parent
                if hasattr(doc, "GetWorkbench"):
                    spa = doc.GetWorkbench("SPAWorkbench")
                    if hasattr(doc, "Part"):
                        # It's actually a CATPart wrapped in a product
                        union = self._get_union_aabb_all_bodies(spa, doc.Part)
                        if union is not None:
                            return union
            except Exception as e:
                logger.debug(f"GeometryService: Product SPA direct failed: {e}")

            # Strategy 2: Union of children bounding boxes
            return self._get_children_union_bbox(com_prod)

        except Exception as e:
            logger.debug(f"GeometryService: product bbox failed: {e}")

        return self._get_fallback_bbox()

    def _get_children_union_bbox(self, com_prod: Any) -> Dict[str, float]:
        """
        Recursively unions bounding boxes of all children in a CATProduct.
        Handles both CATPart children (direct measurement) and CATProduct
        children (recursive descent).
        """
        global_min = [float('inf')] * 3
        global_max = [float('-inf')] * 3
        found_any = False

        try:
            count = com_prod.Products.Count
            for i in range(1, count + 1):
                child = com_prod.Products.Item(i)
                child_bbox = None

                try:
                    ref_doc = child.ReferenceProduct.Parent
                    is_part = hasattr(ref_doc, "Part") or ".CATPART" in getattr(ref_doc, "Name", "").upper()

                    if is_part:
                        # Measure the actual part (all bodies)
                        child_bbox = self.get_bounding_box(ref_doc.Part)
                    else:
                        # Sub-assembly: recurse into it
                        child_bbox = self._get_children_union_bbox(child)
                except Exception as e:
                    logger.debug(f"GeometryService: child {i} measurement failed: {e}")
                    continue

                if child_bbox and child_bbox.get("x", 0) > 0.1:
                    found_any = True
                    # Use xmin/xmax if available, otherwise use 0-to-dimension
                    for axis_idx, axis in enumerate(["x", "y", "z"]):
                        axis_min = child_bbox.get(f"{axis}min", 0)
                        axis_max = child_bbox.get(f"{axis}max", child_bbox.get(axis, 0))
                        global_min[axis_idx] = min(global_min[axis_idx], axis_min)
                        global_max[axis_idx] = max(global_max[axis_idx], axis_max)
        except Exception as e:
            logger.debug(f"GeometryService: children union failed: {e}")

        if not found_any:
            return self._get_fallback_bbox()

        dx = round(global_max[0] - global_min[0], 2)
        dy = round(global_max[1] - global_min[1], 2)
        dz = round(global_max[2] - global_min[2], 2)

        return {
            "x": dx, "y": dy, "z": dz,
            "xmin": round(global_min[0], 2), "ymin": round(global_min[1], 2), "zmin": round(global_min[2], 2),
            "xmax": round(global_max[0], 2), "ymax": round(global_max[1], 2), "zmax": round(global_max[2], 2),
            "stock_size": f"{dx} x {dy} x {dz}",
        }

    def _get_union_aabb_all_bodies(self, spa_service: Any, part: Any) -> Dict[str, float] | None:
        """
        Unions the AABB of every body in the part (MainBody + extra bodies).
        This captures the full geometry, not just the MainBody.
        """
        global_min = [float('inf')] * 3
        global_max = [float('-inf')] * 3
        found_any = False

        try:
            com_part = part.com_object if hasattr(part, "com_object") else part
            body_count = com_part.Bodies.Count

            for i in range(1, body_count + 1):
                try:
                    body = com_part.Bodies.Item(i)
                    measurable = spa_service.GetMeasurable(body)
                    bbox = [0.0] * 6
                    res = measurable.GetBoundaryBox(bbox)
                    if isinstance(res, tuple):
                        bbox = list(res)

                    # Skip empty / zero-volume bodies
                    x_min, y_min, z_min = bbox[0], bbox[1], bbox[2]
                    x_max, y_max, z_max = bbox[3], bbox[4], bbox[5]
                    dx = abs(x_max - x_min)
                    dy = abs(y_max - y_min)
                    dz = abs(z_max - z_min)
                    if dx < 1e-9 and dy < 1e-9 and dz < 1e-9:
                        continue

                    found_any = True
                    global_min[0] = min(global_min[0], x_min)
                    global_min[1] = min(global_min[1], y_min)
                    global_min[2] = min(global_min[2], z_min)
                    global_max[0] = max(global_max[0], x_max)
                    global_max[1] = max(global_max[1], y_max)
                    global_max[2] = max(global_max[2], z_max)
                except Exception as be:
                    logger.debug(f"GeometryService: Body {i} AABB failed: {be}")
                    continue
        except Exception as e:
            logger.debug(f"GeometryService: multi-body iteration failed: {e}")

        if not found_any:
            return None

        dx = abs(global_max[0] - global_min[0]) * MM_PER_M
        dy = abs(global_max[1] - global_min[1]) * MM_PER_M
        dz = abs(global_max[2] - global_min[2]) * MM_PER_M

        if dx < 1e-6 and dy < 1e-6 and dz < 1e-6:
            return None

        return {
            "x": round(dx, 2), "y": round(dy, 2), "z": round(dz, 2),
            "xmin": round(global_min[0] * MM_PER_M, 2),
            "ymin": round(global_min[1] * MM_PER_M, 2),
            "zmin": round(global_min[2] * MM_PER_M, 2),
            "xmax": round(global_max[0] * MM_PER_M, 2),
            "ymax": round(global_max[1] * MM_PER_M, 2),
            "zmax": round(global_max[2] * MM_PER_M, 2),
            "stock_size": f"{round(dx, 2)} x {round(dy, 2)} x {round(dz, 2)}",
        }

    def _get_aabb_from_measurable(self, measurable: Any) -> Dict[str, float] | None:
        """Part-local AABB: x,y,z = extents in part axis order (meters -> mm)."""
        try:
            bbox = [0.0] * 6
            res = measurable.GetBoundaryBox(bbox)
            if isinstance(res, tuple):
                bbox = list(res)

            x_min, y_min, z_min = bbox[0], bbox[1], bbox[2]
            x_max, y_max, z_max = bbox[3], bbox[4], bbox[5]

            dx = abs(x_max - x_min) * MM_PER_M
            dy = abs(y_max - y_min) * MM_PER_M
            dz = abs(z_max - z_min) * MM_PER_M

            if dx < 1e-6 and dy < 1e-6 and dz < 1e-6:
                return None

            return {
                "x": round(dx, 2),
                "y": round(dy, 2),
                "z": round(dz, 2),
                "xmin": round(x_min * MM_PER_M, 2),
                "ymin": round(y_min * MM_PER_M, 2),
                "zmin": round(z_min * MM_PER_M, 2),
                "xmax": round(x_max * MM_PER_M, 2),
                "ymax": round(y_max * MM_PER_M, 2),
                "zmax": round(z_max * MM_PER_M, 2),
                "stock_size": f"{round(dx, 2)} x {round(dy, 2)} x {round(dz, 2)}",
            }
        except Exception:
            return None

    def _get_oobb_from_measurable(self, measurable: Any, part: Any) -> Dict[str, float] | None:
        """OOBB edge lengths + volume-derived depth; dimensions sorted descending."""
        try:
            bbox = [0.0] * 9
            res = measurable.GetMinimumBoundingBox(bbox)
            if isinstance(res, tuple) and len(res) == 9:
                bbox = res

            p1 = (bbox[0], bbox[1], bbox[2])
            p2 = (bbox[3], bbox[4], bbox[5])
            p3 = (bbox[6], bbox[7], bbox[8])

            d12 = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2) * MM_PER_M
            d13 = math.sqrt((p3[0] - p1[0]) ** 2 + (p3[1] - p1[1]) ** 2 + (p3[2] - p1[2]) ** 2) * MM_PER_M

            d3 = 10.0
            try:
                if hasattr(part.Parent, "Product"):
                    vol = part.Parent.Product.Analyze.Volume
                    if vol < 1000:
                        vol *= 1e9
                    if vol > 0 and d12 > 0 and d13 > 0:
                        d3 = vol / (d12 * d13)
            except Exception:
                try:
                    aabb = [0.0] * 6
                    r = measurable.GetBoundaryBox(aabb)
                    if isinstance(r, tuple):
                        aabb = r
                    d3 = abs(aabb[5] - aabb[2]) * MM_PER_M
                except Exception:
                    pass

            dims = sorted([d12, d13, d3], reverse=True)
            if dims[0] < 0.1:
                return None

            x, y, z = round(dims[0], 1), round(dims[1], 1), round(dims[2], 1)
            return {
                "x": x, "y": y, "z": z,
                "xmin": 0, "ymin": 0, "zmin": 0, "xmax": x, "ymax": y, "zmax": z,
                "stock_size": f"{x} x {y} x {z} (OOBB)",
            }
        except Exception:
            return None

    def _get_fallback_bbox(self, item: Any = None) -> Dict[str, float]:
        try:
            if item and hasattr(item.Parent, "Product"):
                product = item.Parent.Product
                vol = product.Analyze.Volume
                if vol < 1000:
                    vol *= 1000000000
                area = product.Analyze.WetArea
                if area < 100:
                    area *= 1000000
                if area > 0:
                    thickness = vol / (area / 2)
                    side = math.sqrt(area / 2)
                    dims = sorted([side, side, thickness], reverse=True)
                    x, y, z = round(dims[0], 1), round(dims[1], 1), round(dims[2], 1)
                    return {
                        "x": x, "y": y, "z": z,
                        "xmin": 0, "ymin": 0, "zmin": 0, "xmax": x, "ymax": y, "zmax": z,
                        "stock_size": f"{x} x {y} x {z} (Est)",
                    }
        except Exception:
            pass
        return {
            "x": 100.0, "y": 100.0, "z": 40.0,
            "xmin": 0, "ymin": 0, "zmin": 0, "xmax": 100.0, "ymax": 100.0, "zmax": 40.0,
            "stock_size": "100.0 x 100.0 x 40.0 (Fallback)",
        }

# Singleton
geometry_service = GeometryService()
