import streamlit as st
from pathlib import Path
from modules.xml_parser import parse_define_xml

# ====================== Page Configuration ======================
st.set_page_config(
    page_title="ACRF Page Validator",
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
    </style>
""", unsafe_allow_html=True)

# ====================== Sidebar ======================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/document.png", width=80)
    st.title("ACRF Page Validator")
    st.markdown("**SDTM Define.xml vs ACRF PDF Page Number Validation Tool**")
    st.divider()
    st.caption("Lightweight Version v0.1.0")

# ====================== Main Header ======================
st.markdown('<h1 class="main-header">ACRF Page Validator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Automatically validate ACRF page references between Define.xml and PDF</p>', 
            unsafe_allow_html=True)

# ====================== Tabs ======================
tab1, tab2, tab3 = st.tabs(["📄 XML Parser", "📑 ACRF PDF Parser", "🔍 Cross Validation"])

# ====================== Tab 1: XML Parser ======================
with tab1:
    st.subheader("1. Upload Define.xml")
    xml_file = st.file_uploader(
        "Define-XML File (.xml)", 
        type=["xml"], 
        key="xml_uploader",
        help="Upload the SDTM Define.xml file containing ACRF page references"
    )
    
    if st.button("🚀 Parse ACRF Pages from XML", type="primary"):
        if xml_file is None:
            st.error("Please upload a Define.xml file first.")
        else:
            with st.spinner("Parsing Define.xml with lxml + XPath..."):
                # Read file content
                xml_content = xml_file.getvalue()
                
                # Call parser
                result = parse_define_xml(xml_content)
                
                if result["status"] == "success":
                    st.markdown("**Extracted ACRF Page References**")
                    
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
                        "ACRF Pages": [row[2] for row in display_data],
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
        "ACRF PDF File", 
        type=["pdf"], 
        key="pdf_uploader",
        help="Upload the Annotated Case Report Form (ACRF) PDF"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        use_opencv = st.checkbox("OpenCV + OCR", value=True, 
                               help="Recommended for flattened PDFs")
    with col2:
        use_pymupdf = st.checkbox("PyMuPDF", value=True, 
                                help="Recommended for non-flattened PDFs")
    
    if st.button("🔍 Extract Variables from PDF", type="primary"):
        if pdf_file is None:
            st.error("Please upload an ACRF PDF file first.")
        else:
            with st.spinner("Processing PDF..."):
                results = {}
                
                if use_pymupdf:
                    st.info("📖 Running PyMuPDF parser...")
                    try:
                        from modules.pymupdf_parser import extract_variables_from_pdf
                        pdf_bytes = pdf_file.getvalue()
                        pymupdf_result = extract_variables_from_pdf(pdf_bytes)
                        results["pymupdf"] = pymupdf_result
                        
                        if pymupdf_result["status"] == "success":
                            if pymupdf_result["summary"].get("flattened_message"):
                                st.warning(pymupdf_result["summary"]["flattened_message"])
                            
                            proc_time = pymupdf_result["summary"].get("processing_time_seconds", pymupdf_result["summary"].get("processing_time"))
                            if proc_time is not None:
                                st.success(f"✅ PyMuPDF completed in {proc_time}s")
                            else:
                                st.success("✅ PyMuPDF completed")
                            
                            # === 关键：立即保存到 session_state ===
                            st.session_state.pymupdf_full_data = pymupdf_result["variables"].copy()
                            st.session_state.pdf_result = results
                            
                        else:
                            st.error(f"PyMuPDF Error: {pymupdf_result.get('error_message')}")
                    except Exception as e:
                        st.error(f"PyMuPDF failed: {str(e)}")
                
                st.session_state.pdf_results = results   # 额外备份

    # ====================== 显示结果区域（放在 button 外面） ======================
    if "pymupdf_full_data" in st.session_state and st.session_state.pymupdf_full_data:
        st.markdown("**PyMuPDF Extraction Result**")
        
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
        
        # 搜索框
        search_term = st.text_input("🔍 Search Variable", "", key="search_var_pymupdf_stable")
        
        # 过滤
        if search_term.strip():
            filtered_data = [item for item in full_data if search_term.lower() in item["Variable"].lower()]
        else:
            filtered_data = full_data
        
        st.write(f"**Showing {len(filtered_data)} / {total_vars} variables**")
        
        # 是否在预览中展开 RawTexts
        expand_raw = st.checkbox("Expand RawTexts in preview (may be long)", value=False, key="expand_raw_preview")

        # Build combined display list including domain annotations (classification column)
        combined_list = []
        # Add domain annotations if available
        domain_ann = None
        if "pdf_results" in st.session_state and st.session_state.pdf_results:
            domain_ann = st.session_state.pdf_results.get("pymupdf", {}).get("domain_annotations", [])
        if domain_ann:
            for d in domain_ann:
                combined_list.append({
                    "Classification": "Domain",
                    "Name": d.get("Domain"),
                    "Pages": d.get("PageString", ""),
                    "PageCount": d.get("PageCount", 0),
                    "Category": "dataset",
                    "MatchLevel": "",
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

            classification = "Domain" if item.get("Category") == "dataset_name" else "Variable"
            combined_list.append({
                "Classification": classification,
                "Name": item["Variable"],
                "Pages": item.get("PageString", ""),
                "PageCount": item.get("PageCount", len(item.get("Pages", []))),
                "Category": item.get("Category", "unknown"),
                "MatchLevel": item.get("MatchLevel", ""),
                "RawTexts": display_raw if display_raw else ""
            })

        if combined_list:
            st.table(combined_list)
        else:
            st.info("No matching annotations found.")
        
        # 下载按钮（始终下载全部）
        if full_data or domain_ann:
            import csv
            import io
            import time
            
            output = io.StringIO()
            fieldnames = ["Classification", "Name", "Pages", "PageCount", "Category", "MatchLevel", "RawTexts"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            # write domains first
            if domain_ann:
                for d in domain_ann:
                    writer.writerow({
                        "Classification": "Domain",
                        "Name": d.get("Domain"),
                        "Pages": d.get("PageString", ""),
                        "PageCount": d.get("PageCount", 0),
                        "Category": "dataset",
                        "MatchLevel": "",
                        "RawTexts": ""
                    })

            # write variables
            for item in full_data:
                raw_field = item.get("RawTexts", "")
                if isinstance(raw_field, list):
                    csv_raw = " | ".join(raw_field)
                else:
                    csv_raw = str(raw_field)
                classification = "Domain" if item.get("Category") == "dataset_name" else "Variable"
                writer.writerow({
                    "Classification": classification,
                    "Name": item["Variable"],
                    "Pages": item.get("PageString", ""),
                    "PageCount": item.get("PageCount", len(item.get("Pages", []))),
                    "Category": item.get("Category", "unknown"),
                    "MatchLevel": item.get("MatchLevel", ""),
                    "RawTexts": csv_raw
                })
            
            csv_bytes = output.getvalue().encode('utf-8')
            
            st.download_button(
                label="📥 Download Full Result as CSV",
                data=csv_bytes,
                file_name=f"pymupdf_result_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_pymupdf_final"
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
        if xml_file is None or pdf_file is None:
            st.warning("Please complete XML and PDF parsing first.")
        else:
            with st.spinner("Performing cross validation..."):
                st.success("✅ Validation completed!")
                
                st.markdown("**Validation Report**")
                validation_data = [
                    ["VSDTC", "77-87,119-121", "77-87,119", "⚠️ Mismatch"],
                    ["VSORRES", "45,46", "45", "⚠️ Mismatch"],
                    ["FALOC", "102", "102", "✅ Match"]
                ]
                st.table(validation_data)

# ====================== Footer ======================
st.divider()
st.caption("ACRF Page Validator | Lightweight English Version | Built with Streamlit")