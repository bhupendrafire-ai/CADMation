import re
from typing import Any, Dict, List


def normalize_linear_dims(values: List[float]) -> List[float]:
    return sorted([round(abs(float(v)), 2) for v in values if v is not None], reverse=True)


def _pair_close(a: float, b: float, tolerance_ratio: float = 0.08, absolute_floor: float = 1.0) -> bool:
    delta = abs(float(a) - float(b))
    limit = max(absolute_floor, max(abs(float(a)), abs(float(b))) * tolerance_ratio)
    return delta <= limit


def infer_stock_form_from_dims(dx: float, dy: float, dz: float) -> Dict[str, Any]:
    dims = [round(abs(float(dx)), 2), round(abs(float(dy)), 2), round(abs(float(dz)), 2)]
    dims_sorted = sorted(dims)
    low, mid, high = dims_sorted

    if _pair_close(low, mid) and not _pair_close(mid, high):
        dia = round((low + mid) / 2.0, 2)
        return {"kind": "diameter", "dims": [dia, high], "ordered_dims": [high, dia, dia], "stockForm": "round"}

    if _pair_close(mid, high) and not _pair_close(low, mid):
        dia = round((mid + high) / 2.0, 2)
        return {"kind": "diameter", "dims": [dia, low], "ordered_dims": [dia, dia, low], "stockForm": "round"}

    ordered = normalize_linear_dims(dims)
    return {"kind": "box", "dims": ordered[:3], "ordered_dims": ordered[:3], "stockForm": "rectangular"}


def parse_size_string(size_value: str) -> Dict[str, Any]:
    raw = (size_value or "").strip()
    if not raw or raw == "Not Measurable":
        return {"kind": "empty", "raw": raw, "dims": [], "l": "", "w": "", "h": "", "stockForm": "unknown"}

    normalized = raw.upper().replace("Ø", "DIA ")
    numbers = [float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", normalized)]
    if ("DIA" in normalized or "DIAMETER" in normalized) and len(numbers) >= 2:
        dia = round(numbers[0], 2)
        height = round(numbers[1], 2)
        return {
            "kind": "diameter",
            "raw": raw,
            "dims": [dia, height],
            "l": f"DIA {dia:g}",
            "w": "",
            "h": f"{height:g}",
            "stockForm": "round",
        }

    if len(numbers) >= 3:
        l, w, h = normalize_linear_dims(numbers[:3])[:3]
        return {
            "kind": "box",
            "raw": raw,
            "dims": [l, w, h],
            "l": f"{l:g}",
            "w": f"{w:g}",
            "h": f"{h:g}",
            "stockForm": "rectangular",
        }

    return {"kind": "raw", "raw": raw, "dims": numbers, "l": raw, "w": "", "h": "", "stockForm": "unknown"}


def format_size(size_data: Dict[str, Any]) -> str:
    kind = size_data.get("kind")
    if kind == "diameter" and len(size_data.get("dims", [])) >= 2:
        dia, height = size_data["dims"][:2]
        return f"DIA {dia:g} x {height:g}"
    if kind == "box" and len(size_data.get("dims", [])) >= 3:
        l, w, h = size_data["dims"][:3]
        return f"{l:g} x {w:g} x {h:g}"
    return size_data.get("raw", "") or "Not Measurable"


def build_size_payload(size_value: str) -> Dict[str, Any]:
    parsed = parse_size_string(size_value)
    return {
        "sizeKind": parsed["kind"],
        "stockForm": parsed.get("stockForm", "unknown"),
        "size": format_size(parsed),
        "L": parsed.get("l", ""),
        "W": parsed.get("w", ""),
        "H": parsed.get("h", ""),
        "_MERGE_LW": parsed.get("kind") == "diameter",
    }


def build_measurement_payload(dx: float, dy: float, dz: float, method_used: str = "") -> Dict[str, Any]:
    inferred = infer_stock_form_from_dims(dx, dy, dz)
    if inferred["kind"] == "diameter":
        formatted = format_size(inferred)
    else:
        formatted = format_size({"kind": "box", "dims": inferred["dims"][:3]})
    size_payload = build_size_payload(formatted)
    return {
        "stock_size": formatted,
        "rawDims": [round(abs(float(dx)), 2), round(abs(float(dy)), 2), round(abs(float(dz)), 2)],
        "orderedDims": inferred.get("ordered_dims", []),
        "stockForm": inferred.get("stockForm", "unknown"),
        "sizeKind": size_payload["sizeKind"],
        "L": size_payload["L"],
        "W": size_payload["W"],
        "H": size_payload["H"],
        "_MERGE_LW": size_payload["_MERGE_LW"],
        "measurement_confidence": measurement_confidence(method_used, formatted),
    }


def derive_rm_size(size_value: str, machining_stock: float = 0, rounding_mm: float = 0) -> str:
    parsed = parse_size_string(size_value)
    add = float(machining_stock or 0)
    step = float(rounding_mm or 0)

    def _apply(value: float) -> float:
        bumped = value + add
        if step > 0:
            return round(round(bumped / step) * step, 2)
        return round(bumped, 2)

    if parsed["kind"] == "diameter" and len(parsed["dims"]) >= 2:
        dia, height = parsed["dims"][:2]
        return format_size({"kind": "diameter", "dims": [_apply(dia), _apply(height)]})

    if parsed["kind"] == "box" and len(parsed["dims"]) >= 3:
        dims = [_apply(v) for v in parsed["dims"][:3]]
        return format_size({"kind": "box", "dims": normalize_linear_dims(dims)})

    return size_value or "Not Measurable"


def measurement_confidence(method_used: str, size_value: str) -> str:
    if size_value == "Not Measurable":
        return "low"
    if method_used == "ROUGH_STOCK":
        return "high"
    if method_used in {"STL", "SPA"}:
        return "medium"
    if method_used == "MANUAL":
        return "high"
    return "low"


def compute_weight_kg(size_value: str, material: str) -> float | None:
    parsed = parse_size_string(size_value)
    if parsed["kind"] not in {"box", "diameter"}:
        return None

    material_key = (material or "").upper()
    density = 7.85e-6
    if "AL" in material_key:
        density = 2.7e-6
    elif "BRASS" in material_key:
        density = 8.4e-6

    if parsed["kind"] == "box" and len(parsed["dims"]) >= 3:
        l, w, h = parsed["dims"][:3]
        return round(l * w * h * density, 3)

    if parsed["kind"] == "diameter" and len(parsed["dims"]) >= 2:
        dia, height = parsed["dims"][:2]
        radius = dia / 2.0
        volume = 3.141592653589793 * radius * radius * height
        return round(volume * density, 3)

    return None


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
