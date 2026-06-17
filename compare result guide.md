# Compare Result Guide

## aCRF annotation type

| Type | Meaning | Recommended parser |
|---|---|---|
| MSG 2.0 readable annotations | PDF annotation objects exist and their `/Contents` fields contain machine-readable aCRF annotation text. | Use PyMuPDF as the primary parser; OpenCV + OCR is optional verification. |
| Annotation-flattened PDF | aCRF annotations have been flattened into the page content and are no longer readable PDF annotation objects. The base PDF may still have a text layer. | Use OpenCV + OCR as the primary parser. PyMuPDF may still read page text, but it should not be treated as the main annotation source. |
| Partial/weak annotation layer | Some annotation objects exist, but `/Contents` coverage is incomplete, weak, or mostly special cases such as NOT SUBMITTED. | Run both PyMuPDF and OpenCV + OCR, then review parser differences before XML comparison. |

## Important distinction

In this project, "flattened" should be interpreted in the SDTM MSG 2.0 aCRF annotation context:

- Annotation-flattened means annotation objects are not reliably machine-readable.
- Image-only PDF means the page text layer is also missing and OCR is required for all text.

These are related but not identical. A PDF can be annotation-flattened while still having a readable page text layer.

## Two-parser comparison categories

| Category | Meaning |
|---|---|
| Consensus | PyMuPDF and OpenCV both found the same variable and the same page set. For NOT SUBMITTED, duplicate page occurrences must also match. |
| Page Mismatch | Both parsers found the same variable, but their page sets differ, or NOT SUBMITTED occurrence counts differ. Review before using for XML comparison. |
| PyMuPDF Only | Only PyMuPDF found the variable. Usually reliable for MSG 2.0 readable annotations. |
| OpenCV Only | Only OpenCV found the variable. Common for annotation-flattened PDFs; verify OCR quality and false positives. |
