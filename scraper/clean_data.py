"""
Bank Data Cleaner  v3
─────────────────────
Reads scraped .txt files from bank_data/ and produces cleaner text optimized
for product-level RAG chunking.

Main goals:
  - Remove navigation/UI noise (CTA buttons, menu items, legal boilerplate)
  - Merge financial labels with their values (including reversed order)
  - Deduplicate repeated text blocks
  - Keep structured content useful for retrieval
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DATA_DIR = os.path.join(BASE_DIR, "bank_data")

# ── Exact noise lines (lowercase after strip) ─────────────────────────────────
EXACT_NOISE = {
    "hy", "en", "ru", "ir", "հայ", "arm",
    "scroll down", "loading...", "subscribe", "internet banking",
    "your browser does not support html5 video.",
    "your browser does not support the video tag.",
    "aeb online", "aeb mobile", "aeb payments",
    # Common CTA / menu labels
    "թողնել հայտ", "մանրամասներ", "գնել հիմա", "դիմիր օնլայն",
    "տեսնել ավելին", "իմանալ ավելին", "ավելին",
    "թարմացվել է", "պայմանների արխիվ", "հարցեր ունե՞ս",
    "բանկի մասին", "մասնաճյուղեր",
    "այլ ծառայություններ", "ծառայություններ", "pos տերմինալներ",
    "ներդրումային ծառայություններ", "անհատական պահատուփ",
    "արտարժույթի փոխանակում", "կառուցապատողների ցանկ",
    # Scraper leftovers / language toggles
    "hh դրամ", "loan calculator", "ավանդի հաշվիչ", "վարկային հաշվիչ",
    "pdf", "այլ", "փնտրիր հիմա",
}

# ── Line prefixes that signal noise ───────────────────────────────────────────
NOISE_PREFIXES = (
    "source: http",
    "myameria", "myinvest", "myhome", "mycar", "mytour", "mypay", "mypoint",
    "© ",
    "feedback",
    "acra.am", "abcfinance.am",
    "www.", "http",
    "bank@", "fastcare@",
    "swift code",
)

# ── Substrings that indicate noise ────────────────────────────────────────────
NOISE_SUBSTRINGS = (
    "myameria",
    "download",
    "google pay",
    "apple pay",
    "ussd",
    "sms-",
    "eventhub",
    "subscribe",
    "© 20",
    "terms of use",
    "privacy",
    "cookie",
    "html5 video",
    "video tag",
    "swift code",
    "copyright",
    "all rights reserved",
    "ձեր ֆինանսական տեղեկատու",
    "ձեր ֆինանսական տեղեկատուն",
    "ուշադրություն",
    "պայմանների արխիվ",
    "հաշվարկը կրում է տեղեկատվական բնույթ",
    "վարկային պատմության և սքոր գնահատականի վերաբերյալ տեղեկատվություն",
    "տեղեկատվական ամփոփագիր",
    "տեղեկատվական ամոփոփագիր",
)

# ── Regex helpers ──────────────────────────────────────────────────────────────
RE_PHONE    = re.compile(r"^\+?\d[\d\s\(\)\-]{6,}$")
RE_NUMBERS  = re.compile(r"^[\d,.\s]+$")
RE_TIMESTAMP = re.compile(r"\d{2}\.\d{2}\.\d{4}")
RE_URL      = re.compile(r"^https?://|^www\.")
RE_HAS_DIGIT = re.compile(r"\d")
RE_DATE_SPLIT = re.compile(r"^\(.*\d{2}\.\d{2}\.\d{2,4}\)$")
COMPOUND_SPLIT_RE = re.compile(
    r"\s+(?=("
    r"Անվանական տոկոսադրույք|Առավելագույն գումար|Մինիմալ կանխավճար|"
    r"Առավելագույն ժամկետ|Վաղաժամկետ մարման տույժ|Վարկի գումար|Վարկի ժամկետ|"
    r"Վարկի արժույթ|Սուբսիդավորում|Տեսակը|Վարկառու|Համավարկառու"
    r")\s*:?)"
)

SECTION_HEADERS = {"CREDITS & LOANS", "DEPOSITS & SAVINGS", "BRANCH LOCATIONS"}

# Label/value helpers for Armenian bank facts
LABEL_KEYWORDS = (
    "տոկոս", "տոկոսադրույք", "փաստացի տոկոսադրույք", "անվանական տոկոսադրույք",
    "գումար", "վարկի գումար", "առավելագույն գումար", "նվազագույն գումար",
    "ժամկետ", "մարման ժամկետ", "տրամադրում", "տրամադրման",
    "արժույթ", "կանխավճար", "վաղաժամկետ մարման տույժ", "սուբսիդավորում",
)
VALUE_TOKENS = (
    "մինչև", "սկսած", "առկա չէ", "չի կիրառվում", "չի պահանջվում",
    "հհ դրամ", "amd", "տարի", "ամիս", "օր", "րոպե",
)


def _is_value_line(line: str) -> bool:
    """Return True if a line looks like a financial value."""
    s = line.strip()
    if not s:
        return False
    low = s.lower()
    if ":" in s and _is_label_line(s.split(":", 1)[0]):
        return False
    return bool(RE_HAS_DIGIT.search(s)) or any(tok in low for tok in VALUE_TOKENS)


def _is_label_line(line: str) -> bool:
    """Return True if a line looks like a standalone field label."""
    s = line.strip()
    if not s or len(s) > 60 or len(s) < 3:
        return False
    if RE_HAS_DIGIT.search(s):
        return False
    if s in SECTION_HEADERS:
        return False
    low = s.lower()
    if ":" in s:
        return False
    if any(low == kw or low.endswith(kw) for kw in LABEL_KEYWORDS):
        return True
    # ASCII-only labels like "Amount", "Term"
    ascii_chars = s.encode("ascii", errors="ignore").decode("ascii")
    return ascii_chars.lower() in {"amount", "term", "rate", "currency", "duration"}


def join_label_value_pairs(lines: list[str]) -> list[str]:
    """
    Scan lines and join standalone label lines with their following value line.

    Before:
        Токоs
        սksum 13.5%
    After:
        Токоs: сksum 13.5%
    """
    result: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""

        # Forward pattern: Label -> Value (safe mode)
        if _is_label_line(cur) and _is_value_line(nxt) and not _is_label_line(nxt):
            result.append(f"{cur}: {nxt}")
            i += 2
            continue

        # Reverse pattern: Value -> Label (very strict to avoid bad merges)
        if (
            _is_value_line(cur)
            and _is_label_line(nxt)
            and ":" not in cur
            and len(cur) <= 28
            and len(nxt) <= 35
        ):
            result.append(f"{nxt}: {cur}")
            i += 2
            continue

        result.append(cur)
        i += 1
    return result


def normalize_fragments(lines: list[str]) -> list[str]:
    """
    Repair common scraper line-break artifacts to improve downstream chunking:
      - remove standalone PDF tokens
      - join split "ուժի մեջ է ... -ից մինչև ..." ranges
      - join obvious parenthesis continuations
      - merge very short continuation lines with previous content
    """
    out: list[str] = []
    i = 0

    while i < len(lines):
        cur = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""

        if not cur:
            out.append("")
            i += 1
            continue

        # Drop standalone PDF marker lines.
        if cur.lower() in {"pdf", "pdf."}:
            i += 1
            continue

        # Remove trailing " PDF".
        cur = re.sub(r"\s+PDF$", "", cur, flags=re.IGNORECASE)
        cur = re.sub(r"\bPDF\b", "", cur, flags=re.IGNORECASE).strip()

        # Join split validity ranges:
        # "(ուժի մեջ է 01" + "-ից մինչև 15.03.26)" -> "(ուժի մեջ է 01-ից մինչև 15.03.26)"
        if cur.startswith("(ուժի մեջ է") and nxt.startswith("-ից մինչև"):
            merged = f"{cur}{nxt}"
            out.append(merged)
            i += 2
            continue

        # Join trailing hyphen with "ից մինչև ...".
        if cur.endswith("-") and nxt.startswith("ից մինչև"):
            out.append(f"{cur}{nxt}")
            i += 2
            continue

        # If current line is just "ից մինչև ...", append to previous date header.
        if cur.startswith("ից մինչև") and out:
            prev = out[-1].strip()
            if prev and ("ուժի մեջ է" in prev or prev.endswith("-")):
                out[-1] = f"{prev}{cur}"
                i += 1
                continue

        # Recover broken date parentheses.
        if cur.startswith("(ուժի մեջ է") and "ից մինչև" in cur and not cur.endswith(")"):
            cur = f"{cur})"

        # Join unfinished parenthesis with next line.
        if cur.endswith("(") and nxt:
            out.append(f"{cur}{nxt}")
            i += 2
            continue

        # Split compound field lines if they contain multiple key labels.
        if len(cur) > 120 and COMPOUND_SPLIT_RE.search(cur):
            parts = [p.strip() for p in COMPOUND_SPLIT_RE.split(cur) if p.strip()]
            out.extend(parts)
            i += 1
            continue

        # Join obvious continuation line fragments (only very short tails).
        if (
            out
            and cur
            and len(cur) <= 18
            and not _is_label_line(cur)
            and not _is_value_line(cur)
            and cur not in SECTION_HEADERS
            and not cur.startswith("BANK:")
            and not RE_DATE_SPLIT.match(cur)
        ):
            prev = out[-1].strip()
            if prev and prev[-1] not in ".:;!?":
                out[-1] = f"{prev} {cur}"
                i += 1
                continue

        out.append(cur)
        i += 1

    return out


def remove_high_frequency_noise(lines: list[str]) -> list[str]:
    """
    Remove short boilerplate lines that repeat too often in one file and do not
    carry numeric/product information.
    """
    counts: dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if s:
            counts[s] = counts.get(s, 0) + 1

    result: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            result.append(s)
            continue
        # frequent + short + non-numeric + not explicit label/value
        if (
            counts.get(s, 0) >= 12
            and len(s) <= 40
            and not _is_value_line(s)
            and not _is_label_line(s)
            and s not in SECTION_HEADERS
            and not s.startswith("BANK:")
        ):
            continue
        result.append(s)
    return result


def remove_duplicate_blocks(lines: list[str]) -> list[str]:
    """
    Remove duplicate paragraph blocks. A block is consecutive non-empty lines
    separated by blank lines. Keep only the first occurrence of each block.
    """
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.strip() == "":
            blocks.append(current)
            blocks.append([])  # blank separator
            current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    seen: set[str] = set()
    result: list[str] = []

    for block in blocks:
        if not block:           # blank separator
            result.append("")
            continue
        key = "\n".join(b.strip() for b in block)
        if key in seen:
            continue
        seen.add(key)
        result.extend(block)
        result.append("")

    # Strip trailing blanks
    while result and result[-1] == "":
        result.pop()
    return result


def is_noise(line: str) -> bool:
    """Return True if a line should be completely removed."""
    stripped = line.strip()
    lower = stripped.lower()

    if not stripped:
        return False

    if stripped.startswith("BANK:"):
        return False

    # Too short
    if len(stripped) <= 2:
        return True

    # Browser tab titles
    if " | " in stripped:
        return True

    # Opening-hours UI labels from branch widgets
    if lower.startswith("կբացվի "):
        return True

    if lower in EXACT_NOISE:
        return True

    if any(lower.startswith(p) for p in NOISE_PREFIXES):
        return True

    if any(s in lower for s in NOISE_SUBSTRINGS):
        return True

    if RE_PHONE.match(stripped):
        return True

    # Pure numbers without units are usually calculator/UI noise
    if RE_NUMBERS.match(stripped) and "%" not in stripped and len(stripped) < 20:
        return True

    if RE_TIMESTAMP.search(stripped) and len(stripped) < 30:
        return True

    if RE_URL.match(stripped):
        return True

    MAP_NOISE_MARKERS = [
        "\u057f\u0565\u0572\u0561\u0583\u0578\u056d\u0565\u056c",
        "\u0574\u0565\u056e\u0561\u0581\u0576\u0565\u056c",
        "\u0583\u0578\u0584\u0580\u0561\u0581\u0576\u0565\u056c",
        "\u057d\u057f\u0565\u0572\u0576\u0561\u0575\u056b\u0576 \u0564\u0575\u0578\u0582\u0580\u0561\u0576\u0581\u0578\u0582\u0574",
        "\u0584\u0561\u0580\u057f\u0565\u0566\u056b \u057f\u057e\u0575\u0561\u056c\u0576\u0565\u0580",
        "\u0584\u0561\u0580\u057f\u0565\u0566\u0561\u0563\u0580\u0561\u056f\u0561\u0576",
        "\u0570\u0561\u0572\u0578\u0580\u0564\u0565\u056c \u0584\u0561\u0580\u057f\u0565\u0566\u056b",
        "\u0574\u0565\u057f\u0580\u056b\u056f\u0561\u056f\u0561\u0576",
        "\u0562\u0580\u056b\u057f\u0561\u0576\u0561\u056f\u0561\u0576",
    ]
    if any(m in lower for m in MAP_NOISE_MARKERS):
        return True

    return False


def clean_text(raw: str) -> str:
    """
    Clean raw scraped text in 4 passes:
      Pass 1 — Remove separator lines and noise lines
      Pass 2 — Join label-value pairs
      Pass 3 — Collapse blank lines, remove consecutive duplicates
      Pass 4 — Remove duplicate paragraph blocks
    """
    lines = raw.splitlines()

    # ── Pass 1: remove separators and noise ──────────────────────────────────
    pass1: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Drop scraper separator lines (═══ or ───)
        if set(stripped) <= {"─", "═"} and len(stripped) > 3:
            continue
        if stripped and is_noise(stripped):
            continue
        pass1.append(stripped)

    # ── Pass 2: remove highly repetitive short boilerplate ───────────────────
    pass2 = remove_high_frequency_noise(pass1)

    # ── Pass 3: join label-value pairs ───────────────────────────────────────
    pass3 = join_label_value_pairs(pass2)

    # ── Pass 4: normalize broken line fragments ──────────────────────────────
    pass4 = normalize_fragments(pass3)

    # ── Pass 5: collapse blanks + remove consecutive duplicate lines ─────────
    pass5: list[str] = []
    prev_line = None
    prev_empty = False

    for line in pass4:
        stripped = line.strip()

        if not stripped:
            if not prev_empty:
                pass5.append("")
            prev_empty = True
            prev_line = ""
            continue

        prev_empty = False
        if stripped == prev_line:
            continue

        pass5.append(stripped)
        prev_line = stripped

    # ── Pass 6: remove duplicate paragraph blocks ─────────────────────────────
    pass6 = remove_duplicate_blocks(pass5)

    # Strip leading/trailing blanks
    while pass6 and pass6[0] == "":
        pass6.pop(0)
    while pass6 and pass6[-1] == "":
        pass6.pop()

    return "\n".join(pass6)


def process_bank_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    return clean_text(raw)


def run_cleaner():
    txt_files = [f for f in sorted(os.listdir(BANK_DATA_DIR)) if f.endswith(".txt")]

    if not txt_files:
        print("No .txt files found in bank_data/. Run the scraper first.")
        return

    print("\nBank Data Cleaner  v3")
    print("=" * 60)

    for filename in txt_files:
        filepath = os.path.join(BANK_DATA_DIR, filename)
        raw_size = os.path.getsize(filepath) / 1024
        print(f"\nCleaning: {filename}  (raw: {raw_size:.1f} KB)")

        cleaned = process_bank_file(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)

        clean_size = len(cleaned.encode("utf-8")) / 1024
        reduction = 100 * (1 - clean_size / raw_size)
        print(f"  Done → {clean_size:.1f} KB  (reduced by {reduction:.0f}%)")

    print(f"\n{'=' * 60}")
    print("Cleaning complete.")


if __name__ == "__main__":
    run_cleaner()
