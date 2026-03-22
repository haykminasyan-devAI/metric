"""
Build RAG Index (dense-only)
────────────────────────────
Reads all bank .txt files, splits into product-aware chunks, then builds:
  1. ChromaDB vector index (dense retrieval)

Chunking strategy:
  - Detect section headers (CREDITS & LOANS / DEPOSITS & SAVINGS / BRANCH LOCATIONS).
  - Within each section detect product headers (all-caps / keyword lines).
  - Each product block becomes one chunk; oversized blocks are split by line.
  - Branch data: each branch becomes its own chunk.
  - Every chunk is prefixed with bank name + section for self-contained context.

Run from the project root:
    python agent/build_index.py
"""

import os
import re

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DATA_DIR = os.getenv("BANK_DATA_DIR", os.path.join(BASE_DIR, "bank_data"))
CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(BASE_DIR, "chroma_db"))
COLLECTION_NAME = "bank_data"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "Metric-AI/armenian-text-embeddings-1")

TARGET_CHUNK_CHARS = 600
MAX_CHUNK_CHARS = 900
OVERLAP_LINES = 2
MIN_CHUNK_CHARS = 60

SECTION_HEADERS = {"CREDITS & LOANS", "DEPOSITS & SAVINGS", "BRANCH LOCATIONS"}
SECTION_ALIASES = {
    "SECTION: LOANS & CREDITS": "CREDITS & LOANS",
    "SECTION: CREDITS & LOANS": "CREDITS & LOANS",
    "SECTION: DEPOSITS": "DEPOSITS & SAVINGS",
    "SECTION: DEPOSITS & SAVINGS": "DEPOSITS & SAVINGS",
    "SECTION: BRANCHES": "BRANCH LOCATIONS",
    "SECTION: BRANCH LOCATIONS": "BRANCH LOCATIONS",
}

RE_UPPERCASE_ARM = re.compile(r"^[\u0531-\u0556A-Z\s\d\.,\-«»/()]+$")
RE_HAS_ARM_UPPER = re.compile(r"[\u0531-\u0556]")
PRODUCT_KEYWORDS = (
    "վարկ", "ավանդ", "դեպոզիտ", "հիփոթեք", "օվերդրաֆտ",
    "վարկային գիծ", "մասնաճյուղ",
)


def _is_product_header(line: str) -> bool:
    s = line.strip()
    if len(s) < 4 or len(s) > 120:
        return False
    if ":" in s:
        return False
    low = s.lower()
    if RE_HAS_ARM_UPPER.search(s) and RE_UPPERCASE_ARM.match(s) and s == s.upper():
        return True
    if any(k in low for k in PRODUCT_KEYWORDS) and not re.search(r"\d", s):
        return True
    return False


def _split_large_block(block: str, max_chars: int) -> list[str]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for ln in lines:
        projected = cur_len + len(ln) + (1 if cur else 0)
        if projected > max_chars and cur:
            out.append("\n".join(cur).strip())
            overlap = cur[-OVERLAP_LINES:] if len(cur) >= OVERLAP_LINES else cur[:]
            overlap_len = sum(len(l) for l in overlap) + max(0, len(overlap) - 1)
            if overlap_len + len(ln) + 1 <= max_chars:
                cur = list(overlap) + [ln]
            else:
                cur = [ln]
            cur_len = sum(len(l) for l in cur) + max(0, len(cur) - 1)
        else:
            cur.append(ln)
            cur_len = projected

    if cur:
        out.append("\n".join(cur).strip())
    return [x for x in out if len(x) >= MIN_CHUNK_CHARS]


def _chunk_branches(text: str, bank_name: str) -> list[dict]:
    """Split branch section into per-branch chunks."""
    lines = text.splitlines()
    branches: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                branches.append(current)
                current = []
            continue

        is_header = (
            RE_HAS_ARM_UPPER.search(stripped)
            and RE_UPPERCASE_ARM.match(stripped)
            and len(stripped) > 3
            and len(stripped) < 60
            and not any(c.isdigit() for c in stripped)
        )

        if is_header and current and len(current) >= 2:
            branches.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        branches.append(current)

    merged: list[list[str]] = []
    for branch in branches:
        text_block = "\n".join(branch)
        if merged and len(text_block) < MIN_CHUNK_CHARS:
            merged[-1].extend(branch)
        else:
            merged.append(branch)

    records = []
    section_label = "Մասնաճյուղներ"
    for branch_lines in merged:
        text_block = "\n".join(branch_lines).strip()
        if len(text_block) < MIN_CHUNK_CHARS:
            continue
        prefix = f"[{bank_name} — {section_label}]\n"
        if len(text_block) > MAX_CHUNK_CHARS:
            for sub in _split_large_block(text_block, MAX_CHUNK_CHARS):
                records.append({
                    "bank": bank_name,
                    "section": "BRANCH LOCATIONS",
                    "text": prefix + sub,
                })
        else:
            records.append({
                "bank": bank_name,
                "section": "BRANCH LOCATIONS",
                "text": prefix + text_block,
            })
    return records


def _chunk_products(text: str, bank_name: str, section: str) -> list[dict]:
    """Split a credits/deposits section into product-aware chunks."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    section_label_map = {
        "CREDITS & LOANS": "Վարկեր",
        "DEPOSITS & SAVINGS": "Ավանդներ",
    }
    label = section_label_map.get(section, section)

    blocks: list[str] = []
    current_lines: list[str] = []

    for ln in lines:
        if _is_product_header(ln) and current_lines:
            blocks.append("\n".join(current_lines).strip())
            current_lines = [ln]
        else:
            current_lines.append(ln)

    if current_lines:
        blocks.append("\n".join(current_lines).strip())

    merged: list[str] = []
    for b in blocks:
        if merged and len(b) < MIN_CHUNK_CHARS:
            merged[-1] = f"{merged[-1]}\n{b}".strip()
        else:
            merged.append(b)

    records: list[dict] = []
    for b in merged:
        prefix = f"[{bank_name} — {label}]\n"
        if len(b) > MAX_CHUNK_CHARS:
            for sub in _split_large_block(b, MAX_CHUNK_CHARS):
                records.append({
                    "bank": bank_name,
                    "section": section,
                    "text": prefix + sub,
                })
        elif len(b) >= MIN_CHUNK_CHARS:
            records.append({
                "bank": bank_name,
                "section": section,
                "text": prefix + b,
            })
    return records


def parse_bank_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    bank_name = ""
    lines = content.splitlines()
    if lines and lines[0].startswith("BANK:"):
        bank_name = lines[0].replace("BANK:", "").strip()

    sections: dict[str, str] = {}
    current_section: str | None = None
    buffer: list[str] = []

    for line in lines[1:]:
        stripped = line.strip()
        canonical = SECTION_ALIASES.get(stripped, stripped)
        if canonical in SECTION_HEADERS:
            if current_section:
                sections[current_section] = "\n".join(buffer).strip()
            current_section = canonical
            buffer = []
        else:
            buffer.append(line)

    if current_section and buffer:
        sections[current_section] = "\n".join(buffer).strip()

    records: list[dict] = []
    for section, text in sections.items():
        if section == "BRANCH LOCATIONS":
            records.extend(_chunk_branches(text, bank_name))
        else:
            records.extend(_chunk_products(text, bank_name, section))

    return records


def build_index():
    print("\nBuilding RAG index (dense-only)")
    print("=" * 60)

    print(f"Loading embedding model: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded.\n")

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    txt_files = [f for f in sorted(os.listdir(BANK_DATA_DIR)) if f.endswith(".txt")]
    all_records: list[dict] = []

    for filename in txt_files:
        filepath = os.path.join(BANK_DATA_DIR, filename)
        records = parse_bank_file(filepath)
        print(f"  {filename}: {len(records)} chunks")
        all_records.extend(records)

    if not all_records:
        print("No chunks found. Make sure bank_data/ has .txt files.")
        return

    print(f"\nTotal chunks: {len(all_records)}")

    # Dense index (ChromaDB)
    print("Embedding chunks for dense index...")
    texts = [r["text"] for r in all_records]
    metadatas = [{"bank": r["bank"], "section": r["section"]} for r in all_records]
    ids = [f"chunk_{i}" for i in range(len(all_records))]

    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    BATCH = 5000
    for start in range(0, len(ids), BATCH):
        end = min(start + BATCH, len(ids))
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end].tolist(),
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )

    print(f"Dense index: {collection.count()} vectors stored in {CHROMA_DIR}")

    sep = "=" * 60
    print(f"\n{sep}")
    print("Index build complete.")


if __name__ == "__main__":
    build_index()
