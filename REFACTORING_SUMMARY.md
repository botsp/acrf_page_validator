# MSG 2.0 Annotation Structure Extraction - Refactoring Summary

**Date**: 17 June 2026  
**Status**: ✅ Complete

## Objective

Fix "DF Uniques" text contamination artifact by refactoring PDF annotation extraction to use annotation `/Contents` fields instead of coordinate-based text clipping.

## Root Cause Analysis

The previous implementation used `page.get_text("text", clip=rect)` to extract text from annotation bounding boxes. This approach had a critical flaw:

- **Problem**: Coordinate clipping captured ALL text within the rectangle, including adjacent page labels
- **Evidence**: MHCAT variable RawTexts contained: `DF Uniques MHCAT=DISEASE CHARACTERISTICS | MHCAT=GENERAL MEDICAL HISTORY`
- **Why**: The annotation rect boundaries were wider than the actual text content, causing contamination

## Solution Implemented

### 1. Refactored `extract_annotation_regions()` Function

**Before**:
```python
def extract_annotation_regions(page: fitz.Page) -> List[str]:
    # Used: page.get_text("text", clip=inset_rect)
    # Returns: List of strings
```

**After**:
```python
def extract_annotation_regions(page: fitz.Page) -> Dict[str, Any]:
    # Uses: ann.info.get("content", "")  # MSG 2.0 compliant
    # Returns: {
    #     "texts": [extracted annotation contents],
    #     "need_ocr": [annotations without /Contents field]
    # }
```

**Key Changes**:
- Removed coordinate-based text clipping entirely
- Now reads `/Contents` field directly from annotation objects (structurally sound)
- Marked annotations without `/Contents` for future OCR processing
- Maintained parenthetical cleanup logic

### 2. Updated `extract_variables_from_pdf()` Call Site

Modified lines 409-411 to unpack the new dictionary return format:

```python
annot_result = extract_annotation_regions(page)
annotation_texts = annot_result.get("texts", [])
need_ocr = annot_result.get("need_ocr", [])
```

### 3. Architecture Principles Established

**Separation of Concerns**:
- **PyMuPDF Module**: Structural extraction only (reads annotation `/Contents`)
  - ✅ MSG 2.0 compliant
  - ✅ Clean, accurate, no noise
  - ✗ Fails gracefully if annotation lacks `/Contents`
  
- **OpenCV+OCR Module** (Future): Image-based fallback
  - Handles PDFs that don't comply with MSG 2.0
  - Uses coordinate geometry and visual clustering

## Verification Results

### Test 1: DF Uniques Removal
- **Before**: `MHCAT=DISEASE CHARACTERISTICS | DF Uniques MHCAT=GENERAL MEDICAL HISTORY`
- **After**: `MHCAT=DISEASE CHARACTERISTICS | MHCAT=GENERAL MEDICAL HISTORY`
- **Result**: ✅ PASSED

### Test 2: Variable Extraction Coverage
- Variables extracted from acrf_3039_UC.pdf: **345**
- Breakdown:
  - Standard variables: 313
  - Dataset names: 31
  - Not submitted: 1
- **Result**: ✅ PASSED (no regression)

### Test 3: Issue 17 Pattern Resolution
- All 11 previously failing patterns: ✅ **RESOLVED**
  - 4-part patterns (e.g., `DSSTDTC.DS.DSDECOD.INFORMED CONSENT OBTAINED`)
  - Multi-criteria patterns (e.g., `FAORRES.FA.FATESTCD.CLNRSPC.FA.FACAT.1.FA.FASCAT.2`)
- **Result**: ✅ PASSED

### Test 4: SUPP Variable Pair Extraction
- SUPP variables found: **12**
- Extraction logic: Intact and functional
- **Result**: ✅ PASSED

### Test 5: Syntax and Integration
- Syntax compilation: ✅ PASSED
- Integration with existing comparator logic: ✅ PASSED
- Backward compatibility: ✅ MAINTAINED

## Files Modified

| File | Lines | Change | Impact |
|------|-------|--------|--------|
| `modules/pymupdf_parser.py` | 59-117 | Refactored `extract_annotation_regions()` | Extraction now structural, not coordinate-based |
| `modules/pymupdf_parser.py` | 409-411 | Updated call site to unpack Dict | Proper handling of new return format |

## Impact Summary

### Data Quality
- ✅ Eliminates "DF Uniques" contamination
- ✅ More reliable text extraction
- ✅ Aligns with MSG 2.0 specification

### Maintainability
- ✅ Clear separation of extraction strategies
- ✅ Documented fallback path for OCR
- ✅ No changes to downstream logic

### Backward Compatibility
- ✅ All existing variable extraction logic works unchanged
- ✅ Candidate generation and classification unaffected
- ✅ SUPP variable pair handling preserved

## Future Work

### Immediate
- [ ] Monitor for `need_ocr` annotations in real-world PDFs
- [ ] Log statistics on msg2.0 compliance

### Phase 2: OCR Module Integration
- [ ] Implement OpenCV+OCR module
- [ ] Process `need_ocr` annotations
- [ ] Visual clustering for coordinate-based extraction

## Technical Notes

### PyMuPDF Annotation Structure (MSG 2.0)
- Annotations are independent objects with `/Contents` field
- Can be accessed via `ann.info.get("content", "")`
- 3039 PDF: 526/526 FreeText annotations have `/Contents` (100% compliant)

### Coordinate-Based Extraction Risks
- Rect boundaries > actual text content → adjacent text captured
- Page visual structure ≠ text structure
- Noise from labels, headers, borders, etc.
- **Solution**: Avoid entirely for MSG 2.0 compliant PDFs

### Parenthetical Cleanup
- Maintained for `/Contents` field extraction
- Handles common artifacts: `( )`, `( y )`, leading parentheses
- Applied consistently to structured content

## 19 June 2026 - OpenCV+OCR Tuning Note

- Tightened OCR pipeline to follow: `visual hard gate -> OCR -> semantic gate`.
- Added color-filled rectangle prioritization, border evidence scoring (pixel-based), ROI inset before OCR, and annotation-like text gating to reduce body-text contamination in `RawTexts`.
- Replaced longest-text OCR selection with score-based ranking (`annotation pattern score + OCR confidence`).
- Added debug counters: `roi_prefilter_skipped_count` and `ocr_noise_rejected_count`.
- Set `max_boxes_per_page` to **28** as a temporary cap to reduce truncation risk on dense pages while keeping runtime acceptable.
- Next step: calibrate a more reliable cap with additional project PDFs using `boxes_per_page` saturation and end-to-end processing time.
