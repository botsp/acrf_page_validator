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


def detect_annotations_opencv(page_image: np.ndarray, min_box_area: int = 50) -> List[Dict[str, Any]]:
    """
    Detect annotated regions (colored boxes with text) using contour analysis.

    Strategy:
    1. Use multiple detection methods for robustness:
       - Color-based: detect non-white/non-gray backgrounds
       - Edge-based: detect borders via Canny + dilation
    2. Apply morphological operations to close gaps in box borders
    3. Find contours and filter by area/aspect ratio
    4. Return bounding rectangles with confidence estimate

    Args:
        page_image: Image array from PyMuPDF page.get_pixmap()
        min_box_area: Minimum pixel area to consider as annotation (default 50)

    Returns:
        List of detected boxes: [{"rect": (x, y, w, h), "confidence": float, "type": str}, ...]
        Types: "solid_border", "dashed_border", "colored_bg", "text_region"
    """
    detected_boxes = []

    try:
        gray = cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)

        # ==================== Method 1: Edge detection ====================
        # Detect box borders using Canny edge detection
        edges = cv2.Canny(gray, 30, 150)

        # Dilate edges to connect broken lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        edges_dilated = cv2.dilate(edges, kernel, iterations=3)

        # Close small gaps
        edges_closed = cv2.morphologyEx(edges_dilated, cv2.MORPH_CLOSE, kernel, iterations=2)

        # ==================== Method 2: Color detection ====================
        hsv = cv2.cvtColor(page_image, cv2.COLOR_BGR2HSV)

        # Detect non-white regions (potential colored backgrounds)
        # White in HSV: S < 25, V > 240
        lower_white = np.array([0, 0, 240])
        upper_white = np.array([180, 25, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)

        # Find non-white regions
        non_white_mask = cv2.bitwise_not(white_mask)

        # Detect gray regions (potential text areas with light background)
        # Gray: Low saturation, medium value
        lower_gray = np.array([0, 0, 50])
        upper_gray = np.array([180, 50, 240])
        gray_mask = cv2.inRange(hsv, lower_gray, upper_gray)

        # Combine all detection methods
        combined_mask = cv2.bitwise_or(edges_closed, non_white_mask)
        combined_mask = cv2.bitwise_or(combined_mask, gray_mask)

        # Additional morphological cleanup
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel2, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Track detected rectangles to avoid duplicates
        rects = []

        # Analyze each contour
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_box_area:
                continue

            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)

            # Filter by size (annotations are reasonably sized boxes, not tiny marks)
            if w < 20 or h < 10:
                continue

            # Filter by aspect ratio (avoid thin lines)
            aspect_ratio = max(w, h) / min(w, h)
            if aspect_ratio > 100:  # Very elongated (likely a line)
                continue

            # Estimate confidence based on contour area vs bounding box area
            box_area = w * h
            confidence = area / box_area if box_area > 0 else 0

            # Filter out very low confidence detections
            if confidence < 0.1:
                continue

            # Classify detection type
            contour_points = len(contour)
            box_perimeter = 2 * (w + h)
            fill_ratio = contour_points / box_perimeter if box_perimeter > 0 else 0

            if fill_ratio > 0.7:
                detection_type = "solid_border"
            elif fill_ratio > 0.4:
                detection_type = "dashed_border"
            else:
                detection_type = "colored_bg"

            if confidence < 0.3:
                detection_type = "text_region"

            # Check for overlapping detections (keep the one with higher confidence)
            is_duplicate = False
            for i, existing_rect in enumerate(rects):
                ex, ey, ew, eh, econf, etype = existing_rect
                # Check if rectangles significantly overlap
                overlap_x = max(0, min(x + w, ex + ew) - max(x, ex))
                overlap_y = max(0, min(y + h, ey + eh) - max(y, ey))
                overlap_area = overlap_x * overlap_y
                if overlap_area > 0.5 * min(box_area, ew * eh):
                    if confidence > econf:
                        rects.pop(i)
                    else:
                        is_duplicate = True
                    break

            if not is_duplicate:
                rects.append((x, y, w, h, confidence, detection_type))

        # Convert to output format
        for x, y, w, h, confidence, detection_type in rects:
            detected_boxes.append({
                "rect": (x, y, w, h),
                "confidence": min(confidence, 1.0),
                "type": detection_type
            })

    except Exception as e:
        # Log but don't fail - return empty list if detection fails
        pass

    return detected_boxes


def extract_text_ocr(page_image: np.ndarray, rect: Tuple[int, int, int, int],
                      margin: int = 5, language: str = "eng", debug: bool = False) -> str:
    """
    Extract text from a region using Tesseract OCR.

    Preprocessing steps:
    1. Extract region with margin
    2. Convert to grayscale
    3. Apply multiple binarization approaches
    4. Try OCR with different configurations
    5. Return best result

    Args:
        page_image: Full page image
        rect: (x, y, w, h) bounding rectangle
        margin: Expand rect by this many pixels to capture full annotation
        language: Tesseract language code (default "eng")
        debug: If True, save debug images

    Returns:
        Extracted text string (may be empty if OCR fails)
    """
    try:
        x, y, w, h = rect

        # Add margin with bounds checking
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

        # Try multiple binarization methods and keep best result
        results = []

        # Method 1: Otsu's binarization
        try:
            _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed1 = cv2.dilate(binary_otsu, kernel, iterations=1)
            text1 = pytesseract.image_to_string(processed1, lang=language, config=r'--psm 6 --oem 3')
            if text1.strip():
                results.append(text1.strip())
        except:
            pass

        # Method 2: Adaptive thresholding (for varying illumination)
        try:
            binary_adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                     cv2.THRESH_BINARY, 11, 2)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed2 = cv2.dilate(binary_adaptive, kernel, iterations=1)
            text2 = pytesseract.image_to_string(processed2, lang=language, config=r'--psm 6 --oem 3')
            if text2.strip():
                results.append(text2.strip())
        except:
            pass

        # Method 3: Inverted binary (for light text on dark background)
        try:
            _, binary_normal = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            binary_inverted = cv2.bitwise_not(binary_normal)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed3 = cv2.dilate(binary_inverted, kernel, iterations=1)
            text3 = pytesseract.image_to_string(processed3, lang=language, config=r'--psm 6 --oem 3')
            if text3.strip():
                results.append(text3.strip())
        except:
            pass

        # Return longest result (usually most complete)
        if results:
            return max(results, key=len)

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
        if pattern.startswith("--") and upper_term.endswith(pattern[2:]):
            return "standard_variable", "suffix_prefix"
        if pattern.endswith("--") and upper_term.startswith(pattern[:-2]):
            return "standard_variable", "suffix_prefix"

    suffix_prefix = suffix_prefix_patterns.get("dataset", set())
    for pattern in suffix_prefix:
        if pattern.startswith("--") and upper_term.endswith(pattern[2:]):
            return "dataset_name", "suffix_prefix"
        if pattern.endswith("--") and upper_term.startswith(pattern[:-2]):
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
    results = []

    # Pattern 1: "VAR in SUPPYY" or "VAR in SUPPxx"
    pattern1 = r'([A-Z][A-Z0-9]*?)\s+in\s+(SUPP[A-Z]{2,})'
    for match in re.finditer(pattern1, text):
        var = match.group(1)
        dataset = match.group(2)
        if var and dataset and len(var) <= 8 and len(dataset) <= 8:
            results.append((var, dataset))

    # Pattern 2: "SUPPYY.VAR"
    pattern2 = r'(SUPP[A-Z]{2,})\.([A-Z][A-Z0-9]*?)(?:\s|$|[,;])'
    for match in re.finditer(pattern2, text):
        dataset = match.group(1)
        var = match.group(2)
        if var and dataset and len(var) <= 8 and len(dataset) <= 8:
            results.append((var, dataset))

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
                    "ocr_success_count": 0,
                    "ocr_fail_count": 0,
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
            "ocr_success_count": 0,
            "ocr_fail_count": 0,
            "variables_extracted": 0
        }

        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_idx = page_num + 1

            # ==================== Render page to image ====================
            # Use 150 DPI for reasonable quality vs speed tradeoff
            pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
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
                confidence = box_info["confidence"]

                # Extract text via OCR
                ocr_text = extract_text_ocr(page_image, rect, margin=5)

                if not ocr_text or len(ocr_text.strip()) < 2:
                    debug_info["ocr_fail_count"] += 1
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
                    category, match_level = classify_term(
                        left_var, ocr_text, standard_terms,
                        suffix_prefix_patterns, blacklist
                    )
                    if left_var in standard_terms.get("dataset", set()) and category != "not_submitted":
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

                    # Skip blacklist items
                    if category == "blacklist":
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
    print("✅ OpenCV+OCR Parser Module Loaded Successfully (v1.0 - Image-based extraction)")
