"""
chunk.py
--------
Implements the three chunking strategies defined in Phase 3 of the plan.

Each strategy returns a list of chunk dicts with keys:
  chunk_id    - str, e.g. "fixed_p04_003"
  strategy    - str, one of 'fixed' | 'structural' | 'semantic'
  source_doc  - str, PDF filename
  source_page - int, 1-based page number
  char_start  - int, offset in cleaned_text (inclusive)
  char_end    - int, offset in cleaned_text (exclusive)
  token_count - int, tiktoken cl100k_base count
  chunk_text  - str, the chunk content

Strategy A — Fixed-size:     512 tokens, 64-token overlap
Strategy B — Structural:     paragraph→line→sentence fallback, 400-token target, 600 max, 50 min
Strategy C — Semantic window: 5-sentence window, stride 2
"""

import re
import json
from pathlib import Path
from typing import Optional

import tiktoken
import spacy

# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

SENTINEL_RE = re.compile(r"<<<PAGE_BREAK:\d+>>>")
ENCODING = tiktoken.get_encoding("cl100k_base")

# Lazy-load spaCy model (only needed for semantic strategy)
_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            raise OSError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
    return _NLP


def _token_count(text: str) -> int:
    return len(ENCODING.encode(text))


def _resolve_page(char_offset: int, page_offsets: dict) -> int:
    """
    Return 1-based page number for a given char offset.
    page_offsets: {sentinel_page_num (int): sentinel_char_offset (int)}
    Content before sentinel N belongs to page N; after belongs to page N+1.
    """
    page = 1
    for sentinel_page, sentinel_offset in sorted(page_offsets.items()):
        if char_offset > sentinel_offset:
            page = sentinel_page + 1
        else:
            break
    return page


def _strip_sentinels(text: str) -> str:
    """Remove sentinel markers from chunk text."""
    return SENTINEL_RE.sub("", text).strip()


def _make_chunk(
    strategy: str,
    source_doc: str,
    page: int,
    seq: int,
    char_start: int,
    char_end: int,
    text: str,
) -> dict:
    clean_text = _strip_sentinels(text)
    return {
        "chunk_id": f"{strategy}_p{page:02d}_{seq:03d}",
        "strategy": strategy,
        "source_doc": source_doc,
        "source_page": page,
        "char_start": char_start,
        "char_end": char_end,
        "token_count": _token_count(clean_text),
        "chunk_text": clean_text,
    }


# ---------------------------------------------------------------------------
# Strategy A: Fixed-size with overlap
# ---------------------------------------------------------------------------

FIXED_SIZE = 512    # tokens
FIXED_OVERLAP = 64  # tokens
FIXED_STEP = FIXED_SIZE - FIXED_OVERLAP  # 448


def chunk_fixed(
    cleaned_text: str,
    page_offsets: dict,
    source_doc: str = "source.pdf",
) -> list[dict]:
    """
    Fixed-size chunking: 512-token windows, 64-token overlap.

    Tokenizes the full cleaned text, slides the window, decodes each window
    back to text, and maps token positions back to character offsets.
    """
    # Strip sentinels before tokenizing (offsets tracked separately)
    # Build a sentinel-free version and a mapping from sentinel-free offsets
    # back to original offsets using a position list.

    # We need char offsets in the ORIGINAL cleaned_text (with sentinels),
    # so we track positions by iterating the original string.
    positions = []  # positions[i] = char index in cleaned_text for sentinel-free char i
    sentinel_free_chars = []

    i = 0
    while i < len(cleaned_text):
        m = SENTINEL_RE.match(cleaned_text, i)
        if m:
            i = m.end()
            continue
        sentinel_free_chars.append(cleaned_text[i])
        positions.append(i)
        i += 1

    sentinel_free_text = "".join(sentinel_free_chars)

    # Tokenize the sentinel-free text
    tokens = ENCODING.encode(sentinel_free_text)
    # Get byte offsets of each token in sentinel_free_text
    # tiktoken doesn't expose char offsets directly; reconstruct by decoding incrementally
    token_char_starts = _get_token_char_offsets(sentinel_free_text, tokens)

    chunks = []
    seq = 0
    window_start = 0

    while window_start < len(tokens):
        window_end = min(window_start + FIXED_SIZE, len(tokens))
        window_tokens = tokens[window_start:window_end]

        # Char offsets in sentinel_free_text
        sf_char_start = token_char_starts[window_start]
        if window_end < len(tokens):
            sf_char_end = token_char_starts[window_end]
        else:
            sf_char_end = len(sentinel_free_text)

        # Map back to original cleaned_text char offsets
        orig_char_start = positions[sf_char_start] if sf_char_start < len(positions) else len(cleaned_text)
        orig_char_end = positions[sf_char_end - 1] + 1 if sf_char_end - 1 < len(positions) else len(cleaned_text)

        page = _resolve_page(orig_char_start, page_offsets)
        chunk_text = ENCODING.decode(window_tokens)

        chunk = _make_chunk(
            strategy="fixed",
            source_doc=source_doc,
            page=page,
            seq=seq,
            char_start=orig_char_start,
            char_end=orig_char_end,
            text=chunk_text,
        )

        # Skip near-empty chunks
        if chunk["token_count"] >= 10:
            chunks.append(chunk)
            seq += 1

        if window_end >= len(tokens):
            break
        window_start += FIXED_STEP

    print(f"  [fixed]      {len(chunks)} chunks, avg {_avg_tokens(chunks):.0f} tokens")
    return chunks


def _get_token_char_offsets(text: str, tokens: list) -> list[int]:
    """
    Build a list where token_char_starts[i] = char offset in `text` where token i begins.
    Reconstructs by decoding tokens one by one and tracking position.
    """
    offsets = []
    pos = 0
    for token in tokens:
        offsets.append(pos)
        decoded = ENCODING.decode([token])
        pos += len(decoded)
    return offsets


# ---------------------------------------------------------------------------
# Strategy B: Structural / Recursive
# ---------------------------------------------------------------------------

STRUCTURAL_TARGET = 400   # tokens — target chunk size
STRUCTURAL_MAX = 600      # tokens — hard cap; triggers fallback splits
STRUCTURAL_MIN = 50       # tokens — below this, merge with next chunk


def chunk_structural(
    cleaned_text: str,
    page_offsets: dict,
    source_doc: str = "source.pdf",
) -> list[dict]:
    """
    Structural chunking with 3-tier fallback:
      1. Split on paragraph boundaries (\\n\\n)
      2. If segment > MAX, split on single newline (\\n)
      3. If still > MAX, split on sentence boundary (?<=[.!?])\\s+
    Then greedily merge segments toward TARGET tokens.
    """
    # Collect (text, char_start, char_end) segments by splitting on \\n\\n
    segments = _split_with_offsets(cleaned_text, r"\n\n")

    # Apply fallback splits for oversized segments
    refined = []
    for seg_text, seg_start, seg_end in segments:
        tc = _token_count(_strip_sentinels(seg_text))
        if tc <= STRUCTURAL_MAX:
            refined.append((seg_text, seg_start, seg_end))
        else:
            # Fallback 1: single newline
            sub = _split_with_offsets_within(seg_text, seg_start, r"\n")
            still_over = any(_token_count(_strip_sentinels(t)) > STRUCTURAL_MAX for t, _, _ in sub)
            if still_over:
                # Fallback 2: sentence boundary
                final_sub = []
                for st, ss, se in sub:
                    if _token_count(_strip_sentinels(st)) > STRUCTURAL_MAX:
                        final_sub.extend(_split_with_offsets_within(st, ss, r"(?<=[.!?])\s+"))
                    else:
                        final_sub.append((st, ss, se))
                refined.extend(final_sub)
            else:
                refined.extend(sub)

    # Greedy merge toward TARGET
    chunks = []
    seq = 0
    current_parts = []
    current_tokens = 0

    def flush(parts):
        nonlocal seq
        if not parts:
            return
        combined_text = " ".join(t for t, _, _ in parts)
        c_start = parts[0][1]
        c_end = parts[-1][2]
        page = _resolve_page(c_start, page_offsets)
        chunk = _make_chunk("structural", source_doc, page, seq, c_start, c_end, combined_text)
        if chunk["token_count"] >= STRUCTURAL_MIN:
            chunks.append(chunk)
            seq += 1

    for seg_text, seg_start, seg_end in refined:
        tc = _token_count(_strip_sentinels(seg_text))
        if tc == 0:
            continue

        if current_tokens + tc <= STRUCTURAL_TARGET:
            current_parts.append((seg_text, seg_start, seg_end))
            current_tokens += tc
        else:
            flush(current_parts)
            current_parts = [(seg_text, seg_start, seg_end)]
            current_tokens = tc

    flush(current_parts)

    print(f"  [structural] {len(chunks)} chunks, avg {_avg_tokens(chunks):.0f} tokens")
    return chunks


def _split_with_offsets(text: str, pattern: str) -> list[tuple[str, int, int]]:
    """Split text by regex pattern, returning (segment, start, end) tuples."""
    result = []
    last_end = 0
    for m in re.finditer(pattern, text):
        seg = text[last_end:m.start()]
        if seg:
            result.append((seg, last_end, m.start()))
        last_end = m.end()
    if last_end < len(text):
        result.append((text[last_end:], last_end, len(text)))
    return result


def _split_with_offsets_within(
    text: str, base_offset: int, pattern: str
) -> list[tuple[str, int, int]]:
    """
    Split `text` by pattern, returning (segment, abs_start, abs_end).
    abs_start = base_offset + local_start.
    """
    result = []
    last_end = 0
    for m in re.finditer(pattern, text):
        seg = text[last_end:m.start()]
        if seg:
            result.append((seg, base_offset + last_end, base_offset + m.start()))
        last_end = m.end()
    if last_end < len(text):
        result.append((text[last_end:], base_offset + last_end, base_offset + len(text)))
    return result


# ---------------------------------------------------------------------------
# Strategy C: Semantic / Sentence-Window
# ---------------------------------------------------------------------------

SEMANTIC_WINDOW = 5   # sentences per chunk
SEMANTIC_STRIDE = 2   # stride (overlap = window - stride = 3 sentences)
SEMANTIC_MAX_TOKENS = 512  # if window exceeds this, reduce to 3 sentences


def chunk_semantic(
    cleaned_text: str,
    page_offsets: dict,
    source_doc: str = "source.pdf",
) -> list[dict]:
    """
    Sliding sentence-window chunking.
    Uses spaCy en_core_web_sm for sentence segmentation.
    Window: 5 sentences, stride: 2 (60% overlap).
    Falls back to 3-sentence window if token count exceeds 512.
    """
    nlp = _get_nlp()

    # Remove sentinels before NLP (spaCy may misparse them)
    # Track original offsets via position mapping
    positions = []
    sentinel_free_chars = []
    i = 0
    while i < len(cleaned_text):
        m = SENTINEL_RE.match(cleaned_text, i)
        if m:
            # For each sentinel char, we record None (not mappable)
            i = m.end()
            continue
        sentinel_free_chars.append(cleaned_text[i])
        positions.append(i)
        i += 1

    sentinel_free_text = "".join(sentinel_free_chars)

    # Run spaCy sentence segmentation
    # Disable unnecessary pipeline components for speed
    doc = nlp(sentinel_free_text, disable=["ner", "tagger", "lemmatizer", "attribute_ruler"])
    sentences = list(doc.sents)

    if len(sentences) < SEMANTIC_WINDOW:
        print(f"  WARNING: Only {len(sentences)} sentences found — fewer than window size {SEMANTIC_WINDOW}")

    chunks = []
    seq = 0
    i = 0
    reduced_count = 0

    while i < len(sentences):
        window_size = SEMANTIC_WINDOW
        end_idx = min(i + window_size, len(sentences))
        window_sents = sentences[i:end_idx]

        # Get char offsets in sentinel_free_text
        sf_start = window_sents[0].start_char
        sf_end = window_sents[-1].end_char

        # Map back to original cleaned_text offsets
        orig_start = positions[sf_start] if sf_start < len(positions) else len(cleaned_text)
        orig_end = positions[sf_end - 1] + 1 if sf_end - 1 < len(positions) else len(cleaned_text)

        chunk_text = " ".join(s.text.strip() for s in window_sents)
        tc = _token_count(chunk_text)

        # Reduce window if over token limit
        if tc > SEMANTIC_MAX_TOKENS and window_size > 3:
            reduced_count += 1
            window_size = 3
            end_idx = min(i + window_size, len(sentences))
            window_sents = sentences[i:end_idx]
            sf_start = window_sents[0].start_char
            sf_end = window_sents[-1].end_char
            orig_start = positions[sf_start] if sf_start < len(positions) else len(cleaned_text)
            orig_end = positions[sf_end - 1] + 1 if sf_end - 1 < len(positions) else len(cleaned_text)
            chunk_text = " ".join(s.text.strip() for s in window_sents)

        page = _resolve_page(orig_start, page_offsets)
        chunk = _make_chunk("semantic", source_doc, page, seq, orig_start, orig_end, chunk_text)

        if chunk["token_count"] >= 10:
            chunks.append(chunk)
            seq += 1

        if end_idx >= len(sentences):
            break
        i += SEMANTIC_STRIDE

    if reduced_count:
        print(f"  WARNING: {reduced_count} windows reduced from 5 to 3 sentences due to token limit")

    print(f"  [semantic]   {len(chunks)} chunks, avg {_avg_tokens(chunks):.0f} tokens")
    return chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _avg_tokens(chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    return sum(c["token_count"] for c in chunks) / len(chunks)


def run_all_strategies(
    cleaned_text: str,
    page_offsets: dict,
    source_doc: str = "source.pdf",
    output_dir: str = "data",
) -> list[dict]:
    """
    Run all three strategies and save combined chunks to data/chunks.json.
    Returns the combined list.
    """
    print("\nRunning chunking strategies:")
    fixed = chunk_fixed(cleaned_text, page_offsets, source_doc)
    structural = chunk_structural(cleaned_text, page_offsets, source_doc)
    semantic = chunk_semantic(cleaned_text, page_offsets, source_doc)

    all_chunks = fixed + structural + semantic
    print(f"\n  Total chunks: {len(all_chunks)}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "chunks.json"
    out_path.write_text(json.dumps(all_chunks, indent=2), encoding="utf-8")
    print(f"  Wrote chunks: {out_path}")

    return all_chunks


if __name__ == "__main__":
    import sys
    from src.clean import load_cleaned_text

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    source_doc = sys.argv[2] if len(sys.argv) > 2 else "source.pdf"

    cleaned_text, page_offsets = load_cleaned_text(data_dir)
    run_all_strategies(cleaned_text, page_offsets, source_doc, data_dir)
