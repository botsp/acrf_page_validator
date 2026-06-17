#!/usr/bin/env python
"""
Debug script to investigate PDF annotation structure and render output.
"""

import fitz
import cv2
import numpy as np
from pathlib import Path

def inspect_pdf_annotations(pdf_path):
    """Check what annotations exist in the PDF"""
    print(f"\n{'='*70}")
    print(f"Inspecting: {pdf_path}")
    print(f"{'='*70}")
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    total_annotations = 0
    annotations_with_contents = 0
    annotations_without_contents = 0
    
    print(f"Total pages: {len(doc)}")
    
    # Check first 10 pages (increased to find annotations)
    for page_num in range(min(10, len(doc))):
        page = doc[page_num]
        page_idx = page_num + 1
        
        annotations = []
        ann = page.first_annot
        while ann is not None:
            ann_info = ann.info
            ann_type = ann.type[1]
            has_content = "content" in ann_info and bool(ann_info.get("content", "").strip())
            
            annotations.append({
                "type": ann_type,
                "has_content": has_content,
                "rect": ann.rect,
                "content": ann_info.get("content", "")[:100] if has_content else None
            })
            
            if has_content:
                annotations_with_contents += 1
            else:
                annotations_without_contents += 1
            
            total_annotations += 1
            ann = ann.next
        
        if annotations:
            print(f"\nPage {page_idx}: {len(annotations)} annotations")
            for i, annot in enumerate(annotations):
                status = "HAS CONTENT" if annot["has_content"] else "NO CONTENT"
                print(f"  [{i}] Type: {annot['type']:15s} {status}")
                if annot["content"]:
                    print(f"      Content: {annot['content']}")
    
    doc.close()
    
    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Total annotations: {total_annotations}")
    print(f"  With /Contents field: {annotations_with_contents}")
    print(f"  Without /Contents: {annotations_without_contents}")
    if total_annotations > 0:
        print(f"  Coverage: {annotations_with_contents/total_annotations*100:.1f}%")
    else:
        print(f"  Coverage: N/A (no annotations in checked pages)")


def check_page_rendering(pdf_path, page_num=0):
    """Check what the rendered page looks like"""
    print(f"\n{'='*70}")
    print(f"Page Rendering Check: {pdf_path}")
    print(f"{'='*70}")
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    
    # Get text to see if there's any text layer
    text = page.get_text("text")
    print(f"Page {page_num} text layer size: {len(text)} characters")
    print(f"First 200 chars: {text[:200]}")
    
    # Render at different DPIs
    for dpi in [72, 150, 300]:
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        print(f"\nDPI {dpi}: Image size = {pix.width}x{pix.height}")
        
        # Convert to CV format
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Check image statistics
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        unique_values = len(np.unique(gray))
        print(f"  Unique grayscale values: {unique_values}")
        print(f"  Min/Max intensity: {gray.min()}/{gray.max()}")
    
    doc.close()


def main():
    pdfs = [
        "config/acrf_324.pdf",
        "config/acrf_3039_UC.pdf",
    ]
    
    for pdf in pdfs:
        path = Path(pdf)
        if path.exists():
            try:
                inspect_pdf_annotations(path)
                check_page_rendering(path, page_num=0)
            except Exception as e:
                print(f"Error processing {pdf}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"File not found: {pdf}")


if __name__ == "__main__":
    main()
