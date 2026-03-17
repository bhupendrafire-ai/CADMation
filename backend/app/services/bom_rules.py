import re
from typing import Any, Dict, List

from app.services.bom_schema import build_size_payload, compute_weight_kg, derive_rm_size, ensure_list, format_size, measurement_confidence, normalize_linear_dims, parse_size_string


STD_KEYWORDS = ("MISUMI", "FIBRO", "DIN", "ISO", "STANDARD", "PUNCH", "PILLAR", "GSV", "DTPK", "MWF", "SWL")
MS_PART_HINTS = ("STRAP", "SETTING PLATE", "MTG PLATE", "MOUNTING PLATE", "STACKER BLOCK")
BLOCK_PART_HINTS = ("PLATE", "BLOCK", "FLANGE", "PAD", "STRAP", "ADAPTER", "DIE", "STEEL", "MOUNT", "MTG")
ROUND_PART_HINTS = ("PIN", "PILLAR", "BUSH", "BUSHING", "ROD", "SHAFT", "ROLLER", "POST", "SPACER", "SLEEVE", "PUNCH", "DOWEL")


def clean_token(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^COPY \(\d+\) OF\s+", "", text, flags=re.I)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"_\d+$", "", text)
    text = re.sub(r"\.\d+$", "", text)
    return text.strip(" ._")


def _normalize_std_sheet(value: str) -> str:
    text = (value or "").strip()
    if text in {"STD-MISUMI", "STD-OTHER", "STD"}:
        return "STD"
    return text


def _coerce_rectangular_size(row: Dict[str, Any], size_value: str) -> str:
    parsed = parse_size_string(size_value)
    if parsed.get("kind") != "diameter":
        return size_value

    combined = f"{row.get('description', '')} {row.get('partNumber', '')} {row.get('instanceName', '')}".upper()
    if any(token in combined for token in ROUND_PART_HINTS):
        return size_value
    if not any(token in combined for token in BLOCK_PART_HINTS):
        return size_value

    source_dims: List[float] = []
    for raw_dim in ensure_list(row.get("orderedDims")) or ensure_list(row.get("rawDims")):
        try:
            source_dims.append(float(raw_dim))
        except (TypeError, ValueError):
            continue
    if len(source_dims) < 3:
        return size_value

    return format_size({"kind": "box", "dims": normalize_linear_dims(source_dims[:3])})


def normalize_catalog_code(part_number: str, instance_name: str = "") -> str:
    combined = f"{part_number} {instance_name}".upper()
    patterns = [
        r"\b(MWF\d+(?:-\d+)+)\b",
        r"\b(DTPK\d+(?:-\d+)+(?:-[A-Z]+)?)\b",
        r"\b(DTPM\d+(?:-\d+)+(?:-[A-Z]+)?)\b",
        r"\b(GSV\d+(?:-\d+)+)\b",
        r"\b(SWL\d+(?:-\d+)+)\b",
        r"\b([A-Z]{2,}\d+(?:-\d+){1,4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return clean_token(match.group(1))
    cleaned = clean_token(part_number)
    if re.match(r"^[A-Z0-9-]+$", cleaned.upper()):
        return cleaned
    return ""


def is_standard_part(part_number: str, instance_name: str = "", manufacturer: str = "") -> bool:
    combined = f"{part_number} {instance_name} {manufacturer}".upper()
    return any(token in combined for token in STD_KEYWORDS)


def normalize_material(material: str, part_number: str = "", description: str = "", explicit_category: str = "") -> str:
    raw = (material or "").strip().upper()
    category = (explicit_category or "").strip()
    if not raw or raw in {"N/A", "NONE"}:
        raw = ""
    if raw == "MS" or "MILD" in raw:
        return "MS"
    if "CAST" in raw or raw in {"CI", "FG260", "FG300", "SG IRON"}:
        return raw or "CASTING"
    if raw in {"STEEL", "C45"}:
        return "C45"
    if "D2" in raw:
        return "IMP D2"
    if "OHNS" in raw:
        return "OHNS"
    if "EN8" in raw:
        return "EN8"
    if not raw:
        if category in {"Steel", "Casting"}:
            return ""
        combined = f"{clean_token(part_number)} {description}".upper()
        if any(token in combined for token in MS_PART_HINTS):
            return "MS"
        return "C45"
    return raw


def humanize_identifier(value: str) -> str:
    cleaned = clean_token(value)
    cleaned = re.sub(r"^\d+[-_ ]*", "", cleaned)
    cleaned = cleaned.replace("_", " ").replace(".", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.title()


def infer_description(part_number: str, instance_name: str, catalog_code: str, is_std: bool) -> str:
    combined = f"{part_number} {instance_name}".upper()
    keyword_map = {
        "WEAR_PLATE": "Wear Plate",
        "TRANSPORTAION STRAP": "Transportation Strap",
        "TRANSPORTATION STRAP": "Transportation Strap",
        "GAS SPRING MTG PLATE": "Gas Spring Mtg Plate",
        "GAS SPRING": "Gas Spring",
        "BALANCER": "Balancer Block",
        "STACKER BLOCK": "Stacker Block",
        "STACKER PIN": "Stacker Pin",
        "STOPPER PLATE": "Stopper Plate",
        "SETTING PLATE": "Setting Plate",
        "LOWER FLANGE STEEL": "Lower Flange Steel",
        "UPPER FLANGE STEEL": "Upper Flange Steel",
        "LOWER PAD STEEL": "Lower Pad Steel",
        "HITTING BLOCK": "Hitting Block",
        "PART GAUGE PIN": "Part Gauge Pin",
    }
    for needle, label in keyword_map.items():
        if needle in combined:
            return label
    if is_std and catalog_code:
        return humanize_identifier(catalog_code)
    return humanize_identifier(part_number or instance_name)


def infer_manufacturer(is_std: bool, part_number: str, instance_name: str) -> str:
    if not is_std:
        return ""
    combined = f"{part_number} {instance_name}".upper()
    if any(token in combined for token in ("MISUMI", "MWF", "DTPK", "DTPM", "GSV", "SWL")):
        return "MISUMI"
    return "STANDARD"


def infer_remark(row: Dict[str, Any]) -> str:
    if row.get("isStd"):
        return "STD"
    description = (row.get("description") or "").upper()
    material = (row.get("material") or "").upper()
    if (row.get("sheetCategory") or row.get("exportBucket")) == "Casting" or "CAST" in material:
        return "Casting"
    size = row.get("millingSize") or row.get("size") or ""
    parsed = parse_size_string(size)
    dims = parsed.get("dims", [])
    large_plate = len(dims) >= 3 and max(dims[:3]) >= 300
    if "MTG PLATE" in description:
        return "VMC Gas Cut"
    if "SETTING PLATE" in description and material == "MS":
        return "Gas Cut"
    if material == "MS" and large_plate:
        return "Gas Cut"
    if parsed.get("kind") == "diameter":
        return f"Dia {dims[0]:g}" if dims else "Dia"
    return "Bend Saw"


def infer_validation_flags(row: Dict[str, Any]) -> List[str]:
    flags = list(ensure_list(row.get("validationFlags")))
    if row.get("millingSize") == "Not Measurable":
        flags.append("measurement_failed")
    if row.get("originType") == "assembly_container":
        flags.append("assembly_container")
    if row.get("isStd") and not row.get("catalogCode"):
        flags.append("missing_catalog_code")
    if not row.get("isStd") and not row.get("material"):
        flags.append("missing_material")
    if not row.get("description"):
        flags.append("missing_description")
    if row.get("measurementConfidence") == "low":
        flags.append("low_confidence")
    if ".." in (row.get("partNumber") or "") or ".." in (row.get("instanceName") or ""):
        flags.append("noisy_identifier")
    return sorted(set(flags))


def infer_sheet_category(row: Dict[str, Any]) -> str:
    explicit = _normalize_std_sheet(row.get("sheetCategory") or row.get("exportBucket"))
    if explicit in {"Steel", "MS", "Casting", "STD"}:
        return explicit

    if row.get("isStd"):
        return "STD"

    material = normalize_material(row.get("material", ""), row.get("partNumber", ""), row.get("description", ""))
    description = (row.get("description") or "").upper()
    if "CAST" in material or "CAST" in description:
        return "Casting"
    if material == "MS" or any(token in description for token in MS_PART_HINTS):
        return "MS"
    return "Steel"


def infer_review_status(row: Dict[str, Any]) -> str:
    if row.get("reviewStatus"):
        return row["reviewStatus"]
    flags = set(ensure_list(row.get("validationFlags")))
    if flags:
        return "needs_review"
    return "approved"


def infer_discrepancy_type(row: Dict[str, Any]) -> str:
    if row.get("discrepancyType"):
        return row["discrepancyType"]
    flags = set(ensure_list(row.get("validationFlags")))
    if "measurement_failed" in flags:
        return "measurement_failed"
    if "assembly_container" in flags:
        return "wrong_data"
    if flags:
        return "uncertain"
    return ""


def canonicalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    part_number = row.get("partNumber") or row.get("id") or row.get("name") or ""
    instance_name = row.get("instanceName") or row.get("name") or part_number
    origin_type = row.get("originType") or ("leaf_part" if row.get("type") in {"Part", "Component"} else "unknown_leaf")
    catalog_code = row.get("catalogCode") or normalize_catalog_code(part_number, instance_name)
    std_flag = bool(row.get("isStd")) or is_standard_part(part_number, instance_name, row.get("manufacturer", ""))
    manufacturer = row.get("manufacturer") or infer_manufacturer(std_flag, part_number, instance_name)
    description = row.get("description") or infer_description(part_number, instance_name, catalog_code, std_flag)
    explicit_category = _normalize_std_sheet(row.get("sheetCategory") or row.get("exportBucket") or "")
    material = normalize_material(row.get("material", ""), part_number, description, explicit_category)
    milling_size = _coerce_rectangular_size(row, row.get("millingSize") or row.get("size") or "Not Measurable")
    rm_size = row.get("rmSize") or derive_rm_size(
        milling_size,
        row.get("machiningStock", 0),
        row.get("roundingMm", 0),
    )
    method_used = row.get("methodUsed") or row.get("method_used") or "UNKNOWN"
    measurement_conf = row.get("measurementConfidence") or row.get("measurement_confidence") or measurement_confidence(method_used, milling_size)

    canonical = {
        "id": row.get("id", part_number),
        "name": row.get("name", part_number),
        "sourceRowId": row.get("sourceRowId") or f"{part_number}|{instance_name}|{row.get('id', '')}",
        "partNumber": part_number,
        "instanceName": instance_name,
        "instances": ensure_list(row.get("instances")) or [instance_name],
        "qty": int(row.get("qty", 1) or 1),
        "selected": row.get("selected", True),
        "keepInExport": row.get("keepInExport", row.get("selected", True)),
        "isStd": std_flag,
        "classification": "std_misumi" if std_flag and manufacturer == "MISUMI" else ("std_other" if std_flag else "mfg"),
        "originType": origin_type,
        "parentAssembly": row.get("parentAssembly", ""),
        "referenceKey": row.get("referenceKey", ""),
        "sourceDocPath": row.get("sourceDocPath", ""),
        "sourceDocumentName": row.get("sourceDocumentName", ""),
        "manufacturer": manufacturer,
        "catalogCode": catalog_code,
        "material": "" if std_flag else material,
        "description": description,
        "remark": row.get("remark") or "",
        "heatTreatment": row.get("heatTreatment") or row.get("heat_treatment") or "NONE",
        "methodUsed": method_used,
        "millingSize": milling_size,
        "rmSize": rm_size,
        "machiningStock": float(row.get("machiningStock", 0) or 0),
        "roundingMm": float(row.get("roundingMm", 0) or 0),
        "rawDims": ensure_list(row.get("rawDims")),
        "orderedDims": ensure_list(row.get("orderedDims")),
        "stockForm": row.get("stockForm", ""),
        "measurementConfidence": measurement_conf,
        "reviewNote": row.get("reviewNote", ""),
    }
    canonical.update(build_size_payload(canonical["millingSize"]))
    rm_payload = build_size_payload(canonical["rmSize"])
    canonical["rmSizeKind"] = rm_payload["sizeKind"]
    canonical["rmStockForm"] = rm_payload["stockForm"]
    canonical["rmL"] = rm_payload["L"]
    canonical["rmW"] = rm_payload["W"]
    canonical["rmH"] = rm_payload["H"]
    canonical["rmMergeLW"] = rm_payload["_MERGE_LW"]
    canonical["remark"] = canonical["remark"] or infer_remark(canonical)
    canonical["validationFlags"] = infer_validation_flags({**canonical, "validationFlags": row.get("validationFlags", [])})
    canonical["sheetCategory"] = infer_sheet_category(canonical)
    canonical["exportBucket"] = _normalize_std_sheet(row.get("exportBucket")) or canonical["sheetCategory"]
    canonical["reviewStatus"] = infer_review_status(canonical)
    canonical["discrepancyType"] = infer_discrepancy_type(canonical)
    canonical["rmWeightKg"] = row.get("rmWeightKg")
    if canonical["rmWeightKg"] is None and not std_flag:
        canonical["rmWeightKg"] = compute_weight_kg(canonical["rmSize"], canonical["material"])
    canonical["finishWeightKg"] = row.get("finishWeightKg")
    if canonical["finishWeightKg"] is None and not std_flag:
        canonical["finishWeightKg"] = compute_weight_kg(canonical["millingSize"], canonical["material"])
    return canonical
