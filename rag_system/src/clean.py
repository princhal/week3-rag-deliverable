"""
clean.py
--------
Clean raw extracted PDF text according to the pipeline defined in Phase 2.2:

  1. Strip running headers/footers (lines repeating on > 80% of pages)
  2. Dehyphenation (rejoin words split across line breaks)
  3. Normalize whitespace (3+ newlines → 2, single mid-paragraph newlines → space)
  4. Remove isolated page-number artifacts
  5. Unicode normalization (NFKC)
  6. Preserve <<<PAGE_BREAK:N>>> sentinels throughout

Outputs:
  data/cleaned_text.txt  - cleaned full text (sentinels still present)
  data/page_offsets.json - {page_number: char_offset} in the CLEANED text
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


SENTINEL_RE = re.compile(r"<<<PAGE_BREAK:(\d+)>>>")


def _split_into_pages(text: str) -> list[tuple[int, str]]:
    """
    Split full_text on sentinels into [(page_num, page_text), ...].
    Page 1 is the text before the first sentinel.
    """
    segments = SENTINEL_RE.split(text)
    # segments alternates: [text_before_first_sentinel, page_num, text, page_num, text ...]
    pages = []
    # First segment is page 1 text
    pages.append((1, segments[0]))
    # Subsequent pairs: (page_num_str, text_after_sentinel)
    i = 1
    while i < len(segments) - 1:
        page_num = int(segments[i])
        page_text = segments[i + 1]
        pages.append((page_num + 1, page_text))  # text after sentinel belongs to next page
        i += 2
    return pages


def _detect_header_footer_lines(pages: list[tuple[int, str]], threshold: float = 0.8) -> set[str]:
    """
    Detect lines that appear on more than `threshold` fraction of pages.
    Checks the first 2 and last 2 lines of each page.
    Returns a set of stripped line strings to remove.
    """
    total_pages = len(pages)
    line_counts: Counter = Counter()

    for _, page_text in pages:
        lines = page_text.splitlines()
        candidate_lines = set()
        # First 2 lines
        for line in lines[:2]:
            stripped = line.strip()
            if stripped:
                candidate_lines.add(stripped)
        # Last 2 lines
        for line in lines[-2:]:
            stripped = line.strip()
            if stripped:
                candidate_lines.add(stripped)
        for line in candidate_lines:
            line_counts[line] += 1

    cutoff = total_pages * threshold
    return {line for line, count in line_counts.items() if count >= cutoff}


def _strip_header_footer(text: str, noise_lines: set[str]) -> str:
    """Remove lines that are known headers/footers."""
    if not noise_lines:
        return text
    lines = text.splitlines(keepends=True)
    cleaned = []
    for line in lines:
        if line.strip() in noise_lines:
            continue
        cleaned.append(line)
    return "".join(cleaned)


def _dehyphenate(text: str) -> str:
    """
    Rejoin words split across line breaks with a hyphen.
    Pattern: word-\\nword → wordword
    Must run BEFORE whitespace normalization.
    """
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)


def _normalize_whitespace(text: str) -> str:
    """
    - 3+ consecutive newlines → exactly 2 newlines (paragraph boundary)
    - Single newline NOT preceded/followed by another → space (line continuation)
    Sentinels are preserved because they contain no bare newlines that match.
    """
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Replace single newlines (not part of a double newline) with a space
    # Negative lookbehind/lookahead for \n
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text


def _remove_page_number_artifacts(text: str) -> str:
    """
    Remove isolated page numbers: lines containing only digits (1–3 chars),
    possibly surrounded by whitespace.
    """
    return re.sub(r"(?m)^\s*\d{1,3}\s*$", "", text)


def _unicode_normalize(text: str) -> str:
    """
    NFKC normalization: resolves ligatures (ﬁ→fi), smart quotes,
    non-breaking spaces, etc.
    """
    return unicodedata.normalize("NFKC", text)


def _build_page_offsets(cleaned_text: str) -> dict[int, int]:
    """
    Build a mapping of {page_number: char_offset_of_sentinel} in cleaned text.
    Used downstream to resolve source_page for any char_start offset.
    Page N's content starts after the sentinel for page N-1.
    """
    offsets = {}
    for match in SENTINEL_RE.finditer(cleaned_text):
        page_num = int(match.group(1))
        offsets[page_num] = match.start()
    return offsets


def resolve_page(char_offset: int, page_offsets: dict[int, int]) -> int:
    """
    Given a character offset in cleaned_text and the page_offsets map,
    return the 1-based page number that contains that offset.

    page_offsets maps: sentinel_page_num → offset of that sentinel.
    Content before sentinel N belongs to page N.
    Content after sentinel N belongs to page N+1.
    """
    page = 1
    for sentinel_page, sentinel_offset in sorted(page_offsets.items()):
        if char_offset > sentinel_offset:
            page = sentinel_page + 1
        else:
            break
    return page


def clean_text(
    raw_text: str,
    output_dir: str = "data",
    header_footer_threshold: float = 0.8,
) -> tuple[str, dict]:
    """
    Apply the full cleaning pipeline to raw extracted text.

    Args:
        raw_text:                  Full text with <<<PAGE_BREAK:N>>> sentinels.
        output_dir:                Directory to write outputs.
        header_footer_threshold:   Fraction of pages a line must appear on to be removed.

    Returns:
        (cleaned_text, page_offsets) where:
          cleaned_text  - fully cleaned text, sentinels intact
          page_offsets  - {page_num: sentinel_char_offset} in cleaned_text
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Cleaning pipeline:")

    # Step 0: split into pages for header/footer detection
    pages = _split_into_pages(raw_text)
    print(f"  Pages detected: {len(pages)}")

    # Step 1: detect and strip headers/footers
    noise_lines = _detect_header_footer_lines(pages, threshold=header_footer_threshold)
    print(f"  Header/footer lines detected: {len(noise_lines)}")
    if noise_lines:
        print(f"  Removing: {list(noise_lines)[:5]}{'...' if len(noise_lines) > 5 else ''}")
    text = _strip_header_footer(raw_text, noise_lines)

    # Step 2: dehyphenation (before whitespace normalization)
    text = _dehyphenate(text)
    print("  Dehyphenation applied")

    # Step 3: normalize whitespace
    text = _normalize_whitespace(text)
    print("  Whitespace normalized")

    # Step 4: remove isolated page number artifacts
    text = _remove_page_number_artifacts(text)
    print("  Page number artifacts removed")

    # Step 5: unicode normalization
    text = _unicode_normalize(text)
    print("  Unicode normalized (NFKC)")

    # Step 6: build page offsets from cleaned text (sentinels survive all steps)
    page_offsets = _build_page_offsets(text)
    print(f"  Page offsets computed: {len(page_offsets)} sentinels found")

    # Write outputs
    cleaned_path = output_dir / "cleaned_text.txt"
    cleaned_path.write_text(text, encoding="utf-8")
    print(f"  Wrote cleaned text: {cleaned_path} ({len(text):,} chars)")

    offsets_path = output_dir / "page_offsets.json"
    offsets_path.write_text(
        json.dumps({str(k): v for k, v in page_offsets.items()}, indent=2),
        encoding="utf-8"
    )
    print(f"  Wrote page offsets: {offsets_path}")

    return text, page_offsets


def load_cleaned_text(data_dir: str = "data") -> tuple[str, dict]:
    """
    Load previously saved cleaned_text.txt and page_offsets.json.
    Returns (cleaned_text, page_offsets).
    """
    data_dir = Path(data_dir)
    cleaned_text = (data_dir / "cleaned_text.txt").read_text(encoding="utf-8")
    raw_offsets = json.loads((data_dir / "page_offsets.json").read_text(encoding="utf-8"))
    page_offsets = {int(k): v for k, v in raw_offsets.items()}
    return cleaned_text, page_offsets


if __name__ == "__main__":
    import sys
    from src.extract import extract_pdf

    if len(sys.argv) < 2:
        print("Usage: python -m src.clean <pdf_path> [data_dir]")
        sys.exit(1)

    pdf = sys.argv[1]
    data = sys.argv[2] if len(sys.argv) > 2 else "data"

    raw, _ = extract_pdf(pdf, data)
    clean_text(raw, data)
