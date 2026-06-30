import argparse
import csv
from pathlib import Path
from typing import Iterable, List, Set

import cv2
import fitz
import numpy as np


def parse_pages_spec(spec: str, total_pages: int) -> List[int]:
    """
    Parse 1-based page spec like:
    - "11-30"
    - "11-30,35,40-42"
    Returns sorted unique 1-based pages.
    """
    pages: Set[int] = set()
    chunks = [x.strip() for x in spec.split(",") if x.strip()]
    for chunk in chunks:
        if "-" in chunk:
            left, right = chunk.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            lo, hi = sorted((start, end))
            for p in range(lo, hi + 1):
                if 1 <= p <= total_pages:
                    pages.add(p)
        else:
            p = int(chunk)
            if 1 <= p <= total_pages:
                pages.add(p)
    return sorted(pages)


def ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "x", "y", "w", "h", "expected_text"])


def append_rows(path: Path, rows: Iterable[List[str]]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def render_page_bgr(page: fitz.Page, dpi: int) -> np.ndarray:
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manually label gold ROI boxes for OCR benchmark.")
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to source PDF (example: config\\acrf_3039_UC_flattened.pdf)",
    )
    parser.add_argument(
        "--pages",
        default="11-30",
        help='1-based pages, e.g. "11-30" or "11-30,35,40-42"',
    )
    parser.add_argument(
        "--out",
        default="outputs\\gold_roi.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Render DPI used for ROI coordinates (default: 300)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)
    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return 1

    doc = fitz.open(str(pdf_path))
    try:
        pages = parse_pages_spec(args.pages, len(doc))
        if not pages:
            print("[ERROR] No valid pages selected.")
            return 1

        ensure_csv_header(out_path)

        print(f"[INFO] PDF: {pdf_path}")
        print(f"[INFO] Output CSV: {out_path}")
        print(f"[INFO] Pages: {pages}")
        print(f"[INFO] DPI: {args.dpi}")
        print("")
        print("Instructions:")
        print("1. In each page window, draw one or more boxes.")
        print("2. Press ENTER or SPACE to confirm the selected ROIs for that page.")
        print("3. Press ESC to finish selection for that page.")
        print("4. Then input expected_text for each ROI in terminal.")
        print("5. Leave expected_text empty to skip that ROI.")
        print("")

        window_name = "ROI Labeler (draw boxes, ENTER=confirm, ESC=finish page)"

        total_saved = 0
        for page_num in pages:
            page = doc[page_num - 1]
            image = render_page_bgr(page, args.dpi)

            header = image.copy()
            cv2.putText(
                header,
                f"Page {page_num} | Draw ROIs, ENTER confirm, ESC finish",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1600, 900)
            rois = cv2.selectROIs(window_name, header, showCrosshair=True, fromCenter=False)
            cv2.destroyWindow(window_name)
            if rois is None or len(rois) == 0:
                print(f"[INFO] Page {page_num}: no ROI selected.")
                continue

            rows: List[List[str]] = []
            print(f"\n[PAGE {page_num}] {len(rois)} ROI(s) selected.")
            for idx, roi in enumerate(rois, start=1):
                x, y, w, h = [int(v) for v in roi]
                if w <= 1 or h <= 1:
                    print(f"  - ROI {idx}: invalid size, skipped.")
                    continue

                expected_text = input(
                    f"  - ROI {idx} [x={x}, y={y}, w={w}, h={h}] expected_text: "
                ).strip()
                if not expected_text:
                    print("    (empty -> skipped)")
                    continue
                rows.append([str(page_num), str(x), str(y), str(w), str(h), expected_text])

            if rows:
                append_rows(out_path, rows)
                total_saved += len(rows)
                print(f"[INFO] Page {page_num}: saved {len(rows)} ROI row(s).")
            else:
                print(f"[INFO] Page {page_num}: nothing saved.")

        cv2.destroyAllWindows()
        print(f"\n[DONE] Total saved ROI rows: {total_saved}")
        print(f"[DONE] File: {out_path}")
        return 0
    finally:
        doc.close()


if __name__ == "__main__":
    raise SystemExit(main())
