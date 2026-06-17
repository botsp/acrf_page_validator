import streamlit as st
from pathlib import Path
from modules.xml_parser import parse_define_xml
from modules.comparator import compare_xml_vs_pymupdf, rows_to_csv_bytes

# ====================== Page Configuration ======================
st.set_page_config(
    page_title="aCRF Page Validator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.3rem;
        color: #424242;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    div[data-testid="stTable"] table {
        width: 100%;
        table-layout: fixed !important;
    }
    div[data-testid="stTable"] th,
    div[data-testid="stTable"] td {
        white-space: pre-wrap !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
        vertical-align: top !important;
    }
    div[data-testid="stDataFrame"] [role="columnheader"],
    div[data-testid="stDataFrame"] [role="gridcell"] {
        white-space: pre-wrap !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
        vertical-align: top !important;
    }
    div[data-testid="stDataFrame"] div[data-testid="stDataFrameResizable"] {
        overflow-x: hidden !important;
    }
    </style>
""", unsafe_allow_html=True)

# ====================== Sidebar ======================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/document.png", width=80)
    st.title("aCRF Page Validator")
    st.markdown("**SDTM Define.xml vs aCRF PDF Page Number Validation Tool**")
    st.divider()
    st.caption("Lightweight Version v0.1.0")

# ====================== Main Header ======================
st.markdown('<h1 class="main-header">aCRF Page Validator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Automatically validate aCRF page references between Define.xml and PDF</p>',
            unsafe_allow_html=True)

# ====================== Tabs ======================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📄 XML Parser", "📑 aCRF PDF Parser", "🔍 Cross Validation", "📘 Readme"]
)

# ====================== Tab 1: XML Parser ======================
with tab1:
    st.subheader("1. Upload Define.xml")
    xml_file = st.file_uploader(
        "Define-XML File (.xml)",
        type=["xml"],
        key="xml_uploader",
        help="Upload the SDTM Define.xml file containing aCRF page references"
    )

    if st.button("🚀 Parse aCRF Pages from XML", type="primary"):
        if xml_file is None:
            st.error("Please upload a Define.xml file first.")
        else:
            with st.spinner("Parsing Define.xml with lxml + XPath..."):
                # Read file content
                xml_content = xml_file.getvalue()

                # Call parser
                result = parse_define_xml(xml_content)

                if result["status"] == "success":
                    st.markdown("**Extracted aCRF Page References**")

                    # Prepare display data
                    display_data = []
                    for var in result["variables"]:
                        display_data.append([
                            var["Dataset"],
                            var["Variable"],
                            var["PageString"],
                            var["PageCount"]
                        ])

                    # Display as table with headers
                    st.table({
                        "Dataset": [row[0] for row in display_data],
                        "Variable": [row[1] for row in display_data],
                        "aCRF Pages": [row[2] for row in display_data],
                        "Page Count": [row[3] for row in display_data]
                    })

                    # Summary
                    st.success(f"""
                    ✅ Successfully parsed **{result['summary']['total_variables']}** variables
                    from **{result['summary']['unique_datasets']}** datasets.
                    """)

                    # Store in session state for later comparison
                    st.session_state.xml_result = result

                else:
                    st.error(f"Failed to parse XML: {result.get('error_message', 'Unknown error')}")


# ====================== Tab 2: aCRF PDF Parser ======================
with tab2:
    st.subheader("2. Upload aCRF PDF")
    pdf_file = st.file_uploader(
        "aCRF PDF File",
        type=["pdf"],
        key="pdf_uploader",
        help="Upload the Annotated Case Report Form (aCRF) PDF"
    )

    # ==================== Auto-detect aCRF annotation type ====================
    annotation_type_key = "unknown"
    is_text_layer_missing = False
    pdf_bytes = None

    if pdf_file is not None:
        pdf_bytes = pdf_file.getvalue()

        # Auto-detect annotation readability in the MSG 2.0 context.
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            from modules.pymupdf_parser import detect_acrf_annotation_type, is_flattened_pdf
            is_text_layer_missing, avg_text, text_layer_reason = is_flattened_pdf(doc)
            annotation_profile = detect_acrf_annotation_type(doc)
            doc.close()

            annotation_type_key = annotation_profile.get("type_key", "unknown")
            annotation_label = annotation_profile.get("label", "Unknown annotation type")
            recommendation = annotation_profile.get("recommendation", "")
            stats_line = (
                f"Annotation objects: {annotation_profile.get('total_annots', 0)} | "
                f"Readable /Contents: {annotation_profile.get('readable_annots', 0)} | "
                f"Non-special readable: {annotation_profile.get('non_special_readable_annots', 0)} | "
                f"Text layer: {'Missing/weak' if is_text_layer_missing else 'Present'} "
                f"(avg {avg_text:.1f} chars/page)"
            )

            if annotation_type_key == "msg2_readable":
                st.success(f"📊 aCRF Annotation Type: **{annotation_label}**\n\n{recommendation}")
            elif annotation_type_key == "annotation_flattened":
                st.warning(f"📊 aCRF Annotation Type: **{annotation_label}**\n\n{recommendation}")
            else:
                st.info(f"📊 aCRF Annotation Type: **{annotation_label}**\n\n{recommendation}")
            st.caption(stats_line)
        except Exception as e:
            st.warning(f"Could not auto-detect aCRF annotation type: {str(e)}")
            annotation_type_key = "unknown"

    # ==================== Conditional checkbox logic ====================
    col1, col2 = st.columns(2)

    with col1:
        if annotation_type_key == "annotation_flattened":
            use_opencv = st.checkbox(
                "OpenCV + OCR (Recommended)",
                value=True,
                help="Recommended: annotation objects are missing or not readable"
            )
        elif annotation_type_key == "partial_weak_annotation":
            use_opencv = st.checkbox(
                "OpenCV + OCR (Recommended for weak annotation layer)",
                value=True,
                help="Recommended: annotation layer is partial or weak"
            )
        else:
            use_opencv = st.checkbox(
                "OpenCV + OCR (Optional Verification)",
                value=False,
                help="Optional: use for double-verification of PyMuPDF results"
            )

    with col2:
        if annotation_type_key == "annotation_flattened":
            use_pymupdf = st.checkbox(
                "PyMuPDF (Optional page-text check)",
                value=False,
                help="Optional: annotation objects are not readable; PyMuPDF may still read page text"
            )
        elif annotation_type_key == "partial_weak_annotation":
            use_pymupdf = st.checkbox(
                "PyMuPDF (Partial annotation layer)",
                value=True,
                help="Recommended together with OpenCV for weak annotation layers"
            )
        else:
            use_pymupdf = st.checkbox(
                "PyMuPDF (Recommended)",
                value=True,
                help="Default method when MSG 2.0 readable annotations are detected"
            )

    if st.button("🔍 Extract Variables from PDF", type="primary"):
        if pdf_file is None:
            st.error("Please upload an aCRF PDF file first.")
        else:
            with st.spinner("Processing PDF..."):
                results = {}
                pymupdf_result = None
                opencv_result = None

                # ==================== PyMuPDF extraction ====================
                if use_pymupdf:
                    st.info("📖 Running PyMuPDF parser...")
                    try:
                        from modules.pymupdf_parser import extract_variables_from_pdf as pymupdf_extract
                        pymupdf_result = pymupdf_extract(pdf_bytes)
                        results["pymupdf"] = pymupdf_result

                        if pymupdf_result["status"] == "success":
                            proc_time = pymupdf_result["summary"].get("processing_time_seconds",
                                                                      pymupdf_result["summary"].get("processing_time"))
                            st.success(f"✅ PyMuPDF completed in {proc_time}s ({len(pymupdf_result['variables'])} variables)")
                        else:
                            st.error(f"PyMuPDF Error: {pymupdf_result.get('error_message')}")
                    except Exception as e:
                        st.error(f"PyMuPDF failed: {str(e)}")

                # ==================== OpenCV extraction ====================
                if use_opencv:
                    st.info("🖼️ Running OpenCV + OCR parser...")
                    try:
                        from modules.opencv_parser import (
                            extract_variables_from_pdf as opencv_extract,
                            is_tesseract_available
                        )
                        tesseract_ok, _ = is_tesseract_available()
                        if not tesseract_ok:
                            opencv_result = {
                                "status": "error",
                                "variables": [],
                                "domain_annotations": [],
                                "summary": {"total_variables": 0, "extraction_method": "opencv_ocr"},
                                "error_message": "Tesseract OCR engine is not available. Please install Tesseract and add it to PATH."
                            }
                        else:
                            opencv_result = opencv_extract(pdf_bytes)
                        results["opencv"] = opencv_result

                        if opencv_result["status"] == "success":
                            proc_time = opencv_result["summary"].get("processing_time_seconds",
                                                                     opencv_result["summary"].get("processing_time"))
                            st.success(f"✅ OpenCV completed in {proc_time}s ({len(opencv_result['variables'])} variables)")

                            # Display debug info
                            debug = opencv_result.get("debug_info", {})
                            if debug:
                                with st.expander("🔍 OpenCV Debug Info (Detection & OCR Stats)"):
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Total Boxes Detected", debug.get("total_boxes_detected", 0))
                                    with col2:
                                        st.metric("OCR Success", debug.get("ocr_success_count", 0))
                                    with col3:
                                        st.metric("OCR Failed", debug.get("ocr_fail_count", 0))
                                    with col4:
                                        st.metric("Variables Found", debug.get("variables_extracted", 0))

                                    # Per-page breakdown
                                    if debug.get("boxes_per_page"):
                                        st.write("**Boxes per page:**")
                                        pages_breakdown = debug.get("boxes_per_page", [])
                                        for page_info in pages_breakdown[:50]:  # Show first 50 pages
                                            if page_info.get("boxes_count", 0) > 0:
                                                st.caption(f"Page {page_info.get('page')}: {page_info.get('boxes_count')} boxes")
                        else:
                            st.error(f"OpenCV Error: {opencv_result.get('error_message')}")
                    except Exception as e:
                        st.error(f"OpenCV failed: {str(e)}")

                # ==================== Two-layer verification (if both parsers ran) ====================
                if (
                    pymupdf_result and opencv_result and use_pymupdf and use_opencv
                    and pymupdf_result.get("status") == "success"
                    and opencv_result.get("status") == "success"
                ):
                    st.divider()
                    st.info("🔍 Running Two-Layer Verification (Consensus Check)")

                    # Compare results
                    from modules.comparator import compare_parser_results
                    comparison = compare_parser_results(pymupdf_result, opencv_result)

                    # Store in session
                    st.session_state.parser_comparison = comparison
                    st.session_state.pymupdf_full_data = comparison.get("consensus", [])
                    st.session_state.verification_report = {
                        "consensus_count": len(comparison.get("consensus", [])),
                        "page_mismatch": comparison.get("page_mismatch", []),
                        "pymupdf_only": comparison.get("pymupdf_only", []),
                        "opencv_only": comparison.get("opencv_only", [])
                    }

                    # Display verification summary
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Consensus", len(comparison.get("consensus", [])),
                                 help="Both parsers found the same variable on the same pages")
                    with col2:
                        st.metric("Page Mismatch", len(comparison.get("page_mismatch", [])),
                                 help="Both parsers found the variable, but page sets or occurrence counts differ")
                    with col3:
                        st.metric("PyMuPDF Only", len(comparison.get("pymupdf_only", [])),
                                 help="Only PyMuPDF found (likely valid)")
                    with col4:
                        st.metric("OpenCV Only", len(comparison.get("opencv_only", [])),
                                 help="Only OpenCV found (verify manually)")

                    st.success("✅ Verification complete. See results below.")

                # ==================== Single parser (store results) ====================
                elif pymupdf_result and pymupdf_result["status"] == "success":
                    st.session_state.pymupdf_full_data = pymupdf_result["variables"].copy()
                    st.session_state.pdf_result = results

                elif opencv_result and opencv_result["status"] == "success":
                    st.session_state.pymupdf_full_data = opencv_result["variables"].copy()
                    st.session_state.pdf_result = results

                st.session_state.pdf_results = results   # 备份

    # ====================== 显示结果区域（放在 button 外面） ======================

    # Check if we have verification report (two-layer validation)
    show_verification_details = False
    if "parser_comparison" in st.session_state and st.session_state.parser_comparison:
        show_verification_details = True
        comparison = st.session_state.parser_comparison

        def _preview_raw(value, max_len=220):
            text = str(value or "").strip()
            if len(text) > max_len:
                return text[:max_len] + "..."
            return text

        st.divider()
        st.subheader("📊 Two-Layer Verification Report")

        # Show tabs for different categories
        tab_consensus, tab_mismatch, tab_pymupdf, tab_opencv = st.tabs(
            ["✅ Consensus", "⚠️ Page Mismatch", "⚠️ PyMuPDF Only", "❌ OpenCV Only"]
        )

        with tab_consensus:
            consensus_data = comparison.get("consensus", [])
            st.write(f"**{len(consensus_data)} variables confirmed by both parsers**")
            if consensus_data:
                # Display consensus table
                display_consensus = []
                for item in consensus_data[:800]:
                    display_consensus.append({
                        "Classification": "Variable",
                        "Name": item.get("Variable", ""),
                        "Pages": item.get("PageString", ""),
                        "PageCount": item.get("PageCount", 0),
                        "Category": item.get("Category", ""),
                        "RawTexts": _preview_raw(item.get("RawTexts", "")),
                        "PyMuPDF Pages": item.get("PyMuPDF_Pages", ""),
                        "OpenCV Pages": item.get("OpenCV_Pages", "")
                    })
                st.dataframe(display_consensus, use_container_width=True)
            else:
                st.info("No consensus between parsers")

        with tab_mismatch:
            mismatch_data = comparison.get("page_mismatch", [])
            st.warning(f"**{len(mismatch_data)} variables found by both parsers but with page differences**")
            if mismatch_data:
                display_mismatch = []
                for item in mismatch_data[:800]:
                    display_mismatch.append({
                        "Classification": "Variable",
                        "Name": item.get("Variable", ""),
                        "Pages": item.get("PageString", ""),
                        "PageCount": item.get("PageCount", 0),
                        "Category": item.get("Category", ""),
                        "MismatchReason": item.get("MismatchReason", ""),
                        "PyMuPDF Pages": item.get("PyMuPDF_Pages", ""),
                        "PyMuPDF PageCount": item.get("PyMuPDF_PageCount", ""),
                        "OpenCV Pages": item.get("OpenCV_Pages", ""),
                        "OpenCV PageCount": item.get("OpenCV_PageCount", ""),
                        "RawTexts": _preview_raw(item.get("RawTexts", ""))
                    })
                st.dataframe(display_mismatch, use_container_width=True)
            else:
                st.info("No page mismatches between parsers")

        with tab_pymupdf:
            pymupdf_only = comparison.get("pymupdf_only", [])
            st.write(f"**{len(pymupdf_only)} variables found only by PyMuPDF** (likely valid)")
            if pymupdf_only:
                display_only = []
                for item in pymupdf_only[:800]:
                    display_only.append({
                        "Classification": "Variable",
                        "Name": item.get("Variable", ""),
                        "Pages": item.get("Pages", ""),
                        "PageCount": item.get("PageCount", 0),
                        "Category": item.get("Category", ""),
                        "RawTexts": _preview_raw(item.get("RawTexts", ""))
                    })
                st.dataframe(display_only, use_container_width=True)
            else:
                st.info("No PyMuPDF-only variables")

        with tab_opencv:
            opencv_only = comparison.get("opencv_only", [])
            st.warning(f"**{len(opencv_only)} variables found only by OpenCV** (verify manually)")
            if opencv_only:
                display_only = []
                for item in opencv_only[:800]:
                    display_only.append({
                        "Classification": "Variable",
                        "Name": item.get("Variable", ""),
                        "Pages": item.get("Pages", ""),
                        "PageCount": item.get("PageCount", 0),
                        "Category": item.get("Category", ""),
                        "RawTexts": _preview_raw(item.get("RawTexts", ""))
                    })
                st.dataframe(display_only, use_container_width=True)
            else:
                st.info("No OpenCV-only variables")

    # Standard result display (if not two-layer verification)
    if not show_verification_details and "pymupdf_full_data" in st.session_state and st.session_state.pymupdf_full_data:
        st.markdown("**PDF Extraction Result**")

        full_data = st.session_state.pymupdf_full_data

        # Summary
        total_vars = len(full_data)
        not_sub_count = sum(1 for x in full_data if x.get("Category") == "not_submitted")
        unknown_count = sum(1 for x in full_data if x.get("Category") == "unknown")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Variables", total_vars)
        with col2:
            st.metric("NOT SUBMITTED", not_sub_count)
        with col3:
            st.metric("Unknown", unknown_count)

        # 搜索与视图控制
        search_term = st.text_input("🔍 Search Variable", "", key="search_var_pymupdf_stable")
        show_unmatched_only = st.checkbox(
            "Show unmatched only (Category = unknown)",
            value=True,
            key="show_unmatched_only"
        )

        # 过滤
        if search_term.strip():
            filtered_data = [item for item in full_data if search_term.lower() in item["Variable"].lower()]
        else:
            filtered_data = full_data

        if show_unmatched_only:
            filtered_data = [item for item in filtered_data if item.get("Category") == "unknown"]

        st.write(f"**Showing {len(filtered_data)} / {total_vars} variables**")

        # 是否在预览中展开 RawTexts
        expand_raw = st.checkbox("Expand RawTexts in preview (may be long)", value=False, key="expand_raw_preview")

        def get_classification(category: str) -> str:
            if category == "not_submitted":
                return "NOT SUBMITTED"
            if category in ("dataset_name", "dataset"):
                return "Domain"
            return "Variable"

        classification_order = {"Domain": 0, "Variable": 1, "NOT SUBMITTED": 2}

        # Build combined display list including domain annotations (classification column)
        combined_list = []
        # Add domain annotations if available
        domain_ann = None
        if "pdf_results" in st.session_state and st.session_state.pdf_results:
            domain_ann = st.session_state.pdf_results.get("pymupdf", {}).get("domain_annotations", [])
        domain_names_in_vars = {
            item.get("Variable")
            for item in filtered_data
            if item.get("Category") in ("dataset_name", "dataset")
        }
        if domain_ann and not show_unmatched_only:
            for d in domain_ann:
                domain_name = d.get("Domain")
                if domain_name in domain_names_in_vars:
                    continue
                combined_list.append({
                    "Classification": "Domain",
                    "Name": domain_name,
                    "Pages": str(d.get("PageString", "")).replace(",", ", "),
                    "PageCount": d.get("PageCount", 0),
                    "Category": "dataset_name",
                    "RawTexts": ""
                })

        # Add variable entries
        for item in filtered_data[:800]:   # 限制显示数量，避免卡顿
            raw_field = item.get("RawTexts", "")
            if isinstance(raw_field, list):
                raw_display = " | ".join(raw_field)
            else:
                raw_display = str(raw_field)

            # 仅在超长时截断，并且仅在截断时添加省略号
            if expand_raw:
                display_raw = raw_display
            else:
                if raw_display and len(raw_display) > 200:
                    display_raw = raw_display[:200] + "..."
                else:
                    display_raw = raw_display

            classification = get_classification(item.get("Category", "unknown"))
            combined_list.append({
                "Classification": classification,
                "Name": item["Variable"],
                "Pages": str(item.get("PageString", "")).replace(",", ", "),
                "PageCount": item.get("PageCount", len(item.get("Pages", []))),
                "Category": item.get("Category", "unknown"),
                "RawTexts": display_raw if display_raw else ""
            })

        combined_list.sort(
            key=lambda x: (
                classification_order.get(x.get("Classification", "Variable"), 99),
                str(x.get("Name", ""))
            )
        )

        if combined_list:
            st.table(combined_list)
        else:
            st.info("No matching annotations found.")

        # 下载按钮（始终下载全部 + unmatched）
        if full_data or domain_ann:
            import csv
            import io
            import time

            csv_fieldnames = ["Classification", "Name", "Pages", "PageCount", "Category", "RawTexts"]

            def build_csv_bytes(variable_items, include_domains):
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=csv_fieldnames)
                writer.writeheader()

                rows = []

                domain_names_in_vars_csv = {
                    item.get("Variable")
                    for item in variable_items
                    if item.get("Category") in ("dataset_name", "dataset")
                }
                if include_domains and domain_ann:
                    for d in domain_ann:
                        domain_name = d.get("Domain")
                        if domain_name in domain_names_in_vars_csv:
                            continue
                        row = {
                            "Classification": "Domain",
                            "Name": domain_name,
                            "Pages": d.get("PageString", ""),
                            "PageCount": d.get("PageCount", 0),
                            "Category": "dataset_name",
                            "RawTexts": ""
                        }
                        rows.append(row)

                for item in variable_items:
                    raw_field = item.get("RawTexts", "")
                    if isinstance(raw_field, list):
                        csv_raw = " | ".join(raw_field)
                    else:
                        csv_raw = str(raw_field)
                    row = {
                        "Classification": get_classification(item.get("Category", "unknown")),
                        "Name": item["Variable"],
                        "Pages": item.get("PageString", ""),
                        "PageCount": item.get("PageCount", len(item.get("Pages", []))),
                        "Category": item.get("Category", "unknown"),
                        "RawTexts": csv_raw
                    }
                    rows.append(row)

                rows.sort(
                    key=lambda x: (
                        classification_order.get(x.get("Classification", "Variable"), 99),
                        str(x.get("Name", ""))
                    )
                )
                for row in rows:
                    writer.writerow(row)

                return output.getvalue().encode("utf-8")

            csv_bytes = build_csv_bytes(full_data, include_domains=True)
            unknown_items = [item for item in full_data if item.get("Category") == "unknown"]
            unknown_csv_bytes = build_csv_bytes(unknown_items, include_domains=False)

            st.download_button(
                label="📥 Download Full Result as CSV",
                data=csv_bytes,
                file_name=f"pymupdf_result_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_pymupdf_final"
            )
            st.download_button(
                label="📥 Download Unmatched (unknown) as CSV",
                data=unknown_csv_bytes,
                file_name=f"pymupdf_unmatched_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_pymupdf_unmatched"
            )

# ====================== Tab 3: Cross Validation ======================
with tab3:
    st.subheader("3. Cross Validation")

    st.markdown("**Select Comparison Methods**")
    col_a, col_b = st.columns(2)
    with col_a:
        cmp_opencv = st.checkbox("XML vs OpenCV", value=True)
    with col_b:
        cmp_pymupdf = st.checkbox("XML vs PyMuPDF", value=True)

    if st.button("⚖️ Start Cross Validation", type="primary"):
        xml_result = st.session_state.get("xml_result")
        pdf_results = st.session_state.get("pdf_results")
        if not isinstance(pdf_results, dict):
            pdf_results = st.session_state.get("pdf_result", {})
        pymupdf_result = pdf_results.get("pymupdf") if isinstance(pdf_results, dict) else None

        if not cmp_opencv and not cmp_pymupdf:
            st.warning("Please select at least one comparison method.")
        elif not xml_result:
            st.warning("Please parse Define.xml first in Tab 1.")
        elif cmp_pymupdf and not pymupdf_result:
            st.warning("Please run PyMuPDF parsing first in Tab 2.")
        else:
            with st.spinner("Performing cross validation..."):
                if cmp_pymupdf:
                    compare_result = compare_xml_vs_pymupdf(xml_result, pymupdf_result)
                    st.session_state.compare_xml_vs_pymupdf = compare_result

                    if compare_result.get("status") == "success":
                        st.success("✅ XML vs PyMuPDF validation completed.")
                    else:
                        st.error(f"Cross validation failed: {compare_result.get('error_message', 'Unknown error')}")

                if cmp_opencv:
                    st.info("OpenCV comparison is not connected yet in this version.")

    compare_result = st.session_state.get("compare_xml_vs_pymupdf")
    if compare_result and compare_result.get("status") == "success":
        summary = compare_result.get("summary", {})
        summary_by_dataset = compare_result.get("summary_by_dataset", [])
        detail_rows = compare_result.get("detail_rows", [])
        extra_pdf_rows = compare_result.get("extra_pdf_rows", [])
        extra_pdf_domain_rows = compare_result.get("extra_pdf_domain_rows", [])

        st.markdown("**Validation Summary**")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("XML Variables", summary.get("total_xml_variables", 0))
        with m2:
            st.metric("Match + Compound", summary.get("matched", 0) + summary.get("compound_resolved", 0))
        with m3:
            st.metric("Page Mismatch", summary.get("page_mismatch", 0))
        with m4:
            st.metric("Missing in PDF", summary.get("missing_in_pdf", 0))
        with m5:
            st.metric("Extra in PDF", summary.get("extra_in_pdf_variables", 0))

        if summary_by_dataset:
            st.markdown("**Summary by Dataset**")
            st.table(summary_by_dataset)

        def wrap_text(value, max_len=None):
            text = str(value or "").strip()
            if not text:
                return ""
            text = text.replace(",", ", ")
            text = text.replace(" | ", "\n")
            if max_len and len(text) > max_len:
                return text[:max_len] + "..."
            return text

        detail_rows_for_display = []
        for row in detail_rows:
            detail_rows_for_display.append(
                {
                    "XML": f"{row.get('XML_Dataset', '')}  {wrap_text(row.get('XML_Variable', ''))}",
                    "Pages": f"XML: {wrap_text(row.get('XML_Pages', ''))}     PDF: {wrap_text(row.get('PDF_Pages', ''))}",
                    "PDF Match": wrap_text(row.get("PDF_Matched_Name", "")),
                    "Result": (
                        f"{row.get('diff_type', '')}\n"
                        f"relation: {row.get('page_subset') or '-'}\n"
                        f"path: {row.get('match_path') or '-'}"
                    ),
                    "Diff Detail": wrap_text(row.get("page_diff_detail", "")),
                    "Note": wrap_text(row.get("note", "")),
                }
            )

        st.markdown("**Validation Detail (XML as reference)**")
        if detail_rows_for_display:
            st.table(detail_rows_for_display)
        else:
            st.info("No detail records were generated.")

        if extra_pdf_rows:
            st.markdown("**Extra Variables in PyMuPDF (not in XML contract)**")
            extra_pdf_rows_for_display = []
            for row in extra_pdf_rows:
                extra_pdf_rows_for_display.append(
                    {
                        "PDF Name": wrap_text(row.get("PDF_Name", "")),
                        "PDF Pages": wrap_text(row.get("PDF_Pages", "")),
                        "Category": row.get("Category", ""),
                        "Subtype": row.get("subtype", ""),
                        "RawTexts": wrap_text(row.get("RawTexts", ""), max_len=220),
                    }
                )
            st.table(extra_pdf_rows_for_display)

        if extra_pdf_domain_rows:
            st.markdown("**Extra Domains in PyMuPDF**")
            extra_pdf_domain_rows_for_display = []
            for row in extra_pdf_domain_rows:
                extra_pdf_domain_rows_for_display.append(
                    {
                        "PDF Domain": wrap_text(row.get("PDF_Domain", "")),
                        "PDF Pages": wrap_text(row.get("PDF_Pages", "")),
                        "Subtype": row.get("subtype", ""),
                    }
                )
            st.table(extra_pdf_domain_rows_for_display)

        import time

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        summary_fields = [
            "total_xml_variables",
            "total_pdf_variables",
            "total_pdf_domains",
            "matched",
            "compound_resolved",
            "page_mismatch",
            "missing_in_pdf",
            "low_confidence",
            "extra_in_pdf_variables",
            "extra_in_pdf_domains",
        ]
        detail_fields = [
            "XML_Dataset",
            "XML_Variable",
            "XML_Pages",
            "XML_PageCount",
            "PDF_Matched_Name",
            "PDF_Pages",
            "PDF_PageCount",
            "diff_type",
            "page_subset",
            "match_path",
            "page_diff_detail",
            "note",
        ]
        extra_var_fields = [
            "diff_type",
            "PDF_Name",
            "PDF_Pages",
            "PDF_PageCount",
            "Category",
            "subtype",
            "RawTexts",
        ]
        extra_domain_fields = [
            "diff_type",
            "PDF_Domain",
            "PDF_Pages",
            "PDF_PageCount",
            "subtype",
        ]

        st.download_button(
            label="📥 Download Compare Summary CSV",
            data=rows_to_csv_bytes([summary], summary_fields),
            file_name=f"compare_summary_{timestamp}.csv",
            mime="text/csv",
            key="download_compare_summary",
        )
        st.download_button(
            label="📥 Download Compare Detail CSV",
            data=rows_to_csv_bytes(detail_rows, detail_fields),
            file_name=f"compare_detail_{timestamp}.csv",
            mime="text/csv",
            key="download_compare_detail",
        )
        st.download_button(
            label="📥 Download Extra PDF Variables CSV",
            data=rows_to_csv_bytes(extra_pdf_rows, extra_var_fields),
            file_name=f"compare_extra_pdf_variables_{timestamp}.csv",
            mime="text/csv",
            key="download_compare_extra_pdf_variables",
        )
        st.download_button(
            label="📥 Download Extra PDF Domains CSV",
            data=rows_to_csv_bytes(extra_pdf_domain_rows, extra_domain_fields),
            file_name=f"compare_extra_pdf_domains_{timestamp}.csv",
            mime="text/csv",
            key="download_compare_extra_pdf_domains",
        )

# ====================== Tab 4: Readme ======================
with tab4:
    st.subheader("4. Readme")
    guide_path = Path(__file__).parent / "COMPARE_RESULT_GUIDE.md"
    if guide_path.exists():
        st.markdown(guide_path.read_text(encoding="utf-8"))
    else:
        st.warning("COMPARE_RESULT_GUIDE.md was not found.")

# ====================== Footer ======================
st.divider()
st.caption("aCRF Page Validator | Lightweight English Version | Built with Streamlit")
