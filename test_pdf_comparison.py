#!/usr/bin/env python
"""
Test OpenCV+OCR parser on actual PDF files.
Compares results with PyMuPDF for consistency.
"""

import json
from pathlib import Path
from modules.opencv_parser import extract_variables_from_pdf as opencv_extract
from modules.pymupdf_parser import extract_variables_from_pdf as pymupdf_extract

def compare_results(pdf_path, name):
    """Test a PDF with both parsers and compare results"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"File: {pdf_path}")
    print(f"{'='*70}")
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    print(f"File size: {len(pdf_bytes) / 1024 / 1024:.2f} MB")
    
    # Test PyMuPDF
    print("\n[PyMuPDF Parser]")
    pymupdf_result = pymupdf_extract(pdf_bytes)
    print(f"Status: {pymupdf_result['status']}")
    if pymupdf_result['status'] == 'success':
        print(f"Variables found: {pymupdf_result['summary']['total_variables']}")
        print(f"Total pages: {pymupdf_result['summary']['total_pages']}")
        print(f"Processing time: {pymupdf_result['summary']['processing_time_seconds']:.2f}s")
        if pymupdf_result['summary'].get('flattened_message'):
            print(f"Note: {pymupdf_result['summary']['flattened_message']}")
        
        # Show sample variables
        if pymupdf_result['variables']:
            print(f"\nSample variables (first 5):")
            for var in pymupdf_result['variables'][:5]:
                print(f"  - {var['Variable']}: pages {var['PageString']}, category={var['Category']}")
    else:
        print(f"Error: {pymupdf_result['error_message']}")
    
    # Test OpenCV+OCR
    print("\n[OpenCV+OCR Parser]")
    opencv_result = opencv_extract(pdf_bytes)
    print(f"Status: {opencv_result['status']}")
    if opencv_result['status'] == 'success':
        print(f"Variables found: {opencv_result['summary']['total_variables']}")
        print(f"Total pages: {opencv_result['summary']['total_pages']}")
        print(f"Processing time: {opencv_result['summary']['processing_time_seconds']:.2f}s")
        
        # Show sample variables
        if opencv_result['variables']:
            print(f"\nSample variables (first 5):")
            for var in opencv_result['variables'][:5]:
                print(f"  - {var['Variable']}: pages {var['PageString']}, category={var['Category']}")
    else:
        print(f"Error: {opencv_result['error_message']}")
    
    # Comparison
    print(f"\n[Comparison]")
    if pymupdf_result['status'] == 'success' and opencv_result['status'] == 'success':
        pymupdf_count = pymupdf_result['summary']['total_variables']
        opencv_count = opencv_result['summary']['total_variables']
        print(f"PyMuPDF found: {pymupdf_count} variables")
        print(f"OpenCV found: {opencv_count} variables")
        print(f"Difference: {abs(pymupdf_count - opencv_count)} ({abs(pymupdf_count - opencv_count)/max(pymupdf_count, opencv_count)*100:.1f}%)")
        
        # Find common variables
        pymupdf_vars = {v['Variable'] for v in pymupdf_result['variables']}
        opencv_vars = {v['Variable'] for v in opencv_result['variables']}
        common = pymupdf_vars & opencv_vars
        only_pymupdf = pymupdf_vars - opencv_vars
        only_opencv = opencv_vars - pymupdf_vars
        
        print(f"Common variables: {len(common)}")
        print(f"Only in PyMuPDF: {len(only_pymupdf)}")
        print(f"Only in OpenCV: {len(only_opencv)}")
        
        if only_pymupdf:
            print(f"  Missing in OpenCV (sample): {list(only_pymupdf)[:3]}")
        if only_opencv:
            print(f"  Extra in OpenCV (sample): {list(only_opencv)[:3]}")
    else:
        print("Cannot compare: One or both parsers failed")


def main():
    config_dir = Path("config")
    pdfs = [
        ("acrf_324.pdf", "ACRF 324"),
        ("acrf_3039_UC.pdf", "ACRF 3039 UC"),
    ]
    
    for filename, name in pdfs:
        pdf_path = config_dir / filename
        if pdf_path.exists():
            try:
                compare_results(pdf_path, name)
            except Exception as e:
                print(f"\n❌ Exception processing {name}: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\n⚠️  File not found: {pdf_path}")


if __name__ == "__main__":
    main()
