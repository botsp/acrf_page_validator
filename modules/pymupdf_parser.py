import fitz  # PyMuPDF
import re
import time
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

# Load configuration
try:
    from config.config_loader import CONFIG
except ImportError:
    from ..config.config_loader import CONFIG


def is_flattened_pdf(doc: fitz.Document, threshold: float = 180) -> Tuple[bool, float, str]:
    """
    Detect if PDF is flattened (text layer missing or very weak).
    
    Args:
        doc: PyMuPDF document
        threshold: Character count threshold per page
    
    Returns:
        Tuple of (is_flattened: bool, avg_text_per_page: float, reason: str)
    """
    total_text = 0
    total_words = 0
    pages_with_text = 0
    
    for page in doc:
        text = page.get_text("text").strip()
        words = len(text.split())
        total_text += len(text)
        total_words += words
        if len(text) > 50:
            pages_with_text += 1
    
    num_pages = len(doc)
    avg_text = total_text / num_pages if num_pages > 0 else 0
    avg_words = total_words / num_pages if num_pages > 0 else 0
    
    is_flattened = (
        avg_text < threshold or
        avg_words < 25 or
        (pages_with_text / num_pages < 0.3 if num_pages > 0 else True)
    )
    
    reason = ""
    if is_flattened:
        if avg_text < 50:
            reason = "Very few text layers detected (highly likely flattened PDF)"
        else:
            reason = "Weak text layer detected, likely flattened PDF"
    
    return is_flattened, avg_text, reason


def extract_annotation_regions(page: fitz.Page) -> List[str]:
    """
    Extract text from annotation regions using actual PDF annotation objects (annots).
    Clip using a slightly inset bbox to avoid capturing adjacent glyphs (e.g., radio
    buttons), and perform light cleaning to remove very short parenthetical markers
    like `( )`, `( y )` that commonly appear near widgets.

    Args:
        page: PyMuPDF page object

    Returns:
        List of extracted annotation texts (may be empty if no annotations found)
    """
    annotation_texts = []

    # Preferred method: iterate actual annotation objects (works for non-flattened PDFs)
    try:
        ann = page.first_annot
        while ann is not None:
            try:
                rect = ann.rect
                # Inset the rect slightly to avoid capturing adjacent UI elements (radio circles, borders)
                pad = 1.5  # points
                try:
                    inset_rect = fitz.Rect(rect.x0 + pad, rect.y0 + pad, rect.x1 - pad, rect.y1 - pad)
                    # If inset becomes invalid, fall back to original rect
                    if inset_rect.x1 <= inset_rect.x0 or inset_rect.y1 <= inset_rect.y0:
                        inset_rect = rect
                except Exception:
                    inset_rect = rect

                text_in_rect = page.get_text("text", clip=inset_rect).strip()
                if not text_in_rect:
                    # Try fallback to original rect if inset removed text unexpectedly
                    text_in_rect = page.get_text("text", clip=rect).strip()

                if text_in_rect:
                    # initial value
                    cleaned = text_in_rect
                    # Remove very short parenthetical markers like '( )' or '( y )'
                    cleaned = re.sub(r'\(\s*[A-Za-z\s]{0,3}\s*\)', '', cleaned)
                    # Remove leading parenthetical fragments, closed or not, e.g. '(x )', '(x', '(x FAORRES'
                    cleaned = re.sub(r'^\(\s*[^)]{0,15}\)\s*', '', cleaned)  # closed parentheses at start
                    cleaned = re.sub(r'^\(\s*[^)]{1,15}\s+', '', cleaned)    # opening parenthesis with no close, up to 15 chars
                    # Remove any residual leading '('
                    cleaned = re.sub(r'^\(\s*', '', cleaned)
                    # Collapse multiple spaces and normalize
                    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
                    if cleaned:
                        annotation_texts.append(cleaned)
            except Exception:
                # ignore individual annotation failures
                pass
            ann = ann.next
    except Exception:
        # If annotation iteration fails, fall back to empty list (do NOT use whole-page heuristics)
        pass

    # Deduplicate exact duplicate texts while preserving order
    seen = set()
    unique_texts = []
    for text in annotation_texts:
        if text not in seen:
            seen.add(text)
            unique_texts.append(text)

    return unique_texts


def parse_supp_variable(text: str) -> List[Tuple[str, str]]:
    """
    Extract SUPP-related variable-dataset pairs from text.
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


def extract_candidates(text: str) -> Set[str]:
    """
    Extract candidate terms (potential variable/dataset names) from text.
    Uses capitalization rule and length constraints.
    More conservative approach to reduce false positives.
    
    Args:
        text: Text to extract from
    
    Returns:
        Set of candidate terms
    """
    candidates = set()
    
    # Rule: Capitalized terms (all caps)
    # Length: 2-8 characters (standard SDTM constraint)
    
    # Pattern 1: All-caps words surrounded by boundaries
    # Match sequences of uppercase letters and digits (2-8 chars)
    for match in re.finditer(r'\b([A-Z][A-Z0-9]{1,7})\b', text):
        token = match.group(1)
        if 2 <= len(token) <= 8:
            candidates.add(token)
    
    # Pattern 2: Explicit variable references in conditions
    # "VAR when", "VAR if", "VAR then", "VAR =", "VAR :", etc
    for match in re.finditer(r'\b([A-Z][A-Z0-9]{1,7})\s+(?:when|if|then|=|:|;|,)', text, re.IGNORECASE):
        token = match.group(1)
        if 2 <= len(token) <= 8:
            candidates.add(token)
    
    return candidates


def classify_term(term: str, raw_context: str, standard_terms: Dict, 
                  suffix_prefix_patterns: Dict, blacklist: Set) -> Tuple[str, str]:
    """
    Classify a term and return (category, match_level).

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

    # Level 3: Exact match in standard_term.csv
    if upper_term in standard_terms.get("variable", set()):
        return "standard_variable", "exact"
    if upper_term in standard_terms.get("dataset", set()):
        return "dataset_name", "exact"

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

    # Level 5: SUPP variable pattern detection
    if "SUPP" in upper_term:
        supp_pattern = r'(SUPP[A-Z]{2,8})'
        supp_matches = re.findall(supp_pattern, raw_context)
        if supp_matches:
            return supp_matches[0], "supp"
        return "supp_variable", "supp"

    # Level 6: Unknown
    return "unknown", "none"


def extract_not_submitted_entries(text: str, page_idx: int) -> List[Dict[str, Any]]:
    """
    Extract all NOT SUBMITTED occurrences with case insensitivity.
    Returns aggregated count per page to avoid duplication of the same pattern.
    
    Args:
        text: Text to search
        page_idx: Page number (1-indexed)
    
    Returns:
        List of NOT SUBMITTED entries with counts
    """
    entries = []
    
    # Case-insensitive patterns for NOT SUBMITTED
    # Search for variations
    pattern = re.compile(r'\b(?:NOT\s+SUBMITTED|NOTSUBMITTED)\b', re.IGNORECASE)
    matches = pattern.findall(text)
    
    if matches:
        total_count = len(matches)
        entries.append({
            "Variable": "NOT SUBMITTED",
            "Page": page_idx,
            "Count": total_count
        })
    
    return entries


def extract_variables_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Main PyMuPDF parser focusing on annotation-based variable extraction.
    
    Workflow:
    1. Detect if PDF is flattened
    2. For each page, extract ONLY annotation regions (no fallback to full text)
    3. Extract candidate terms from annotations using capitalization rules
    4. Classify each term using 6-level priority matching
    5. Aggregate results per variable with complete page lists
    
    Args:
        pdf_bytes: PDF file content as bytes
    
    Returns:
        Dict with structure:
        {
            "status": "success" | "error",
            "variables": list of variable records,
            "not_submitted": list of NOT SUBMITTED occurrences,
            "summary": dict with metadata,
            "error_message": str or None
        }
    """
    start_time = time.time()
    doc = None
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Flattened PDF detection
        is_flattened, avg_text, flatten_reason = is_flattened_pdf(doc)
        flattened_message = None
        if is_flattened:
            flattened_message = (
                f"Flattened PDF detected (avg text: {avg_text:.1f} chars/page). {flatten_reason}. "
                "Recommend using OpenCV + OCR as well."
            )
        
        # Load config
        standard_terms = CONFIG.get("standard_terms", {"variable": set(), "dataset": set()})
        suffix_prefix_patterns = CONFIG.get("suffix_prefix_patterns", {"variable": set(), "dataset": set()})
        blacklist = CONFIG.get("blacklist", set())
        
        # Result containers
        # Map: term -> {"pages": set, "raw_contexts": list, "category": str, "flag": str}
        variable_index = defaultdict(lambda: {
            "pages": set(),
            "raw_contexts": [],
            "category": "unknown",
            "match_level": "none"
        })

        # Domain annotations: domain -> set(pages)
        domain_index = defaultdict(set)
        
        # Separate tracking for NOT SUBMITTED
        not_submitted_entries = []
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_idx = page_num + 1
            
            # ==================== Extract annotation regions ====================
            annotation_texts = extract_annotation_regions(page)
            
            # If no annotations found, skip this page (do NOT fallback to full text)
            if not annotation_texts:
                continue
            
            # ==================== Extract NOT SUBMITTED entries ====================
            full_page_text = page.get_text("text")
            not_sub_list = extract_not_submitted_entries(full_page_text, page_idx)
            not_submitted_entries.extend(not_sub_list)
            
            # ==================== Process each annotation ====================
            for ann_text in annotation_texts:
                if not ann_text.strip():
                    continue

                # Heuristic: detect domain annotations in the annotation text
                try:
                    # Match explicit dataset tokens listed in standard_terms
                    for m in re.finditer(r'\b([A-Z]{1,3})\b', ann_text):
                        token = m.group(1)
                        if token in standard_terms.get("dataset", set()):
                            domain_index[token].add(page_idx)
                    # Check pattern like 'DM (Demographics)' at line start
                    m2 = re.match(r'^([A-Z]{1,3})\b', ann_text)
                    if m2:
                        t0 = m2.group(1)
                        if t0 in standard_terms.get("dataset", set()):
                            domain_index[t0].add(page_idx)
                except Exception:
                    pass

                # Extract candidate terms
                candidates = extract_candidates(ann_text)
                
                # Try to extract SUPP-related variables first
                supp_pairs = parse_supp_variable(ann_text)
                for var, dataset in supp_pairs:
                    candidates.add(var)
                    candidates.add(dataset)
                
                # Classify each candidate
                for candidate in candidates:
                    if not candidate or len(candidate) < 2 or len(candidate) > 8:
                        continue
                    
                    upper_cand = candidate.upper()
                    category, match_level = classify_term(
                        upper_cand, ann_text, standard_terms, 
                        suffix_prefix_patterns, blacklist
                    )

                    # Skip blacklist items
                    if category == "blacklist":
                        continue

                    # Record this occurrence
                    variable_index[upper_cand]["pages"].add(page_idx)

                    # Store FULL raw context (untruncated)
                    # Issue 5 fix: preserve complete annotation text
                    variable_index[upper_cand]["raw_contexts"].append(ann_text.strip())

                    # Update category and match_level with priority logic
                    # Priority order for match_level: exact (3) > suffix_prefix (2) > supp (1) > none (0)
                    current_level = variable_index[upper_cand].get("match_level", "none")

                    priority = {"exact": 3, "suffix_prefix": 2, "supp": 1, "none": 0}
                    new_priority = priority.get(match_level, -1)
                    current_priority = priority.get(current_level, -1)

                    if new_priority > current_priority:
                        variable_index[upper_cand]["category"] = category
                        variable_index[upper_cand]["match_level"] = match_level
                    elif new_priority == current_priority and category != "unknown":
                        # Same priority: update category if more specific
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
        # Build ordered list of page occurrences (allow duplicates) preserving appearance order
        pages_sequence = []
        for entry in not_submitted_entries:
            # entry has keys: Page and Count
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
                "flattened_detected": is_flattened,
                "flattened_message": flattened_message,
                "avg_text_per_page": round(avg_text, 1)
            },
            "error_message": None
        }
    
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        return {
            "status": "error",
            "variables": [],
            "summary": {
                "processing_time_seconds": elapsed
            },
            "error_message": str(e)
        }
    
    finally:
        if doc is not None:
            doc.close()


if __name__ == "__main__":
    print("✅ PyMuPDF Parser Module Loaded Successfully (v2.0 - Annotation-focused)")