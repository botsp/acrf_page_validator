"""
OpenCV + OCR based annotation extraction for PDF analysis.

This module provides image-based extraction for:
1. Flattened PDFs (no text layer) - primary use case
2. Non-MSG-2.0-compliant PDFs - fallback for PyMuPDF failures
3. Annotations without /Contents field - detected by PyMuPDF's need_ocr list

Strategy:
- Convert PDF pages to images using PyMuPDF rendering
- Detect colored/bordered boxes using contour analysis
- Extract text via Tesseract OCR
- Classify results using same priority rules as PyMuPDF

Output format: Identical to PyMuPDF extract_variables_from_pdf()
"""

import fitz  # PyMuPDF for rendering
import cv2
import numpy as np
import re
import time
import shutil
import os
from pathlib import Path
import pytesseract
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

try:
    from config.config_loader import CONFIG
except ImportError:
    from ..config.config_loader import CONFIG

# Local stopwords (same as PyMuPDF)
DEFAULT_STOPWORDS = {"AND", "OR", "IF", "THEN", "THE", "A", "IN", "ON", "FOR", "WITH", "IS", "ARE", "TO", "BY", "OF", "NOTE"}
OCR_SHORT_TOKEN_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=/._-"


def resolve_tesseract_cmd() -> str:
    """Resolve Tesseract executable path from PATH or common Windows install paths."""
    found = shutil.which("tesseract")
    if found:
        return found

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def is_tesseract_available() -> Tuple[bool, str]:
    """Check whether Tesseract OCR engine is available on this machine."""
    try:
        cmd = resolve_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        _ = pytesseract.get_tesseract_version()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _compute_rect_iou(rect_a: Tuple[int, int, int, int], rect_b: Tuple[int, int, int, int]) -> float:
    """Compute IoU between two (x, y, w, h) rectangles."""
    ax, ay, aw, ah = rect_a
    bx, by, bw, bh = rect_b

    left = max(ax, bx)
    right = min(ax + aw, bx + bw)
    top = max(ay, by)
    bottom = min(ay + ah, by + bh)

    if right <= left or bottom <= top:
        return 0.0

    intersection = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - intersection
    return (intersection / union) if union > 0 else 0.0


def _normalize_ocr_text(text: str) -> str:
    """Normalize OCR text by collapsing whitespace."""
    return re.sub(r"\s{2,}", " ", (text or "").replace("\n", " ").replace("\r", " ")).strip()


def _score_annotation_text(text: str) -> float:
    """
    Score whether OCR text looks like annotation content rather than page body text.

    Higher score => more annotation-like.
    """
    normalized = _normalize_ocr_text(text)
    if not normalized:
        return -10.0

    upper_tokens = re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", normalized)
    domain_label_hits = len(re.findall(r"\b[A-Z][A-Z0-9]{1,7}\s*(?:\(|=)", normalized))
    variable_equal_hits = len(re.findall(r"\b[A-Z][A-Z0-9]{1,7}(?:/[A-Z][A-Z0-9]{1,7})*\s*=", normalized))
    supp_hits = 1 if re.search(r"\bSUPP[A-Z]{2,8}\b", normalized) else 0
    not_submitted_hits = len(re.findall(r"\b(?:NOT\s+SUBMITTED|NOTSUBMITTED)\b", normalized, re.IGNORECASE))
    slash_pair_hits = len(re.findall(r"\b[A-Z][A-Z0-9]{1,7}/[A-Z][A-Z0-9]{1,7}\b", normalized))

    letters = [ch for ch in normalized if ch.isalpha()]
    lowercase_ratio = (sum(1 for ch in letters if ch.islower()) / len(letters)) if letters else 0.0
    word_count = len(normalized.split())

    length_penalty = 0.0
    if len(normalized) > 220:
        length_penalty += min(6.0, (len(normalized) - 220) / 35.0)
    if word_count > 22:
        length_penalty += min(5.0, (word_count - 22) / 5.0)

    score = (
        len(upper_tokens) * 2.0
        + domain_label_hits * 4.0
        + variable_equal_hits * 4.5
        + supp_hits * 3.0
        + not_submitted_hits * 5.0
        + slash_pair_hits * 2.0
        - lowercase_ratio * 2.5
        - length_penalty
    )
    return round(score, 2)


def _passes_annotation_text_gate(text: str, score: float, min_score: float = 1.5) -> bool:
    """Hard gate to keep only annotation-like OCR strings."""
    normalized = _normalize_ocr_text(text)
    if not normalized or score < min_score:
        return False

    if re.search(r"\b(?:NOT\s+SUBMITTED|NOTSUBMITTED)\b", normalized, re.IGNORECASE):
        return True
    if re.search(r"\bSUPP[A-Z]{2,8}\b", normalized):
        return True
    if re.search(r"\b[A-Z][A-Z0-9]{1,7}(?:/[A-Z][A-Z0-9]{1,7})*\s*=", normalized):
        return True
    if re.search(r"\b[A-Z][A-Z0-9]{1,7}\s*\(", normalized):
        return True

    upper_tokens = re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", normalized)
    letters = [ch for ch in normalized if ch.isalpha()]
    lowercase_ratio = (sum(1 for ch in letters if ch.islower()) / len(letters)) if letters else 0.0

    if len(upper_tokens) >= 2 and lowercase_ratio <= 0.45:
        return True
    if len(upper_tokens) == 1 and lowercase_ratio <= 0.2 and len(normalized) <= 14:
        return True
    return False


def _has_strong_unknown_signal(token: str, raw_context: str) -> bool:
    """
    Return True when an unknown token has strong structural evidence.

    This reduces noisy OCR uppercase tokens while keeping potentially useful unknowns.
    """
    upper_token = (token or "").upper().strip()
    if not upper_token:
        return False

    context_upper = (raw_context or "").upper()
    escaped = re.escape(upper_token)

    if re.search(rf"\b{escaped}\s*=", context_upper):
        return True
    if re.search(rf"\b{escaped}\s*[:;,]", context_upper):
        return True
    if re.search(rf"\b{escaped}\s+(?:WHEN|IF|THEN)\b", context_upper):
        return True
    if re.search(rf"\b{escaped}\s*\(", context_upper):
        return True

    # Keep short isolated annotation tokens (e.g., standalone box text).
    if re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", upper_token):
        words = context_upper.split()
        if len(words) <= 2:
            return True
    return False


def _is_one_edit_or_less(left: str, right: str) -> bool:
    """Return True when two tokens are equal or differ by at most one edit."""
    if left == right:
        return True

    left_len = len(left)
    right_len = len(right)
    if abs(left_len - right_len) > 1:
        return False

    if left_len == right_len:
        mismatches = sum(1 for lch, rch in zip(left, right) if lch != rch)
        return mismatches <= 1

    # Ensure `shorter` is actually the shorter token.
    if left_len > right_len:
        left, right = right, left
        left_len, right_len = right_len, left_len

    i = 0
    j = 0
    mismatch_used = False
    while i < left_len and j < right_len:
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        if mismatch_used:
            return False
        mismatch_used = True
        j += 1
    return True


def _find_unique_nearby_standard_term(token: str, standard_variable_terms: Set[str]) -> str:
    """
    Return a unique standard variable that is one edit away from token.

    This is used only as a conservative OCR typo repair helper.
    """
    token = (token or "").upper().strip()
    if not token:
        return ""

    candidates = []
    token_len = len(token)
    for standard in standard_variable_terms:
        if abs(len(standard) - token_len) > 1:
            continue
        if _is_one_edit_or_less(token, standard):
            candidates.append(standard)
            if len(candidates) > 1:
                break
    return candidates[0] if len(candidates) == 1 else ""


def _match_any_pattern(text: str, patterns: List[str]) -> bool:
    """Return True if any regex pattern matches text."""
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False


def _guess_contextual_token_fix(
    token: str,
    context: str,
    standard_variable_terms: Set[str],
    neighbor_token: str = "",
) -> str:
    """
    Guess a repaired token for common OCR first-character loss patterns.

    This stays conservative: only returns candidates present in standard_variable_terms.
    """
    token = (token or "").upper().strip()
    if not token or token in standard_variable_terms:
        return token

    context_upper = (context or "").upper()
    neighbor_upper = (neighbor_token or "").upper()

    direct_rules = [
        ("ACAT", "FACAT", [r"\bDISEASE\s+CHARACTERISTICS\b", r"\bCROHN", r"\bULCERATIVE\b"]),
        ("AOBJ", "FAOBJ", [r"\bFEVER\b", r"\bCROHN", r"\bDISEASE\b"]),
        ("AORRES", "FAORRES", [r"\bFATESTCD\b"]),
        ("OSCAT", "QSCAT", [r"\bIBDQ\b"]),
        ("SORRES", "VSORRES", [r"\bVSTESTCD\b", r"\bVSORRESU\b", r"\bSYSBP\b", r"\bDIABP\b"]),
        ("SSTAT", "RSSTAT", [r"\bRSTESTCD\b", r"\bRSALL\b"]),
        ("STERM", "DSTERM", [r"\bDSDECOD\b", r"\bVOLUNTARY\b", r"\bWITHDRAWAL\b"]),
        ("UOCCUR", "SUOCCUR", [r"\bFORMER\b", r"\bCURRENT\b", r"\bSUST"]),
        ("USTRTPT", "SUSTRTPT", [r"\bFORMER\b", r"\bCURRENT\b", r"\bSUST"]),
    ]
    for source, target, patterns in direct_rules:
        if token != source:
            continue
        if target not in standard_variable_terms:
            continue
        if _match_any_pattern(context_upper, patterns):
            return target

    preferred_prefixes: List[str] = []
    if (
        _match_any_pattern(context_upper, [r"\bFATESTCD\b", r"\bFAORRES\b", r"\bFAOBJ\b", r"\bFACAT\b", r"\bFASCAT\b"])
        or neighbor_upper.startswith("FA")
    ):
        preferred_prefixes.append("F")
    if (
        _match_any_pattern(context_upper, [r"\bVSTESTCD\b", r"\bVSORRES\b", r"\bVSORRESU\b", r"\bSYSBP\b", r"\bDIABP\b"])
        or neighbor_upper.startswith("VS")
    ):
        preferred_prefixes.append("V")
    if _match_any_pattern(context_upper, [r"\bRSTESTCD\b", r"\bRSALL\b", r"\bRSCAT\b"]):
        preferred_prefixes.append("R")
    if _match_any_pattern(context_upper, [r"\bDSDECOD\b", r"\bDSTERM\b", r"\bDISPOSITION\b"]):
        preferred_prefixes.append("D")
    if _match_any_pattern(context_upper, [r"\bSUST", r"\bSUCAT\b", r"\bTOBACCO\b", r"\bFORMER\b", r"\bCURRENT\b"]):
        preferred_prefixes.append("S")
    if _match_any_pattern(context_upper, [r"\bIBDQ\b", r"\bQSCAT\b", r"\bQUESTIONNAIRE\b"]):
        preferred_prefixes.append("Q")

    for prefix in preferred_prefixes:
        candidate = f"{prefix}{token}"
        if candidate in standard_variable_terms:
            return candidate

    nearby = _find_unique_nearby_standard_term(token, standard_variable_terms)
    if nearby:
        return nearby

    leading_candidates = sorted(
        candidate
        for candidate in standard_variable_terms
        if len(candidate) == len(token) + 1 and candidate.endswith(token)
    )
    if len(leading_candidates) == 1:
        return leading_candidates[0]

    if leading_candidates:
        for prefix in preferred_prefixes:
            for candidate in leading_candidates:
                if candidate.startswith(prefix):
                    return candidate

    return token


def _repair_annotation_text(
    text: str,
    standard_variable_terms: Set[str],
    standard_dataset_terms: Set[str] = None,
) -> str:
    """
    Repair common OCR artifacts that drop/split variable names around "=".

    Examples:
    - FASC ALT=...  -> FASCAT=...
    - ON AM=...     -> QNAM=... (in SUPP context)
    - QONAM=...     -> QNAM=... (in SUPP context)
    """
    normalized = _normalize_ocr_text(text)
    if not normalized:
        return normalized

    repaired = normalized
    standard_dataset_terms = standard_dataset_terms or set()
    known_terms = set(standard_variable_terms) | set(standard_dataset_terms)

    # Merge accidental uppercase token splits when the merged token is a known SDTM term.
    split_token_pattern = re.compile(r"\b([A-Z][A-Z0-9]{0,3})\s+([A-Z0-9]{1,7})\b")
    for _ in range(2):
        before = repaired

        def merge_split_token(match: re.Match) -> str:
            left = match.group(1).upper()
            right = match.group(2).upper()
            merged = f"{left}{right}"
            if len(merged) <= 8 and merged in known_terms:
                return merged
            return match.group(0)

        repaired = split_token_pattern.sub(merge_split_token, repaired)
        if repaired == before:
            break

    has_supp_context = bool(re.search(r"\bSUPP[A-Z]{2,8}\b", repaired, re.IGNORECASE))

    if has_supp_context:
        repaired = re.sub(
            r"\b(?:QONAM|ONAM|INAM|JNAM|QDNAM)\s*=",
            "QNAM=",
            repaired,
            flags=re.IGNORECASE,
        )

    split_lhs_pattern = re.compile(r"\b([A-Z]{2,6})\s+([A-Z]{2,8})\s*=")

    def replace_split_lhs(match: re.Match) -> str:
        left_part = match.group(1).upper()
        right_part = match.group(2).upper()
        merged = f"{left_part}{right_part}"

        if len(merged) > 8:
            return match.group(0)

        corrected = merged
        if has_supp_context and right_part in {"QONAM", "ONAM", "INAM", "JNAM", "QDNAM"}:
            corrected = "QNAM"
        elif has_supp_context and right_part == "AM" and left_part in {"QO", "QD", "QN", "ON", "IN", "JN"}:
            corrected = "QNAM"
        elif corrected not in standard_variable_terms:
            nearby = _find_unique_nearby_standard_term(corrected, standard_variable_terms)
            if nearby:
                corrected = nearby

        if corrected == merged and corrected not in standard_variable_terms:
            return match.group(0)
        return f"{corrected}="

    repaired = split_lhs_pattern.sub(replace_split_lhs, repaired)
    context_upper = repaired.upper()

    lhs_assign_pattern = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\s*=")

    def replace_lhs_assign(match: re.Match) -> str:
        lhs = match.group(1).upper()
        corrected = _guess_contextual_token_fix(lhs, context_upper, standard_variable_terms)
        if corrected == lhs:
            return match.group(0)
        return f"{corrected}="

    repaired = lhs_assign_pattern.sub(replace_lhs_assign, repaired)

    conditional_lhs_pattern = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\s+(?=(?:when|if|then)\b)", re.IGNORECASE)

    def replace_conditional_lhs(match: re.Match) -> str:
        lhs = match.group(1).upper()
        corrected = _guess_contextual_token_fix(lhs, context_upper, standard_variable_terms)
        if corrected == lhs:
            return match.group(0)
        return f"{corrected} "

    repaired = conditional_lhs_pattern.sub(replace_conditional_lhs, repaired)

    slash_pair_pattern = re.compile(r"\b([A-Z][A-Z0-9]{1,7})/([A-Z][A-Z0-9]{1,7})\b")

    def replace_slash_pair(match: re.Match) -> str:
        left = match.group(1).upper()
        right = match.group(2).upper()
        fixed_left = _guess_contextual_token_fix(left, context_upper, standard_variable_terms, neighbor_token=right)
        fixed_right = _guess_contextual_token_fix(right, context_upper, standard_variable_terms, neighbor_token=left)
        if fixed_left == left and fixed_right == right:
            return match.group(0)
        return f"{fixed_left}/{fixed_right}"

    repaired = slash_pair_pattern.sub(replace_slash_pair, repaired)
    return _normalize_ocr_text(repaired)


def _extract_lhs_tokens(text: str) -> List[str]:
    """Extract normalized left-hand tokens from VAR=VALUE patterns."""
    return [match.group(1).upper() for match in re.finditer(r"\b([A-Z][A-Z0-9]{1,7})\s*=", text or "")]


def _needs_second_pass_ocr(
    text: str,
    standard_variable_terms: Set[str],
    standard_dataset_terms: Set[str],
) -> bool:
    """Return True when first-pass OCR text contains high-risk corruption patterns."""
    normalized = _normalize_ocr_text(text)
    if not normalized:
        return False

    lhs_tokens = _extract_lhs_tokens(normalized)
    for token in lhs_tokens:
        if token in standard_variable_terms or token in standard_dataset_terms:
            continue
        # Short unknown left-hand variables often indicate OCR truncation (e.g. ACAT vs FASCAT).
        if len(token) <= 4:
            return True

    if re.search(r"\b[A-Z]{2,6}\s+[A-Z]{2,8}\s*=", normalized):
        return True
    if re.search(r"\b(?:QONAM|ONAM|INAM|JNAM|QDNAM)\s*=", normalized):
        return True
    if re.search(r"\bSUPP[A-Z]{2,8}\b", normalized) and not re.search(r"\bQNAM\s*=", normalized):
        return True
    return False


def _ocr_quality_adjustment(
    text: str,
    standard_variable_terms: Set[str],
    standard_dataset_terms: Set[str],
) -> float:
    """
    Extra scoring bias used to choose between first-pass and second-pass OCR results.
    """
    normalized = _normalize_ocr_text(text)
    if not normalized:
        return -5.0

    adjustment = 0.0
    if re.search(r"\bQNAM\s*=", normalized):
        adjustment += 1.0
    if re.search(r"\b[A-Z]{2,6}\s+[A-Z]{2,8}\s*=", normalized):
        adjustment -= 1.2
    if re.search(r"\b(?:QONAM|ONAM|INAM|JNAM|QDNAM)\s*=", normalized):
        adjustment -= 1.0

    lhs_tokens = _extract_lhs_tokens(normalized)
    for token in lhs_tokens:
        if token in standard_variable_terms or token in standard_dataset_terms:
            adjustment += 0.2
        elif len(token) <= 4:
            adjustment -= 0.9
        else:
            adjustment -= 0.4
    return adjustment


def _run_second_pass_ocr(
    gray: np.ndarray,
    language: str,
    tiny_roi: bool,
    standard_variable_terms: Set[str],
    standard_dataset_terms: Set[str],
) -> str:
    """
    Run a slower OCR pass for suspicious first-pass results only.
    """
    second_variants: List[np.ndarray] = []

    try:
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        second_variants.append(adaptive)
    except Exception:
        pass

    try:
        upscaled = cv2.resize(gray, None, fx=1.35, fy=1.35, interpolation=cv2.INTER_CUBIC)
        _, upscaled_otsu = cv2.threshold(
            upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        second_variants.append(upscaled_otsu)
    except Exception:
        pass

    if not second_variants:
        return ""

    configs = [r"--psm 7 --oem 3"] if tiny_roi else [r"--psm 7 --oem 3", r"--psm 6 --oem 3"]
    best_text = ""
    best_score = -999.0

    for processed in second_variants:
        for config in configs:
            try:
                text = _quick_ocr_text(processed, language, config)
            except Exception:
                continue
            if not text:
                continue
            score = _score_annotation_text(text) + _ocr_quality_adjustment(
                text,
                standard_variable_terms,
                standard_dataset_terms,
            )
            if score > best_score or (score == best_score and len(text) > len(best_text)):
                best_score = score
                best_text = text

    return best_text


def _extract_ocr_text_with_confidence(image: np.ndarray, language: str, config: str) -> Tuple[str, float]:
    """Run OCR once and return normalized text plus mean confidence."""
    data = pytesseract.image_to_data(
        image, lang=language, config=config, output_type=pytesseract.Output.DICT
    )

    texts = data.get("text", [])
    confs = data.get("conf", [])

    words = []
    valid_conf_values = []
    for raw_text, raw_conf in zip(texts, confs):
        token = (raw_text or "").strip()
        if token:
            words.append(token)
        try:
            confidence = float(raw_conf)
        except (TypeError, ValueError):
            continue
        if confidence >= 0 and token:
            valid_conf_values.append(confidence)

    merged_text = _normalize_ocr_text(" ".join(words))
    mean_conf = (
        round(sum(valid_conf_values) / len(valid_conf_values), 2)
        if valid_conf_values else 0.0
    )
    return merged_text, mean_conf


def _quick_ocr_text(image: np.ndarray, language: str, config: str) -> str:
    """Run lightweight OCR and return normalized text without confidence parsing."""
    raw_text = pytesseract.image_to_string(image, lang=language, config=config)
    return _normalize_ocr_text(raw_text)


def detect_annotations_opencv(page_image: np.ndarray, min_box_area: int = 50) -> List[Dict[str, Any]]:
    """
    Detect annotated regions by prioritizing colored rectangle backgrounds.

    Strategy:
    1. Build a colored-background mask (hard gate).
    2. Keep contours that are rectangle-like and reasonably sized.
    3. Use border edge evidence as a confidence boost.
    4. Deduplicate overlapping boxes by IoU.

    Args:
        page_image: Image array from PyMuPDF page.get_pixmap()
        min_box_area: Minimum pixel area to consider as annotation (default 50)

    Returns:
        List of detected boxes with OCR candidate metadata.
    """
    detected_boxes = []

    try:
        if page_image is None or page_image.size == 0:
            return detected_boxes

        gray = cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(page_image, cv2.COLOR_BGR2HSV)
        edges = cv2.Canny(gray, 40, 140)

        # Hard gate: keep regions with visible color fill.
        lower_colored = np.array([0, 18, 105], dtype=np.uint8)
        upper_colored = np.array([180, 255, 255], dtype=np.uint8)
        color_mask = cv2.inRange(hsv, lower_colored, upper_colored)

        # Remove thin text strokes and close fragmented fill areas.
        open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5))
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)

        contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        page_area = page_image.shape[0] * page_image.shape[1]
        candidate_boxes: List[Dict[str, Any]] = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < max(min_box_area, 120):
                continue

            x, y, w, h = cv2.boundingRect(contour)
            rect_area = w * h

            if w < 24 or h < 10:
                continue
            if rect_area <= 0:
                continue
            if rect_area > page_area * 0.18:
                continue
            if w <= 26 and h <= 26 and area < 320:
                # Most tiny near-square contours are checkbox markers, not annotation text boxes.
                continue

            aspect_ratio = max(w, h) / min(w, h)
            if aspect_ratio > 35:
                continue

            fill_ratio = area / rect_area
            if fill_ratio < 0.35:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
            if len(approx) > 10:
                continue

            roi_mask = color_mask[y:y + h, x:x + w]
            colored_ratio = cv2.countNonZero(roi_mask) / rect_area
            if colored_ratio < 0.40:
                continue

            # Border evidence from edge density in a thin border band.
            band = np.zeros((h, w), dtype=np.uint8)
            border_thickness = max(1, min(3, min(w, h) // 10))
            cv2.rectangle(band, (0, 0), (w - 1, h - 1), 255, border_thickness)
            roi_edges = edges[y:y + h, x:x + w]
            band_pixels = cv2.countNonZero(band)
            edge_band_pixels = cv2.countNonZero(cv2.bitwise_and(roi_edges, band))
            border_density = (edge_band_pixels / band_pixels) if band_pixels > 0 else 0.0

            confidence = (
                0.50 * colored_ratio
                + 0.35 * fill_ratio
                + 0.15 * min(border_density * 8.0, 1.0)
            )
            if confidence < 0.42:
                continue

            if border_density >= 0.12:
                detection_type = "solid_border"
            elif border_density >= 0.05:
                detection_type = "dashed_border"
            else:
                detection_type = "colored_bg"

            candidate_boxes.append({
                "rect": (x, y, w, h),
                "confidence": min(1.0, float(round(confidence, 3))),
                "type": detection_type,
                "fill_ratio": round(fill_ratio, 3),
                "colored_ratio": round(colored_ratio, 3),
                "border_density": round(border_density, 3),
            })

        # Deduplicate by IoU (keep higher-confidence boxes).
        candidate_boxes.sort(key=lambda item: item["confidence"], reverse=True)
        for candidate in candidate_boxes:
            if any(
                _compute_rect_iou(candidate["rect"], kept["rect"]) > 0.45
                for kept in detected_boxes
            ):
                continue
            detected_boxes.append(candidate)

        # Guardrail for OCR cost on noisy pages.
        max_boxes_per_page = 36
        if len(detected_boxes) > max_boxes_per_page:
            detected_boxes = detected_boxes[:max_boxes_per_page]

    except Exception as e:
        # Log but don't fail - return empty list if detection fails
        pass

    return detected_boxes


def extract_text_ocr(
    page_image: np.ndarray,
    rect: Tuple[int, int, int, int],
    margin: int = 5,
    language: str = "eng",
    debug: bool = False,
    standard_variable_terms: Set[str] = None,
    standard_dataset_terms: Set[str] = None,
) -> str:
    """
    Extract text from a region using Tesseract OCR.

    Preprocessing steps:
    1. Shrink region to avoid neighboring body text
    2. Extract region with a small margin
    3. Convert to grayscale
    4. Apply multiple binarization approaches
    5. Run lightweight OCR to find likely annotation text
    6. Run confidence OCR only for top candidates
    7. Return best result

    Args:
        page_image: Full page image
        rect: (x, y, w, h) bounding rectangle
        margin: Small post-shrink margin to retain annotation border glyphs
        language: Tesseract language code (default "eng")
        debug: If True, save debug images

    Returns:
        Extracted text string (may be empty if OCR fails)
    """
    try:
        standard_variable_terms = standard_variable_terms or set()
        standard_dataset_terms = standard_dataset_terms or set()
        x, y, w, h = rect

        # Shrink ROI first to avoid neighboring body text.
        # Keep horizontal shrink minimal to avoid dropping leading characters.
        inset_x = max(0, int(w * 0.005))
        inset_y = max(0, int(h * 0.06))
        if (w - 2 * inset_x) >= 10 and (h - 2 * inset_y) >= 8:
            x += inset_x
            y += inset_y
            w -= 2 * inset_x
            h -= 2 * inset_y

        # Add small margin with bounds checking (default callers may pass 0 or 1).
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(page_image.shape[1], x + w + margin)
        y2 = min(page_image.shape[0], y + h + margin)

        # Extract region
        region = page_image[y1:y2, x1:x2]

        if region.size == 0:
            return ""

        # Convert to grayscale
        if len(region.shape) == 3:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        else:
            gray = region

        tiny_roi = w < 70 or h < 24
        ocr_gray = gray
        if tiny_roi:
            ocr_gray = cv2.resize(gray, None, fx=1.45, fy=1.45, interpolation=cv2.INTER_CUBIC)

        variants: List[np.ndarray] = [ocr_gray]

        _, binary_otsu = cv2.threshold(ocr_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        variants.append(cv2.dilate(binary_otsu, kernel, iterations=1))

        # Adaptive threshold is helpful but relatively expensive; use as fallback only.
        if tiny_roi:
            quick_configs = [
                r"--psm 7 --oem 3",
                rf"--psm 8 --oem 3 -c tessedit_char_whitelist={OCR_SHORT_TOKEN_WHITELIST}",
                rf"--psm 13 --oem 3 -c tessedit_char_whitelist={OCR_SHORT_TOKEN_WHITELIST}",
            ]
        else:
            quick_configs = [
                r"--psm 6 --oem 3",
                r"--psm 7 --oem 3",
            ]
        primary_config = quick_configs[0]

        quick_candidates = []
        for processed in variants:
            for config in quick_configs:
                try:
                    quick_text = _quick_ocr_text(processed, language, config)
                except Exception:
                    continue
                if not quick_text:
                    continue
                quick_score = _score_annotation_text(quick_text)
                quick_candidates.append({
                    "text": quick_text,
                    "score": quick_score,
                    "image": processed,
                    "config": config,
                })

        if not quick_candidates:
            try:
                binary_adaptive = cv2.adaptiveThreshold(
                    ocr_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                processed = cv2.dilate(binary_adaptive, kernel, iterations=1)
                quick_text = _quick_ocr_text(processed, language, primary_config)
                if quick_text:
                    quick_candidates.append({
                        "text": quick_text,
                        "score": _score_annotation_text(quick_text),
                        "image": processed,
                        "config": primary_config,
                    })
            except Exception:
                pass

        if not quick_candidates:
            return ""

        quick_candidates.sort(
            key=lambda item: (item["score"], -len(item["text"])),
            reverse=True
        )
        best_quick = quick_candidates[0]
        best_quick_text = best_quick["text"].strip().strip("[]|;:,")
        second_gap = (
            best_quick["score"] - quick_candidates[1]["score"]
            if len(quick_candidates) > 1 else 99.0
        )

        # For likely-noise text, skip expensive confidence OCR and return quick result.
        if best_quick["score"] < 1.5:
            return best_quick["text"]

        # Fast path for unambiguous short tokens (common annotation case).
        if (
            best_quick["score"] >= 2.0
            and second_gap >= 0.8
            and re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", best_quick_text)
        ):
            return best_quick_text

        confidence_candidates = [best_quick]
        if len(quick_candidates) > 1:
            second = quick_candidates[1]
            if best_quick["score"] - second["score"] <= 1.0:
                confidence_candidates.append(second)

        results = []
        for candidate in confidence_candidates:
            try:
                conf_text, confidence = _extract_ocr_text_with_confidence(
                    candidate["image"], language, candidate["config"]
                )
            except Exception:
                conf_text, confidence = "", 0.0

            final_text = conf_text if conf_text else candidate["text"]
            annotation_score = _score_annotation_text(final_text)
            total_score = (
                annotation_score * 10.0
                + confidence
                + _ocr_quality_adjustment(
                    final_text,
                    standard_variable_terms,
                    standard_dataset_terms,
                )
            )
            results.append((total_score, annotation_score, confidence, final_text))

        if results:
            results.sort(key=lambda item: (item[0], item[1], item[2], -len(item[3])), reverse=True)
            best_total, _, _, best_text = results[0]
            if best_total < 0 and len(best_text.split()) > 10:
                return ""

            best_text = _normalize_ocr_text(best_text)
            if _needs_second_pass_ocr(
                best_text,
                standard_variable_terms,
                standard_dataset_terms,
            ):
                second_pass_text = _run_second_pass_ocr(
                    gray,
                    language,
                    tiny_roi,
                    standard_variable_terms,
                    standard_dataset_terms,
                )
                if second_pass_text:
                    first_score = _score_annotation_text(best_text) + _ocr_quality_adjustment(
                        best_text,
                        standard_variable_terms,
                        standard_dataset_terms,
                    )
                    second_score = _score_annotation_text(second_pass_text) + _ocr_quality_adjustment(
                        second_pass_text,
                        standard_variable_terms,
                        standard_dataset_terms,
                    )
                    if second_score >= first_score + 0.35:
                        return second_pass_text
            return best_text

        return ""

    except Exception as e:
        return ""


def extract_candidates(text: str) -> Set[str]:
    """
    Extract candidate terms (potential variable/dataset names) from text.
    IDENTICAL to PyMuPDF version for consistency.

    Uses capitalization rule and length constraints.
    More conservative approach to reduce false positives.

    Args:
        text: Text to extract from

    Returns:
        Set of candidate terms
    """
    candidates = set()
    equal_value_spans = []

    # Heuristic: tokens on the right side of "=" are usually values, not variable/domain names.
    for match in re.finditer(r'=\s*([A-Z0-9][A-Z0-9\s/\-]{0,80})', text):
        value_text = match.group(1).rstrip()
        if not value_text:
            continue
        span_start = match.start(1)
        span_end = span_start + len(value_text)
        equal_value_spans.append((span_start, span_end))

    def is_in_equal_value(pos: int) -> bool:
        for start, end in equal_value_spans:
            if start <= pos < end:
                return True
        return False

    # Rule: Capitalized terms (all caps)
    # Length: 2-8 characters (standard SDTM constraint)

    # Pattern 1: All-caps words surrounded by boundaries
    # Match sequences of uppercase letters and digits (2-8 chars)
    for match in re.finditer(r'\b([A-Z][A-Z0-9]{1,7})\b', text):
        token = match.group(1)
        if 2 <= len(token) <= 8:
            if is_in_equal_value(match.start(1)):
                continue
            # Require fully uppercase token to avoid capturing capitalized words like 'And'
            if not token.isupper():
                continue
            # Skip common stopwords and configured blacklist
            if token.upper() in DEFAULT_STOPWORDS or token.upper() in CONFIG.get("blacklist", set()):
                continue
            candidates.add(token)

    # Pattern 2: Explicit variable references in conditions
    # "VAR when", "VAR if", "VAR then", "VAR =", "VAR :", etc
    for match in re.finditer(r'\b([A-Z][A-Z0-9]{1,7})\s+(?:when|if|then|=|:|;|,)', text):
        token = match.group(1)
        if 2 <= len(token) <= 8:
            if is_in_equal_value(match.start(1)):
                continue
            if not token.isupper():
                continue
            if token.upper() in DEFAULT_STOPWORDS or token.upper() in CONFIG.get("blacklist", set()):
                continue
            candidates.add(token)

    return candidates


def classify_term(term: str, raw_context: str, standard_terms: Dict,
                  suffix_prefix_patterns: Dict, blacklist: Set) -> Tuple[str, str]:
    """
    Classify a term and return (category, match_level).
    IDENTICAL to PyMuPDF version for consistency.

    Category: semantic class (standard_variable, dataset_name, supp_variable, not_submitted, unknown)
    Match level: how it was matched (exact | suffix_prefix | supp | none)

    Priority used by caller: prefer higher match_level when multiple occurrences exist.
    """
    upper_term = term.upper()

    # Level 1: Blacklist check
    if upper_term in blacklist:
        return "blacklist", "none"

    # Level 2: NOT SUBMITTED check
    if "NOT" in upper_term and "SUBMITTED" in upper_term:
        return "not_submitted", "none"

    # Heuristic: token followed by explanatory parentheses in the raw context -> likely a domain label (e.g., 'AE (Adverse Events)')
    if raw_context and re.search(r'\b' + re.escape(upper_term) + r'\s*\(', raw_context, re.IGNORECASE):
        return "dataset_name", "exact"

    # Level 3: Exact match in standard_term.csv (prefer dataset exact for short tokens)
    if upper_term in standard_terms.get("dataset", set()):
        return "dataset_name", "exact"
    if upper_term in standard_terms.get("variable", set()):
        return "standard_variable", "exact"

    # Level 4: Suffix/prefix match in standard_term_suffix_prefix.csv
    suffix_prefix = suffix_prefix_patterns.get("variable", set())
    for pattern in suffix_prefix:
        if not pattern:
            continue
        if pattern.startswith("--"):
            suffix = pattern[2:]
            if not suffix:
                continue
            if upper_term.endswith(suffix):
                return "standard_variable", "suffix_prefix"
        if pattern.endswith("--"):
            prefix = pattern[:-2]
            if not prefix:
                continue
            if upper_term.startswith(prefix):
                return "standard_variable", "suffix_prefix"

    suffix_prefix = suffix_prefix_patterns.get("dataset", set())
    for pattern in suffix_prefix:
        if not pattern:
            continue
        if pattern.startswith("--"):
            suffix = pattern[2:]
            if not suffix:
                continue
            if upper_term.endswith(suffix):
                return "dataset_name", "suffix_prefix"
        if pattern.endswith("--"):
            prefix = pattern[:-2]
            if not prefix:
                continue
            if upper_term.startswith(prefix):
                return "dataset_name", "suffix_prefix"

    # Level 5: SUPP variable check (e.g., AEPTRTPT in SUPPAE context)
    supp_pattern = r'\bSUPP[A-Z]{2,8}\b'
    if re.search(supp_pattern, raw_context):
        return "supp_variable", "supp"

    # Level 6: Unknown
    return "unknown", "none"


def parse_supp_variable(text: str) -> List[Tuple[str, str]]:
    """
    Extract SUPP-related variable-dataset pairs from text.
    IDENTICAL to PyMuPDF version for consistency.

    Handles formats like:
    - 'AEPTRTPT in SUPPAE'
    - 'SUPPAE.AEPTRTPT'
    - 'AEPTRTPT in SUPPxx'

    Args:
        text: Annotation text to parse

    Returns:
        List of (variable, dataset) tuples
    """
    results: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    def add_pair(var_value: str, dataset_value: str) -> None:
        var = (var_value or "").upper().strip()
        dataset = (dataset_value or "").upper().strip()
        if not var or not dataset:
            return
        if len(var) > 8 or len(dataset) > 8:
            return
        key = (var, dataset)
        if key in seen:
            return
        seen.add(key)
        results.append(key)

    # Pattern 0: "QNAM=AEHOSPDT in SUPPAE" -> capture (QNAM, SUPPAE)
    pattern0 = r'([A-Z][A-Z0-9]{1,7})\s*=\s*([A-Z0-9][A-Z0-9\s/\-]{0,80}?)\s+in\s+(SUPP[A-Z]{2,8})\b'
    for match in re.finditer(pattern0, text, re.IGNORECASE):
        lhs = match.group(1)
        value = re.sub(r'\s{2,}', ' ', (match.group(2) or '').strip()).upper()
        dataset = match.group(3)
        add_pair(lhs, dataset)
        # SUPP records commonly encode variable names in QNAM=VALUE.
        if lhs.upper() == "QNAM" and re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", value):
            add_pair(value, dataset)

    # Pattern 1: "VAR in SUPPYY" or "VAR in SUPPxx"
    # Negative lookbehind avoids matching value side in "QNAM=OTHLOC in SUPPFA".
    pattern1 = r'(?<![=A-Z0-9])([A-Z][A-Z0-9]{1,7})\s+in\s+(SUPP[A-Z]{2,8})\b'
    for match in re.finditer(pattern1, text, re.IGNORECASE):
        add_pair(match.group(1), match.group(2))

    # Pattern 2: "SUPPYY.VAR"
    pattern2 = r'(SUPP[A-Z]{2,8})\.([A-Z][A-Z0-9]{1,7})(?:\s|$|[,;])'
    for match in re.finditer(pattern2, text, re.IGNORECASE):
        add_pair(match.group(2), match.group(1))

    return results


def extract_variable_value_pairs(text: str) -> List[Tuple[str, str, str]]:
    """
    Extract VARIABLE=VALUE pairs from annotation text.
    IDENTICAL to PyMuPDF version for consistency.

    Supports shared-value syntax like DSDECOD/DSTERM=COMPLETED.

    Returns:
        List of tuples: (variable_name, value_text, combined_pair_text)
    """
    pairs = []
    pattern = r'([A-Z][A-Z0-9]{1,7}(?:/[A-Z][A-Z0-9]{1,7})*)\s*=\s*([A-Z0-9][A-Z0-9\s/\-]{0,80}?)(?=\s+(?:when|if|then)\b|\s*\||\s*;|$)'
    for match in re.finditer(pattern, text):
        lhs = match.group(1).strip()
        value = re.sub(r'\s{2,}', ' ', match.group(2).strip())
        if not lhs or not value:
            continue
        left_vars = [x.strip().upper() for x in lhs.split("/") if x.strip()]
        for var in left_vars:
            if 2 <= len(var) <= 8:
                if var == "VSSTAT" and value == "NOT DONE":
                    continue
                pairs.append((var, value, f"{var}={value}"))

    # SUPP annotations often use the shape "QNAM=AEHOSPDT in SUPPAE".
    # Capture the variable/value pair before the trailing dataset phrase.
    supp_pattern = r'([A-Z][A-Z0-9]{1,7}(?:/[A-Z][A-Z0-9]{1,7})*)\s*=\s*([A-Z0-9][A-Z0-9\s/\-]{0,80}?)\s+in\s+(SUPP[A-Z]{2,8})\b'
    for match in re.finditer(supp_pattern, text):
        lhs = match.group(1).strip()
        value = re.sub(r'\s{2,}', ' ', match.group(2).strip())
        if not lhs or not value:
            continue
        left_vars = [x.strip().upper() for x in lhs.split("/") if x.strip()]
        for var in left_vars:
            if 2 <= len(var) <= 8:
                if var == "VSSTAT" and value == "NOT DONE":
                    continue
                pairs.append((var, value, f"{var}={value}"))
    return pairs


def extract_not_submitted_entries(text: str, page_number: int) -> List[Dict[str, Any]]:
    """
    Extract NOT SUBMITTED annotations.
    IDENTICAL to PyMuPDF version for consistency.

    Handles variants: NOT SUBMITTED, Not Submitted, NOTSUBMITTED, etc.
    Returns all occurrences (no deduplication) per page.

    Args:
        text: Text to search
        page_number: Page number for tracking

    Returns:
        List of {"Page": int, "Count": int} dicts
    """
    pattern = r'\b(?:NOT\s+SUBMITTED|NOTSUBMITTED)\b'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))

    if matches:
        return [{"Page": page_number, "Count": len(matches)}]
    return []


def extract_variables_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract variables and annotations from PDF using OpenCV + OCR.

    Strategy:
    1. For each page:
       a. Render page to image
       b. Detect annotated boxes using contour analysis
       c. Extract text via Tesseract OCR
       d. Classify terms using priority rules
    2. Aggregate by variable
    3. Format output identical to PyMuPDF

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        Dict with structure (identical to PyMuPDF):
        {
            "status": "success" | "error",
            "variables": list of variable records,
            "domain_annotations": list of domain occurrences,
            "not_submitted": included in variables list,
            "summary": dict with metadata,
            "error_message": str or None
        }
    """
    start_time = time.time()
    doc = None

    try:
        tesseract_ok, tesseract_error = is_tesseract_available()
        if not tesseract_ok:
            elapsed = round(time.time() - start_time, 2)
            return {
                "status": "error",
                "variables": [],
                "domain_annotations": [],
                "summary": {
                    "processing_time_seconds": elapsed,
                    "extraction_method": "opencv_ocr"
                },
                "debug_info": {
                    "total_pages": 0,
                    "pages_processed": 0,
                    "total_boxes_detected": 0,
                    "boxes_per_page": [],
                    "roi_prefilter_skipped_count": 0,
                    "ocr_success_count": 0,
                    "ocr_fail_count": 0,
                    "ocr_noise_rejected_count": 0,
                    "variables_extracted": 0
                },
                "error_message": f"Tesseract OCR engine not available: {tesseract_error}"
            }

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Load config
        standard_terms = CONFIG.get("standard_terms", {"variable": set(), "dataset": set()})
        suffix_prefix_patterns = CONFIG.get("suffix_prefix_patterns", {"variable": set(), "dataset": set()})
        blacklist = CONFIG.get("blacklist", set())

        # Result containers
        variable_index = defaultdict(lambda: {
            "pages": set(),
            "raw_contexts": [],
            "category": "unknown",
            "match_level": "none"
        })

        domain_index = defaultdict(set)
        not_submitted_entries = []

        # Debug tracking
        debug_info = {
            "total_pages": len(doc),
            "pages_processed": 0,
            "total_boxes_detected": 0,
            "boxes_per_page": [],
            "roi_prefilter_skipped_count": 0,
            "ocr_success_count": 0,
            "ocr_fail_count": 0,
            "ocr_noise_rejected_count": 0,
            "variables_extracted": 0
        }

        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_idx = page_num + 1

            # ==================== Render page to image ====================
            # Use 300 DPI for better short-code recognition accuracy
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            page_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))

            # Convert RGB/RGBA to BGR for OpenCV
            if pix.n == 4:  # RGBA
                page_image = cv2.cvtColor(page_image, cv2.COLOR_RGBA2BGR)
            else:  # RGB
                page_image = cv2.cvtColor(page_image, cv2.COLOR_RGB2BGR)

            # ==================== Detect annotations ====================
            detected_boxes = detect_annotations_opencv(page_image, min_box_area=100)

            debug_info["pages_processed"] += 1
            debug_info["total_boxes_detected"] += len(detected_boxes)
            debug_info["boxes_per_page"].append({
                "page": page_idx,
                "boxes_count": len(detected_boxes)
            })

            # ==================== Extract text from each box ====================
            for box_info in detected_boxes:
                rect = box_info["rect"]
                x, y, w, h = rect
                aspect_ratio = max(w, h) / max(1, min(w, h))
                border_density = float(box_info.get("border_density", 0.0))

                # Fast prefilter: skip very wide, short strips that mostly come from row headers/body bands.
                if h <= 19 and w >= 140 and aspect_ratio >= 7.5 and border_density < 0.35:
                    debug_info["roi_prefilter_skipped_count"] += 1
                    continue

                # Extract text via OCR
                ocr_text = extract_text_ocr(
                    page_image,
                    rect,
                    margin=2,
                    standard_variable_terms=standard_terms.get("variable", set()),
                    standard_dataset_terms=standard_terms.get("dataset", set()),
                )

                if not ocr_text or len(ocr_text.strip()) < 2:
                    debug_info["ocr_fail_count"] += 1
                    continue

                repaired_text = _repair_annotation_text(
                    ocr_text,
                    standard_terms.get("variable", set()),
                    standard_terms.get("dataset", set()),
                )
                if repaired_text:
                    first_score = _score_annotation_text(ocr_text) + _ocr_quality_adjustment(
                        ocr_text,
                        standard_terms.get("variable", set()),
                        standard_terms.get("dataset", set()),
                    )
                    repaired_score = _score_annotation_text(repaired_text) + _ocr_quality_adjustment(
                        repaired_text,
                        standard_terms.get("variable", set()),
                        standard_terms.get("dataset", set()),
                    )
                    if repaired_score >= first_score:
                        ocr_text = repaired_text
                        ocr_text_score = _score_annotation_text(ocr_text)
                    else:
                        ocr_text_score = _score_annotation_text(ocr_text)
                else:
                    ocr_text_score = _score_annotation_text(ocr_text)

                if not _passes_annotation_text_gate(ocr_text, ocr_text_score, min_score=1.8):
                    debug_info["ocr_noise_rejected_count"] += 1
                    continue

                debug_info["ocr_success_count"] += 1

                # ==================== Extract NOT SUBMITTED entries ====================
                not_sub_list = extract_not_submitted_entries(ocr_text, page_idx)
                not_submitted_entries.extend(not_sub_list)

                # ==================== Extract candidates ====================
                candidates = extract_candidates(ocr_text)

                # Extract SUPP variable pairs
                supp_pairs = parse_supp_variable(ocr_text)
                for var, dataset in supp_pairs:
                    candidates.add(var)
                    candidates.add(dataset)

                # Extract VARIABLE=VALUE pairs
                value_pairs = extract_variable_value_pairs(ocr_text)
                for left_var, _, pair_text in value_pairs:
                    normalized_left = left_var
                    if normalized_left not in standard_terms.get("variable", set()):
                        nearby_left = _find_unique_nearby_standard_term(
                            normalized_left,
                            standard_terms.get("variable", set()),
                        )
                        if nearby_left:
                            normalized_left = nearby_left
                            pair_text = re.sub(
                                rf"^{re.escape(left_var)}=",
                                f"{normalized_left}=",
                                pair_text,
                                flags=re.IGNORECASE,
                            )

                    category, match_level = classify_term(
                        normalized_left, ocr_text, standard_terms,
                        suffix_prefix_patterns, blacklist
                    )
                    if normalized_left in standard_terms.get("dataset", set()) and category != "not_submitted":
                        category = "dataset_name"
                        if match_level == "none":
                            match_level = "exact"
                    if category == "blacklist":
                        continue

                    variable_index[pair_text]["pages"].add(page_idx)
                    variable_index[pair_text]["raw_contexts"].append(ocr_text.strip())

                    current_level = variable_index[pair_text].get("match_level", "none")
                    priority = {"exact": 3, "suffix_prefix": 2, "supp": 1, "none": 0}
                    new_priority = priority.get(match_level, -1)
                    current_priority = priority.get(current_level, -1)
                    if new_priority > current_priority:
                        variable_index[pair_text]["category"] = category
                        variable_index[pair_text]["match_level"] = match_level
                    elif new_priority == current_priority and category != "unknown":
                        current_category = variable_index[pair_text].get("category", "unknown")
                        category_rank = {
                            "dataset_name": 3,
                            "not_submitted": 3,
                            "standard_variable": 2,
                            "supp_variable": 1,
                            "unknown": 0
                        }
                        if category_rank.get(category, 0) >= category_rank.get(current_category, 0):
                            variable_index[pair_text]["category"] = category

                # Classify each candidate
                for candidate in candidates:
                    if not candidate or len(candidate) < 2 or len(candidate) > 8:
                        continue

                    upper_cand = candidate.upper()
                    if upper_cand not in standard_terms.get("variable", set()):
                        nearby_cand = _find_unique_nearby_standard_term(
                            upper_cand,
                            standard_terms.get("variable", set()),
                        )
                        if nearby_cand:
                            upper_cand = nearby_cand

                    category, match_level = classify_term(
                        upper_cand, ocr_text, standard_terms,
                        suffix_prefix_patterns, blacklist
                    )

                    # Prefer dataset classification when the term is a known dataset token.
                    if upper_cand in standard_terms.get("dataset", set()) and category != "not_submitted":
                        category = "dataset_name"
                        if match_level == "none":
                            match_level = "exact"
                        # Track domain annotations
                        domain_index[upper_cand].add(page_idx)
                    elif category == "dataset_name" and upper_cand not in standard_terms.get("dataset", set()):
                        context_upper = (ocr_text or "").upper()
                        if not (
                            upper_cand.startswith("SUPP")
                            or re.search(rf"\b{re.escape(upper_cand)}\s*(?:=|\()", context_upper)
                        ):
                            category = "unknown"
                            match_level = "none"

                    # Skip blacklist items
                    if category == "blacklist":
                        continue

                    if category == "unknown" and not _has_strong_unknown_signal(upper_cand, ocr_text):
                        continue
                    if (
                        category == "standard_variable"
                        and len(upper_cand) <= 3
                        and upper_cand not in standard_terms.get("dataset", set())
                        and not _has_strong_unknown_signal(upper_cand, ocr_text)
                    ):
                        continue
                    if (
                        match_level == "suffix_prefix"
                        and len(upper_cand) <= 2
                        and upper_cand not in standard_terms.get("dataset", set())
                        and not _has_strong_unknown_signal(upper_cand, ocr_text)
                    ):
                        continue
                    if (
                        category == "dataset_name"
                        and len(upper_cand) <= 2
                        and upper_cand not in standard_terms.get("dataset", set())
                        and not _has_strong_unknown_signal(upper_cand, ocr_text)
                    ):
                        continue

                    # Record this occurrence
                    variable_index[upper_cand]["pages"].add(page_idx)
                    variable_index[upper_cand]["raw_contexts"].append(ocr_text.strip())

                    # Update category and match_level with priority logic
                    current_level = variable_index[upper_cand].get("match_level", "none")
                    priority = {"exact": 3, "suffix_prefix": 2, "supp": 1, "none": 0}
                    new_priority = priority.get(match_level, -1)
                    current_priority = priority.get(current_level, -1)

                    if new_priority > current_priority:
                        variable_index[upper_cand]["category"] = category
                        variable_index[upper_cand]["match_level"] = match_level
                    elif new_priority == current_priority and category != "unknown":
                        current_category = variable_index[upper_cand].get("category", "unknown")
                        category_rank = {
                            "dataset_name": 3,
                            "not_submitted": 3,
                            "standard_variable": 2,
                            "supp_variable": 1,
                            "unknown": 0
                        }
                        if category_rank.get(category, 0) >= category_rank.get(current_category, 0):
                            variable_index[upper_cand]["category"] = category

        # ==================== Build final variable list ====================
        variables_list = []
        for var, info in sorted(variable_index.items()):
            pages = sorted(info["pages"])

            # Deduplicate raw contexts while preserving order
            unique_raw = []
            seen_raw = set()
            for raw in info["raw_contexts"]:
                if raw not in seen_raw:
                    seen_raw.add(raw)
                    unique_raw.append(raw)

            variables_list.append({
                "Variable": var,
                "Pages": pages,
                "PageString": ",".join(map(str, pages)),
                "PageCount": len(pages),
                "RawTexts": unique_raw,
                "Category": info["category"],
                "MatchLevel": info.get("match_level", "none")
            })

        # ==================== Build domain annotation list ====================
        domain_list = []
        for dom, pages in sorted(domain_index.items()):
            page_list = sorted(pages)
            domain_list.append({
                "Domain": dom,
                "Pages": page_list,
                "PageString": ",".join(map(str, page_list)),
                "PageCount": len(page_list)
            })

        # ==================== Aggregate NOT SUBMITTED ====================
        pages_sequence = []
        for entry in not_submitted_entries:
            pages_sequence.extend([entry["Page"]] * entry.get("Count", 1))

        not_sub_list = []
        if pages_sequence:
            not_sub_list.append({
                "Variable": "NOT SUBMITTED",
                "Pages": pages_sequence,
                "PageString": ",".join(map(str, pages_sequence)),
                "PageCount": len(pages_sequence),
                "Count": len(pages_sequence),
                "RawTexts": [],
                "Category": "not_submitted",
                "MatchLevel": ""
            })

        # Combine variable list with NOT SUBMITTED entries
        final_variables = variables_list + not_sub_list

        elapsed = round(time.time() - start_time, 2)

        debug_info["variables_extracted"] = len(variables_list)

        return {
            "status": "success",
            "variables": final_variables,
            "domain_annotations": domain_list,
            "summary": {
                "total_variables": len(variables_list),
                "total_not_submitted_entries": len(not_sub_list),
                "total_pages": len(doc),
                "processing_time_seconds": elapsed,
                "processing_time": elapsed,
                "extraction_method": "opencv_ocr"
            },
            "debug_info": debug_info,
            "error_message": None
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        return {
            "status": "error",
            "variables": [],
            "domain_annotations": [],
            "summary": {
                "processing_time_seconds": elapsed,
                "extraction_method": "opencv_ocr"
            },
            "error_message": str(e)
        }

    finally:
        if doc is not None:
            doc.close()


if __name__ == "__main__":
    print("✅ OpenCV+OCR Parser Module Loaded Successfully (VERSION 2.0 - OCR refactoring release)")
