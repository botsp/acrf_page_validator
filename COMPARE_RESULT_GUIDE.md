# Compare Result Guide (XML vs PyMuPDF)

This guide explains each result element in Cross Validation, especially:

- `diff_type`
- `relation` (output field: `page_subset`)
- `path` (output field: `match_path`)

---

## 1. Comparison Principles

1. **XML is the source of truth**: only XML records with page references are included in the main comparison.
2. **Variable-level comparison first**: the main check is variable matching and page consistency.
3. The Cross Validation results may contain too many categories, making it difficult to quickly grasp all elements. This is because the categories parsed from acrf.pdf are already numerous, and the XML cross-validation introduces even more classifications. Keeping the detailed categories is helpful for locating differences. However, please prioritize alerts associated with the following keywords, as they are <u>**directly related to differences**</u>.

   **Recommended priority, from highest to lowest:**
   
   | Priority | Alert Type | Action |
   |---|---|---|
   | 🔴 Critical | `PAGE_MISMATCH` | Pages in PDF don't match XML specification |
   | 🔴 Critical | `MISSING_IN_PDF` | Variable exists in XML but not found in PDF |
   | 🟠 High | `LOW_CONFIDENCE` | Pattern parsing failed; please manually check in source files |
   | 🟡 Medium | `extra_domain` | Domain appears in PDF but not in XML; please manually cross-check in CSDRG |
   | 🟡 Medium | `unmapped_variable` | Variable appears in PDF but not in XML; please manually cross-check in CSDRG |

4. **VLM (Value Level Metadata) XML variables are supported**:
   for a pattern like `A.B.C.EQ.V`, e.g.`DDORRES.DD.DDTESTCD.EQ.AUTOPIND`:
   - `A` = target variable
   - `B` = dataset/domain
   - `C` = qualifier variable
   - `EQ/IN` = operator
   - `V` = value (VLM expansion)
   A VLM XML variable can match PyMuPDF through two paths:
   - `path_A_target_var`: match `A`
   - `path_B_qualifier_value`: match `C=V`

---

## 2. Meaning of Common Result Examples

### A) `VLM_RESOLVED relation: exact path: path_A_target_var`

Meaning:
- XML item is a VLM (Value Level Metadata) variable (e.g. `DDORRES.DD.DDTESTCD.EQ.AUTOPIND`)
- it was matched through Path A (`DDORRES`) in PyMuPDF
- page sets are exactly the same (`relation=exact`)

Conclusion: **matched successfully through VLM resolution**

---

### B) `MATCH relation: exact path: simple`

Meaning:
- XML item is a simple variable (not compound)
- matched directly by variable name in PyMuPDF
- page sets are exactly the same

Conclusion: **direct match**

---

### C) `PAGE_MISMATCH relation: pdf_superset path: path_A_target_var`

Meaning:
- variable matching succeeded (through Path A in this example)
- page sets are not the same
- `pdf_superset` means PDF contains all XML pages plus extra pages

Conclusion: **matched variable, but page mismatch**

---

## 3. `diff_type` Definitions

| diff_type | Meaning | Treated as pass |
|---|---|---|
| `MATCH` | Simple variable matched and pages are identical | Yes |
| `VLM_RESOLVED` | VLM variable matched through path A or B, with identical pages | Yes |
| `PAGE_MISMATCH` | Variable matched but page sets differ | No |
| `MISSING_IN_PDF` | XML has the item but PDF has no match | No |
| `LOW_CONFIDENCE` | XML variable format cannot be reliably parsed as simple/VLM | No (manual review) |
| `EXTRA_IN_PDF` | Item appears only in PDF (shown in extra outputs) | Not part of XML main pass rate |

> Note: `EXTRA_IN_PDF` mainly appears in extra outputs, not as XML-anchored main detail rows.

---

## 4. `relation` (`page_subset`) Definitions

| relation | Meaning |
|---|---|
| `exact` | XML and PDF page sets are identical |
| `pdf_superset` | PDF contains all XML pages and additional pages |
| `pdf_subset` | PDF covers only part of XML pages |
| `overlap` | XML and PDF page sets overlap but neither contains the other |
| `disjoint` | XML and PDF page sets have no overlap |

---

## 5. `path` (`match_path`) Definitions

| path | Meaning | Typical use |
|---|---|---|
| `simple` | Match by XML variable name directly | Simple variable |
| `path_A_target_var` | For compound XML item, match by `target_var` (A) | Compound variable |
| `path_B_qualifier_value` | For compound XML item, match by `qualifier=value` (`C=V`) | Compound variable |

---

## 6. Main Detail Fields (`compare detail`)

| Field | Meaning |
|---|---|
| `XML_Dataset` | Dataset/domain from XML |
| `XML_Variable` | Original XML variable string (may be compound) |
| `XML_Pages` | XML page set |
| `XML_PageCount` | XML page count |
| `PDF_Matched_Name` | Matched variable name in PDF |
| `PDF_Pages` | PDF page set for the matched item |
| `PDF_PageCount` | PDF page count for the matched item |
| `diff_type` | Result type |
| `page_subset` | Page relation (`relation`) |
| `match_path` | Match route (`path`) |
| `page_diff_detail` | Difference details, e.g. `xml_only=...; pdf_only=...` |
| `note` | Additional note (for example low-confidence reason) |

---

## 7. Extra Output Fields

### 7.1 Extra PDF Variables

| Field | Meaning |
|---|---|
| `PDF_Name` | Variable name that exists only in PDF |
| `PDF_Pages` | Page set |
| `Category` | PyMuPDF category |
| `subtype` | `value_pair` (contains `=`) or `unmapped_variable` |
| `RawTexts` | Evidence text |

### 7.2 Extra PDF Domains

| Field | Meaning |
|---|---|
| `PDF_Domain` | Domain that exists only in PDF |
| `PDF_Pages` | Page set |
| `subtype` | Always `extra_domain` |
