"""
extract.py
----------
Extract text from a PDF using pdfplumber, insert page-boundary sentinels,
and save the raw concatenated text plus a page map.

Outputs:
  data/raw_text.txt      - full text with <<<PAGE_BREAK:N>>> sentinels
  data/page_map.json     - {page_number: char_offset_of_sentinel} mapping
"""

import json
import os
import sys
from pathlib import Path

import pdfplumber


SENTINEL_TEMPLATE = "\n\n<<<PAGE_BREAK:{n}>>>\n\n"


def extract_pdf(pdf_path: str, output_dir: str = "data") -> tuple[str, dict]:
    """
    Extract text from all pages of a PDF.

    Args:
        pdf_path:   Path to the source PDF file.
        output_dir: Directory to write raw_text.txt and page_map.json.

    Returns:
        (full_text, page_map) where:
          full_text  - concatenated text with page-break sentinels
          page_map   - dict mapping page number (int) to char offset of its sentinel
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pages_text = []
    page_map = {}  # page_number (1-based) -> char offset of sentinel in full_text

    print(f"Extracting: {pdf_path.name}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")

        for i, page in enumerate(pdf.pages):
            page_num = i + 1  # 1-based

            # layout=True uses bounding boxes to reconstruct reading order
            text = page.extract_text(layout=True) or ""

            # Warn on empty pages (likely images/scans)
            if not text.strip():
                print(f"  WARNING: Page {page_num} returned empty text — may be scanned image")

            pages_text.append((page_num, text))

    # Build full_text by concatenating pages with sentinels between them
    parts = []
    cursor = 0

    for page_num, text in pages_text:
        parts.append(text)
        cursor += len(text)

        # Insert sentinel after page text (except after the last page)
        if page_num < len(pages_text):
            sentinel = SENTINEL_TEMPLATE.format(n=page_num)
            # Record the char offset where this sentinel starts
            page_map[page_num] = cursor
            parts.append(sentinel)
            cursor += len(sentinel)

    full_text = "".join(parts)

    # Write outputs
    raw_text_path = output_dir / "raw_text.txt"
    raw_text_path.write_text(full_text, encoding="utf-8")
    print(f"  Wrote raw text: {raw_text_path} ({len(full_text):,} chars)")

    page_map_path = output_dir / "page_map.json"
    # Convert keys to strings for JSON serialisation
    page_map_path.write_text(
        json.dumps({str(k): v for k, v in page_map.items()}, indent=2),
        encoding="utf-8"
    )
    print(f"  Wrote page map: {page_map_path} ({len(page_map)} entries)")

    return full_text, page_map


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.extract <pdf_path> [output_dir]")
        sys.exit(1)

    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "data"
    extract_pdf(pdf, out)
