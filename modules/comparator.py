"""
Comparator module for Define XML and PyMuPDF outputs.

The comparison contract is XML-first:
1. Define XML structure is the authority.
2. PyMuPDF records are normalized to match XML-oriented keys.
3. Variable presence and page consistency are the primary checks.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Diff types
DIFF_MATCH = "MATCH"
DIFF_VLM_RESOLVED = "VLM_RESOLVED"
DIFF_PAGE_MISMATCH = "PAGE_MISMATCH"
DIFF_MISSING_IN_PDF = "MISSING_IN_PDF"
DIFF_EXTRA_IN_PDF = "EXTRA_IN_PDF"
DIFF_LOW_CONFIDENCE = "LOW_CONFIDENCE"

_VLM_OPERATORS = {"EQ", "IN"}
_PAGE_RELATION_RANK = {
    "exact": 4,
    "pdf_superset": 3,
    "overlap": 2,
    "pdf_subset": 1,
    "disjoint": 0,
}


def _normalize_text(value: Any) -> str:
    """Normalize text for stable key matching."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text


def _iter_page_tokens(raw_pages: Any) -> Iterable[str]:
    """Yield normalized page tokens from mixed page inputs."""
    if raw_pages is None:
        return

    if isinstance(raw_pages, list):
        for item in raw_pages:
            if item is None:
                continue
            text = str(item).strip()
            if not text:
                continue
            for token in re.split(r"[,\s]+", text):
                token = token.strip()
                if token:
                    yield token
        return

    text = str(raw_pages).strip()
    if not text:
        return
    for token in re.split(r"[,\s]+", text):
        token = token.strip()
        if token:
            yield token


def _parse_pages(raw_pages: Any) -> Set[int]:
    """Parse pages into a deduplicated integer set, supporting ranges like 7-9."""
    pages: Set[int] = set()
    for token in _iter_page_tokens(raw_pages):
        range_match = re.fullmatch(r"(\d+)-(\d+)", token)
        if range_match:
            left = int(range_match.group(1))
            right = int(range_match.group(2))
            start, end = sorted((left, right))
            pages.update(range(start, end + 1))
            continue

        if token.isdigit():
            pages.add(int(token))
    return pages


def _format_pages(pages: Set[int]) -> str:
    """Format sorted pages as a comma-separated string."""
    if not pages:
        return ""
    return ",".join(str(page) for page in sorted(pages))


def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
    """Deduplicate text items while preserving first-seen order."""
    output: List[str] = []
    seen: Set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _build_page_diff_detail(xml_pages: Set[int], pdf_pages: Set[int]) -> str:
    """Build readable page difference detail."""
    xml_only = sorted(xml_pages - pdf_pages)
    pdf_only = sorted(pdf_pages - xml_pages)
    if not xml_only and not pdf_only:
        return ""

    parts: List[str] = []
    if xml_only:
        parts.append(f"xml_only={','.join(map(str, xml_only))}")
    if pdf_only:
        parts.append(f"pdf_only={','.join(map(str, pdf_only))}")
    return "; ".join(parts)


def _page_relation(xml_pages: Set[int], pdf_pages: Set[int]) -> str:
    """Return relation label between XML page set and PDF page set."""
    if xml_pages == pdf_pages:
        return "exact"
    if xml_pages and xml_pages.issubset(pdf_pages):
        return "pdf_superset"
    if pdf_pages and pdf_pages.issubset(xml_pages):
        return "pdf_subset"
    if xml_pages.intersection(pdf_pages):
        return "overlap"
    return "disjoint"


def _parse_define_variable(variable_name: str) -> Dict[str, str]:
    """
    Parse Define XML variable pattern.

    Supported patterns:
    1. Simple: target_var
       Example: FAORRES

    2. 4-part VLM (qualifier with value, no operator):
       target_var.dataset.qualifier.value
       Example: DSSTDTC.DS.DSDECOD.INFORMED CONSENT OBTAINED

    3. 5-part VLM with operator (EQ/IN):
       target_var.dataset.qualifier.operator.value
       Example: IEORRES.IE.IETESTCD.EQ.I03V020

    4. Multi-criteria (multiple dataset.qualifier.value sequences):
       target_var.dataset.qualifier.value.dataset.qualifier.value...
       Example: FAORRES.FA.FATESTCD.CLNRSPC.FA.FACAT.1.FA.FASCAT.2
    """
    normalized = _normalize_text(variable_name)
    parts = [segment.strip() for segment in normalized.split(".") if segment.strip()]

    parsed = {
        "kind": "simple",
        "normalized": normalized,
        "target_var": "",
        "dataset": "",
        "qualifier": "",
        "operator": "",
        "value": "",
        "qualifier_key": "",
        "criteria": [],
    }

    if len(parts) == 1:
        parsed["target_var"] = parts[0]
        return parsed

    if len(parts) >= 5 and parts[3] in _VLM_OPERATORS:
        value = ".".join(parts[4:]).strip()
        if parts[0] and parts[1] and parts[2] and value:
            parsed.update(
                {
                    "kind": "vlm",
                    "target_var": parts[0],
                    "dataset": parts[1],
                    "qualifier": parts[2],
                    "operator": parts[3],
                    "value": value,
                    "qualifier_key": f"{parts[2]}={value}",
                }
            )
            return parsed

    if len(parts) == 4:
        if parts[0] and parts[1] and parts[2] and parts[3]:
            parsed.update(
                {
                   "kind": "vlm",
                    "target_var": parts[0],
                    "dataset": parts[1],
                    "qualifier": parts[2],
                    "value": parts[3],
                    "qualifier_key": f"{parts[2]}={parts[3]}",
                }
            )
            return parsed

    if len(parts) >= 7:
        if (parts[0] and
            (len(parts) - 1) % 3 == 0):
            target_var = parts[0]
            criteria = []
            valid = True

            for i in range(1, len(parts), 3):
                if i + 2 < len(parts):
                    dataset = parts[i]
                    qualifier = parts[i + 1]
                    value = parts[i + 2]
                    if dataset and qualifier and value:
                        criteria.append({
                            "dataset": dataset,
                            "qualifier": qualifier,
                            "value": value,
                        })
                    else:
                        valid = False
                        break

            if valid and criteria:
                qualifier_keys = [f"{c['qualifier']}={c['value']}" for c in criteria]
                parsed.update(
                    {
                        "kind": "multi_criteria",
                        "target_var": target_var,
                        "criteria": criteria,
                        "qualifier_key": " AND ".join(qualifier_keys),
                    }
                )
                return parsed

    parsed["kind"] = "low_confidence"
    return parsed


def _extract_xml_rows(xml_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert XML parser output into normalized compare rows."""
    rows: List[Dict[str, Any]] = []
    for item in xml_result.get("variables", []):
        dataset = str(item.get("Dataset", "")).strip()
        variable = str(item.get("Variable", "")).strip()
        if not variable:
            continue

        pages_set = _parse_pages(item.get("Pages", item.get("PageString", "")))
        parsed = _parse_define_variable(variable)

        rows.append(
            {
                "dataset": dataset,
                "dataset_norm": _normalize_text(dataset),
                "variable": variable,
                "variable_norm": _normalize_text(variable),
                "pages_set": pages_set,
                "pages": _format_pages(pages_set),
                "page_count": len(pages_set),
                "parsed": parsed,
            }
        )
    return rows


def _extract_raw_texts(raw_value: Any) -> List[str]:
    """Normalize raw texts into a list."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    value = str(raw_value).strip()
    return [value] if value else []


def _build_pdf_variable_index(pymupdf_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build an index for PyMuPDF variables (excluding domains and NOT SUBMITTED)."""
    index: Dict[str, Dict[str, Any]] = {}
    for item in pymupdf_result.get("variables", []):
        name_raw = item.get("Variable", item.get("Name", ""))
        name_norm = _normalize_text(name_raw)
        if not name_norm:
            continue

        category = str(item.get("Category", "")).strip().lower()
        if category in {"dataset", "dataset_name", "not_submitted"}:
            continue

        entry = index.setdefault(
            name_norm,
            {
                "name": name_norm,
                "pages_set": set(),
                "category": category or "unknown",
                "raw_texts": [],
            },
        )

        entry["pages_set"].update(_parse_pages(item.get("Pages", item.get("PageString", ""))))
        if not entry["category"] and category:
            entry["category"] = category
        entry["raw_texts"].extend(_extract_raw_texts(item.get("RawTexts")))

    for entry in index.values():
        entry["raw_texts"] = _dedupe_keep_order(entry["raw_texts"])
        entry["pages"] = _format_pages(entry["pages_set"])
        entry["page_count"] = len(entry["pages_set"])

    return index


def _build_pdf_domain_index(pymupdf_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build domain index from domain annotations and any dataset-tagged variable rows."""
    index: Dict[str, Dict[str, Any]] = {}

    def upsert(name_value: Any, pages_value: Any) -> None:
        name_norm = _normalize_text(name_value)
        if not name_norm:
            return
        entry = index.setdefault(name_norm, {"name": name_norm, "pages_set": set()})
        entry["pages_set"].update(_parse_pages(pages_value))

    for item in pymupdf_result.get("domain_annotations", []):
        upsert(item.get("Domain", item.get("Name", "")), item.get("Pages", item.get("PageString", "")))

    for item in pymupdf_result.get("variables", []):
        category = str(item.get("Category", "")).strip().lower()
        if category in {"dataset", "dataset_name"}:
            upsert(item.get("Variable", item.get("Name", "")), item.get("Pages", item.get("PageString", "")))

    for entry in index.values():
        entry["pages"] = _format_pages(entry["pages_set"])
        entry["page_count"] = len(entry["pages_set"])

    return index


def _choose_best_pdf_match(
    xml_pages: Set[int],
    candidates: List[Tuple[str, str]],
    pdf_index: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Pick the best PDF match candidate by page relation quality."""
    best: Optional[Dict[str, Any]] = None

    for order, (candidate_name, match_path) in enumerate(candidates):
        pdf_entry = pdf_index.get(candidate_name)
        if not pdf_entry:
            continue

        relation = _page_relation(xml_pages, pdf_entry["pages_set"])
        score = _PAGE_RELATION_RANK.get(relation, -1)

        candidate = {
            "candidate_name": candidate_name,
            "match_path": match_path,
            "relation": relation,
            "score": score,
            "order": order,
            "pdf_entry": pdf_entry,
        }

        if best is None:
            best = candidate
            continue

        if candidate["score"] > best["score"]:
            best = candidate
            continue

        if candidate["score"] == best["score"] and candidate["order"] < best["order"]:
            best = candidate

    return best


def compare_xml_vs_pymupdf(xml_result: Dict[str, Any], pymupdf_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare Define XML results against PyMuPDF results.

    XML is the authority source. Output includes:
    - detail_rows: XML-anchored comparison report
    - extra_pdf_rows: variables found only in PyMuPDF
    - extra_pdf_domain_rows: domains found only in PyMuPDF
    - summary and summary_by_dataset
    """
    try:
        xml_rows = _extract_xml_rows(xml_result)
        pdf_var_index = _build_pdf_variable_index(pymupdf_result)
        pdf_domain_index = _build_pdf_domain_index(pymupdf_result)

        detail_rows: List[Dict[str, Any]] = []
        xml_candidate_names: Set[str] = set()
        xml_dataset_names: Set[str] = set()

        dataset_summary: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "Dataset": "",
                "XML_Variable_Count": 0,
                DIFF_MATCH: 0,
                DIFF_VLM_RESOLVED: 0,
                DIFF_PAGE_MISMATCH: 0,
                DIFF_MISSING_IN_PDF: 0,
                DIFF_LOW_CONFIDENCE: 0,
            }
        )

        for row in xml_rows:
            parsed = row["parsed"]
            xml_dataset = row["dataset"]
            dataset_key = row["dataset_norm"] or "UNKNOWN"
            xml_dataset_names.add(dataset_key)

            dataset_bucket = dataset_summary[dataset_key]
            dataset_bucket["Dataset"] = xml_dataset or "UNKNOWN"
            dataset_bucket["XML_Variable_Count"] += 1

            candidates: List[Tuple[str, str]] = []
            if parsed["kind"] == "vlm":
                if parsed["target_var"]:
                    candidates.append((parsed["target_var"], "path_A_target_var"))
                    xml_candidate_names.add(parsed["target_var"])
                if parsed["qualifier_key"]:
                    candidates.append((parsed["qualifier_key"], "path_B_qualifier_value"))
                    xml_candidate_names.add(parsed["qualifier_key"])
            elif parsed["kind"] == "multi_criteria":
                if parsed["target_var"]:
                    candidates.append((parsed["target_var"], "path_A_target_var"))
                    xml_candidate_names.add(parsed["target_var"])
                for i, criterion in enumerate(parsed.get("criteria", [])):
                    key = f"{criterion['qualifier']}={criterion['value']}"
                    candidates.append((key, f"path_B_criteria_{i}"))
                    xml_candidate_names.add(key)
            else:
                if row["variable_norm"]:
                    candidates.append((row["variable_norm"], "simple"))
                    xml_candidate_names.add(row["variable_norm"])

            diff_type = DIFF_MISSING_IN_PDF
            page_subset = ""
            matched_name = ""
            matched_pages = ""
            matched_page_count = 0
            page_diff_detail = ""
            match_path = ""
            note = ""

            if parsed["kind"] == "low_confidence":
                diff_type = DIFF_LOW_CONFIDENCE
                note = "Unable to parse XML variable into simple or VLM pattern."
            else:
                best_match = _choose_best_pdf_match(row["pages_set"], candidates, pdf_var_index)
                if best_match is None:
                    diff_type = DIFF_MISSING_IN_PDF
                else:
                    matched_name = best_match["candidate_name"]
                    matched_entry = best_match["pdf_entry"]
                    matched_pages = matched_entry["pages"]
                    matched_page_count = matched_entry["page_count"]
                    page_subset = best_match["relation"]
                    page_diff_detail = _build_page_diff_detail(row["pages_set"], matched_entry["pages_set"])
                    match_path = best_match["match_path"]
                    if page_subset == "exact":
                        diff_type = (
                            DIFF_VLM_RESOLVED
                            if parsed["kind"] in ("vlm", "multi_criteria")
                            else DIFF_MATCH
                        )
                    else:
                        diff_type = DIFF_PAGE_MISMATCH

            dataset_bucket[diff_type] += 1
            detail_rows.append(
                {
                    "XML_Dataset": xml_dataset,
                    "XML_Variable": row["variable"],
                    "XML_Pages": row["pages"],
                    "XML_PageCount": row["page_count"],
                    "PDF_Matched_Name": matched_name,
                    "PDF_Pages": matched_pages,
                    "PDF_PageCount": matched_page_count,
                    "diff_type": diff_type,
                    "page_subset": page_subset,
                    "match_path": match_path,
                    "page_diff_detail": page_diff_detail,
                    "note": note,
                }
            )

        detail_rows.sort(key=lambda item: (item["XML_Dataset"], item["XML_Variable"]))

        extra_pdf_rows: List[Dict[str, Any]] = []
        for name, entry in sorted(pdf_var_index.items()):
            if name in xml_candidate_names:
                continue

            subtype = "value_pair" if "=" in name else "unmapped_variable"
            extra_pdf_rows.append(
                {
                    "diff_type": DIFF_EXTRA_IN_PDF,
                    "PDF_Name": name,
                    "PDF_Pages": entry["pages"],
                    "PDF_PageCount": entry["page_count"],
                    "Category": entry.get("category", "unknown"),
                    "subtype": subtype,
                    "RawTexts": " | ".join(entry.get("raw_texts", [])),
                }
            )

        extra_pdf_domain_rows: List[Dict[str, Any]] = []
        for domain_name, entry in sorted(pdf_domain_index.items()):
            if domain_name in xml_dataset_names:
                continue
            extra_pdf_domain_rows.append(
                {
                    "diff_type": DIFF_EXTRA_IN_PDF,
                    "PDF_Domain": domain_name,
                    "PDF_Pages": entry["pages"],
                    "PDF_PageCount": entry["page_count"],
                    "subtype": "extra_domain",
                }
            )

        summary_by_dataset = list(dataset_summary.values())
        summary_by_dataset.sort(key=lambda row: row["Dataset"])

        summary = {
            "total_xml_variables": len(xml_rows),
            "total_pdf_variables": len(pdf_var_index),
            "total_pdf_domains": len(pdf_domain_index),
            "matched": sum(1 for row in detail_rows if row["diff_type"] == DIFF_MATCH),
            "vlm_resolved": sum(
                1 for row in detail_rows if row["diff_type"] == DIFF_VLM_RESOLVED
            ),
            "page_mismatch": sum(1 for row in detail_rows if row["diff_type"] == DIFF_PAGE_MISMATCH),
            "missing_in_pdf": sum(1 for row in detail_rows if row["diff_type"] == DIFF_MISSING_IN_PDF),
            "low_confidence": sum(1 for row in detail_rows if row["diff_type"] == DIFF_LOW_CONFIDENCE),
            "extra_in_pdf_variables": len(extra_pdf_rows),
            "extra_in_pdf_domains": len(extra_pdf_domain_rows),
        }

        return {
            "status": "success",
            "summary": summary,
            "summary_by_dataset": summary_by_dataset,
            "detail_rows": detail_rows,
            "extra_pdf_rows": extra_pdf_rows,
            "extra_pdf_domain_rows": extra_pdf_domain_rows,
            "error_message": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "summary": {},
            "summary_by_dataset": [],
            "detail_rows": [],
            "extra_pdf_rows": [],
            "extra_pdf_domain_rows": [],
            "error_message": str(exc),
        }


def rows_to_csv_bytes(rows: List[Dict[str, Any]], fieldnames: List[str]) -> bytes:
    """Convert row dictionaries to UTF-8 CSV bytes."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def compare_parser_results(pymupdf_result: Dict[str, Any],
                          opencv_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare extraction results from PyMuPDF and OpenCV parsers.

    Returns consensus, PyMuPDF-only, and OpenCV-only variables.

    Args:
        pymupdf_result: Result dict from extract_variables_from_pdf (PyMuPDF)
        opencv_result: Result dict from extract_variables_from_pdf (OpenCV)

    Returns:
        {
            "consensus": [...],      # Both found same variable
            "pymupdf_only": [...],   # Only PyMuPDF found
            "opencv_only": [...],    # Only OpenCV found
            "summary": {...}
        }
    """
    try:
        # Extract variable names from both results
        pymupdf_vars = {}
        if pymupdf_result.get("status") == "success":
            for var in pymupdf_result.get("variables", []):
                var_name = var.get("Variable", "")
                if var_name:
                    pymupdf_vars[var_name.upper()] = var

        opencv_vars = {}
        if opencv_result.get("status") == "success":
            for var in opencv_result.get("variables", []):
                var_name = var.get("Variable", "")
                if var_name:
                    opencv_vars[var_name.upper()] = var

        # Find consensus, page mismatches, differences
        consensus = []
        page_mismatch = []
        pymupdf_only = []
        opencv_only = []

        def normalize_pages(value: Any) -> List[int]:
            if isinstance(value, list):
                raw_pages = value
            elif isinstance(value, str):
                raw_pages = [part.strip() for part in value.split(",") if part.strip()]
            else:
                raw_pages = []
            pages = []
            for page in raw_pages:
                try:
                    pages.append(int(page))
                except (TypeError, ValueError):
                    continue
            return pages

        def raw_text_display(entry: Dict[str, Any]) -> str:
            raw_texts = entry.get("RawTexts", [])
            if isinstance(raw_texts, list):
                return " | ".join(str(x) for x in raw_texts if x)
            return str(raw_texts) if raw_texts else ""

        # Variables found in both
        for var_name in sorted(pymupdf_vars.keys()):
            if var_name in opencv_vars:
                # Both found it - merge pages
                pymupdf_entry = pymupdf_vars[var_name]
                opencv_entry = opencv_vars[var_name]

                # Compare pages. Regular variables require matching page sets.
                # NOT SUBMITTED is occurrence-based, so compare duplicate page counts too.
                pymupdf_pages_list = normalize_pages(pymupdf_entry.get("Pages", []))
                opencv_pages_list = normalize_pages(opencv_entry.get("Pages", []))
                pymupdf_pages = set(pymupdf_pages_list)
                opencv_pages = set(opencv_pages_list)
                all_pages = sorted(pymupdf_pages | opencv_pages)
                page_set_match = pymupdf_pages == opencv_pages
                is_not_submitted = (
                    var_name == "NOT SUBMITTED"
                    or pymupdf_entry.get("Category") == "not_submitted"
                    or opencv_entry.get("Category") == "not_submitted"
                )
                occurrence_match = True
                if is_not_submitted:
                    occurrence_match = Counter(pymupdf_pages_list) == Counter(opencv_pages_list)

                pymupdf_raw = pymupdf_entry.get("RawTexts", [])
                opencv_raw = opencv_entry.get("RawTexts", [])
                if not isinstance(pymupdf_raw, list):
                    pymupdf_raw = [str(pymupdf_raw)] if pymupdf_raw else []
                if not isinstance(opencv_raw, list):
                    opencv_raw = [str(opencv_raw)] if opencv_raw else []
                merged_raw = []
                seen_raw = set()
                for raw in pymupdf_raw + opencv_raw:
                    if raw and raw not in seen_raw:
                        seen_raw.add(raw)
                        merged_raw.append(raw)

                common_record = {
                    "Variable": var_name,
                    "Pages": all_pages,
                    "PageString": ",".join(map(str, all_pages)),
                    "PageCount": len(all_pages),
                    "PyMuPDF_Pages": pymupdf_entry.get("PageString", ""),
                    "OpenCV_Pages": opencv_entry.get("PageString", ""),
                    "Category": pymupdf_entry.get("Category", "unknown"),
                    "RawTexts": " | ".join(merged_raw)
                }
                if page_set_match and occurrence_match:
                    consensus.append(common_record)
                else:
                    mismatch_reason = "page_set_mismatch"
                    if is_not_submitted and page_set_match and not occurrence_match:
                        mismatch_reason = "occurrence_count_mismatch"
                    elif is_not_submitted and not occurrence_match:
                        mismatch_reason = "page_or_occurrence_mismatch"
                    common_record["MismatchReason"] = mismatch_reason
                    common_record["PyMuPDF_PageCount"] = len(pymupdf_pages_list)
                    common_record["OpenCV_PageCount"] = len(opencv_pages_list)
                    page_mismatch.append(common_record)

        # Variables only in PyMuPDF
        for var_name, entry in sorted(pymupdf_vars.items()):
            if var_name not in opencv_vars:
                pymupdf_only.append({
                    "Variable": var_name,
                    "Pages": entry.get("PageString", ""),
                    "PageCount": entry.get("PageCount", 0),
                    "Category": entry.get("Category", "unknown"),
                    "RawTexts": raw_text_display(entry)
                })

        # Variables only in OpenCV
        for var_name, entry in sorted(opencv_vars.items()):
            if var_name not in pymupdf_vars:
                opencv_only.append({
                    "Variable": var_name,
                    "Pages": entry.get("PageString", ""),
                    "PageCount": entry.get("PageCount", 0),
                    "Category": entry.get("Category", "unknown"),
                    "RawTexts": raw_text_display(entry)
                })

        return {
            "status": "success",
            "consensus": consensus,
            "page_mismatch": page_mismatch,
            "pymupdf_only": pymupdf_only,
            "opencv_only": opencv_only,
            "summary": {
                "consensus_count": len(consensus),
                "page_mismatch_count": len(page_mismatch),
                "pymupdf_only_count": len(pymupdf_only),
                "opencv_only_count": len(opencv_only),
                "total_pymupdf": len(pymupdf_vars),
                "total_opencv": len(opencv_vars)
            },
            "error_message": None
        }

    except Exception as e:
        return {
            "status": "error",
            "consensus": [],
            "page_mismatch": [],
            "pymupdf_only": [],
            "opencv_only": [],
            "summary": {},
            "error_message": str(e)
        }
