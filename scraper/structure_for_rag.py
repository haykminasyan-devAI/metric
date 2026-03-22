"""
RAG Dataset Structurer
----------------------
Converts raw bank datasets into a consistent hierarchy:

BANK: <name>

CREDITS & LOANS
SUBSECTION: <loan type>
PRODUCT: <product title>
- <field/detail>

DEPOSITS & SAVINGS
SUBSECTION: <deposit type>
PRODUCT: <product title>
- <field/detail>

BRANCH LOCATIONS
SUBSECTION: ALL BRANCHES
PRODUCT: <branch title or area>
- <address/contact/hours>
"""

from __future__ import annotations

import os
import re
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DATA_DIR = os.path.join(BASE_DIR, "bank_data")
SECTION_HEADERS = ("CREDITS & LOANS", "DEPOSITS & SAVINGS", "BRANCH LOCATIONS")

LOAN_KEYS = ("վարկ", "հիփոթեք", "օվերդրաֆտ", "վերաֆինանս", "վարկային գիծ", "լիզինգ")
DEP_KEYS = ("ավանդ", "դեպոզիտ", "խնայող", "կուտակային", "savings")
BR_KEYS = ("մասնաճյուղ", "գրասենյակ", "հասցե", "ֆիլիալ", "աշխատանքային ժամ", "office")

NOISE_EXACT = {
    "pdf", "իմանալ ավելին", "ավելին", "տեսնել ավելին", "թողնել հայտ",
    "ասա կարծիքդ", "հարցեր ունե՞ս", "դիմիր օնլայն", "loading...",
}
NOISE_PREFIX = ("http://", "https://", "www.")
RE_SPACE = re.compile(r"\s+")
RE_DIGIT = re.compile(r"\d")
RE_HOURS = re.compile(r"\d{2}[:։]\d{2}")
FIELD_LABEL_WORDS = {
    "տոկոս",
    "տոկոսադրույք",
    "անվանական տոկոսադրույք",
    "տարեկան անվանական տոկոսադրույք",
    "տարեկան փաստացի տոկոսադրույք",
    "գումար",
    "վարկի գումար",
    "առավելագույն գումար",
    "նվազագույն գումար",
    "ժամկետ",
    "վարկի ժամկետ",
    "առավելագույն ժամկետ",
    "տրամադրում",
    "արժույթ",
    "կանխավճար",
    "մինիմալ կանխավճար",
    "նվազագույն կանխավճար",
    "հասցե",
    "հեռ",
    "կառավարիչ",
    "հաճախորդների սպասարկում",
}
GENERIC_TITLE_WORDS = {
    "մանրամասներ",
    "ընդհանուր",
    "ձեր ֆինանսական տեղեկատու",
    "բանկի մասին",
    "հարցեր ունե՞ս",
    "ասա կարծիքդ",
    "թարմացվել է",
    "հայ",
    "en",
    "ru",
    "ir",
}

# Split long concatenated lines into field-like units.
SPLIT_MARKERS = re.compile(
    r"\s+(?=("
    r"Անվանական տոկոսադրույք|Տարեկան անվանական տոկոսադրույք|Տարեկան փաստացի տոկոսադրույք|"
    r"Առավելագույն գումար|Նվազագույն գումար|Վարկի գումար|Վարկի ժամկետ|Վարկի արժույթ|"
    r"Առավելագույն ժամկետ|Նվազագույն կանխավճար|Մինիմալ կանխավճար|Տրամադրում|Արժույթ|"
    r"Հասցե|Կառավարիչ|Հեռ|Հաճախորդների սպասարկում|Գործող ժամ|Աշխատանքային ժամ"
    r")\s*:?)"
)

LOAN_SUBSECTIONS = OrderedDict(
    [
        ("MORTGAGE LOANS", ("հիփոթեք", "mortgage", "բնակարան", "անշարժ գույք")),
        ("CONSUMER LOANS", ("սպառողական", "consumer", "ապառիկ")),
        ("OVERDRAFTS", ("օվերդրաֆտ", "overdraft")),
        ("CREDIT LINES", ("վարկային գիծ", "credit line")),
        ("CAR LOANS", ("ավտո", "car loan", "մեքենա")),
        ("REFINANCING", ("վերաֆինանս", "refinanc")),
        ("BUSINESS LOANS", ("business", "բիզնես", "առևտր", "գյուղատնտես", "լիզինգ")),
        ("OTHER LOANS", ()),
    ]
)

DEPOSIT_SUBSECTIONS = OrderedDict(
    [
        ("TERM DEPOSITS", ("ժամկետ", "դասական", "term", "classic")),
        ("SAVINGS ACCOUNTS", ("խնայող", "saving account", "savings")),
        ("CUMULATIVE DEPOSITS", ("կուտակային", "cumulative")),
        ("CHILD / EDUCATION DEPOSITS", ("մանկական", "երեխ", "kids", "child", "student")),
        ("BUSINESS DEPOSITS", ("business", "բիզնես")),
        ("OTHER DEPOSITS", ()),
    ]
)


def norm(text: str) -> str:
    return RE_SPACE.sub(" ", text.replace("\u00a0", " ")).strip()


def is_noise(line: str) -> bool:
    s = line.lower()
    if not s:
        return True
    if s in NOISE_EXACT:
        return True
    if any(s.startswith(p) for p in NOISE_PREFIX):
        return True
    return False


def maybe_split_line(line: str) -> list[str]:
    s = norm(line)
    if not s:
        return []
    if SPLIT_MARKERS.search(s):
        return [p.strip() for p in SPLIT_MARKERS.split(s) if p.strip()]
    return [s]


def classify_line_to_section(line: str) -> str | None:
    low = line.lower()
    loan = sum(k in low for k in LOAN_KEYS)
    dep = sum(k in low for k in DEP_KEYS)
    br = sum(k in low for k in BR_KEYS)
    if max(loan, dep, br) == 0:
        return None
    if br >= max(loan, dep):
        return "BRANCH LOCATIONS"
    if dep >= loan:
        return "DEPOSITS & SAVINGS"
    return "CREDITS & LOANS"


def is_field_label(line: str) -> bool:
    low = norm(line).lower().strip(":")
    if not low:
        return False
    if low in FIELD_LABEL_WORDS:
        return True
    if len(low.split()) <= 4 and any(low.endswith(w) for w in FIELD_LABEL_WORDS):
        return True
    return False


def is_value_line(line: str) -> bool:
    s = norm(line)
    low = s.lower()
    if not s:
        return False
    if ":" in s:
        return False
    if bool(RE_DIGIT.search(s)) and any(
        t in low for t in ("դրամ", "amd", "usd", "%", "ամիս", "տարի", "օր", "րոպե")
    ):
        return True
    return False


def join_label_value_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = norm(lines[i])
        nxt = norm(lines[i + 1]) if i + 1 < len(lines) else ""
        if is_field_label(cur) and is_value_line(nxt):
            out.append(f"{cur}: {nxt}")
            i += 2
            continue
        out.append(cur)
        i += 1
    return out


def parse_sections(lines: list[str]) -> dict[str, list[str]]:
    sections = {h: [] for h in SECTION_HEADERS}
    current: str | None = None
    for raw in lines:
        for piece in maybe_split_line(raw):
            s = norm(piece)
            if is_noise(s):
                continue
            if s.startswith("SUBSECTION:"):
                continue
            if s.startswith("PRODUCT:"):
                s = norm(s[len("PRODUCT:"):])
            elif s.startswith("- "):
                s = norm(s[2:])
            header_hit = None
            for h in SECTION_HEADERS:
                if s == h or s.startswith(h + " "):
                    header_hit = h
                    break
            if header_hit:
                current = header_hit
                tail = norm(s[len(header_hit):])
                if tail:
                    sections[current].append(tail)
                continue
            if current:
                sections[current].append(s)
            else:
                inferred = classify_line_to_section(s)
                if inferred:
                    sections[inferred].append(s)
    return sections


def looks_like_title(line: str, section: str) -> bool:
    s = norm(line)
    if not s or len(s) < 3 or len(s) > 120:
        return False
    low = s.lower()
    if s.startswith("-") or s.startswith("•"):
        return False
    if is_field_label(s):
        return False
    if s.lower() in GENERIC_TITLE_WORDS:
        return False
    if ":" in s and len(s) < 70:
        return False
    if section == "BRANCH LOCATIONS":
        if "հասցե" in low:
            return False
        if RE_HOURS.search(s):
            return False
        # Many branch names are short, uppercase, or end with office marker.
        return len(s.split()) <= 10 and not ("@" in s or "/" in s)
    # For products, prefer shorter semantic lines and type-keyword hits.
    if len(s.split()) > 14:
        return False
    has_type_kw = (
        any(k in low for k in LOAN_KEYS) if section == "CREDITS & LOANS"
        else any(k in low for k in DEP_KEYS)
    )
    has_digits = bool(RE_DIGIT.search(s))
    # Prefer semantic titles, avoid tiny single-word non-product labels.
    short_word_count = len(s.split()) <= 2
    if short_word_count and not has_type_kw:
        return False
    return has_type_kw or (not has_digits and len(s.split()) <= 10 and len(s) <= 90)


def looks_like_detail(line: str, section: str) -> bool:
    s = norm(line)
    low = s.lower()
    if not s:
        return False
    if s.lower() in GENERIC_TITLE_WORDS:
        return False
    if section == "BRANCH LOCATIONS":
        return (
            "հասցե" in low
            or "ք." in low
            or "ք․" in low
            or "փող" in low
            or "պող" in low
            or "հեռ" in low
            or "phone" in low
            or "tel" in low
            or "կառավարիչ" in low
            or "սպասարկում" in low
            or bool(RE_HOURS.search(s))
        )
    if ":" in s:
        return True
    if bool(RE_DIGIT.search(s)) and any(
        t in low for t in ("դրամ", "amd", "usd", "%", "ամիս", "տարի", "օր")
    ):
        return True
    return len(s) <= 140


def build_entries(lines: list[str], section: str) -> list[tuple[str, list[str]]]:
    prepared = [ln for ln in join_label_value_lines(lines) if norm(ln)]
    entries: list[tuple[str, list[str]]] = []
    title: str | None = None
    details: list[str] = []

    def flush():
        nonlocal title, details
        if title:
            clean = []
            seen = set()
            for d in details:
                if d not in seen:
                    seen.add(d)
                    clean.append(d)
            if clean:
                entries.append((title, clean[:24]))
        title = None
        details = []

    for raw in prepared:
        s = norm(raw)
        if not s:
            continue
        if looks_like_title(s, section):
            flush()
            title = s
            continue
        if title is None:
            # keep uncategorized useful facts under a generic product
            if looks_like_detail(s, section):
                title = "General Information"
                details = [s]
            continue
        if looks_like_detail(s, section):
            details.append(s)
    flush()
    return entries


def pick_subsection(title: str, section: str, details: list[str]) -> str:
    low = f"{title} {' '.join(details)}".lower()
    if section == "CREDITS & LOANS":
        for name, keys in LOAN_SUBSECTIONS.items():
            if not keys:
                continue
            if any(k in low for k in keys):
                return name
        return "OTHER LOANS"
    if section == "DEPOSITS & SAVINGS":
        for name, keys in DEPOSIT_SUBSECTIONS.items():
            if not keys:
                continue
            if any(k in low for k in keys):
                return name
        return "OTHER DEPOSITS"
    return "ALL BRANCHES"


def render_section(section: str, entries: list[tuple[str, list[str]]]) -> list[str]:
    grouped: OrderedDict[str, list[tuple[str, list[str]]]] = OrderedDict()
    for title, details in entries:
        subgroup = pick_subsection(title, section, details)
        grouped.setdefault(subgroup, []).append((title, details))

    out = [section]
    if not grouped:
        out.extend(["SUBSECTION: EMPTY", ""])
        return out

    for subgroup, rows in grouped.items():
        out.append(f"SUBSECTION: {subgroup}")
        for title, details in rows:
            out.append(f"PRODUCT: {title}")
            for d in details:
                out.append(f"- {d}")
            out.append("")
    return out


def structure_bank(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.read().splitlines()
    if raw_lines and raw_lines[0].startswith("BANK:"):
        bank_line = norm(raw_lines[0])
        body = raw_lines[1:]
    else:
        bank_name = os.path.splitext(os.path.basename(path))[0]
        bank_line = f"BANK: {bank_name}"
        body = raw_lines

    sections = parse_sections(body)

    out: list[str] = [bank_line, ""]
    for section in SECTION_HEADERS:
        entries = build_entries(sections[section], section)
        out.extend(render_section(section, entries))
        out.append("")

    # Normalize consecutive blank lines
    normalized: list[str] = []
    prev_blank = False
    for line in out:
        s = norm(line)
        if not s:
            if not prev_blank:
                normalized.append("")
            prev_blank = True
            continue
        normalized.append(s)
        prev_blank = False
    while normalized and not normalized[-1]:
        normalized.pop()
    return "\n".join(normalized) + "\n"


def run() -> None:
    files = [f for f in sorted(os.listdir(BANK_DATA_DIR)) if f.endswith(".txt")]
    print("Structuring datasets for RAG-friendly hierarchy")
    print("=" * 60)
    for fn in files:
        p = os.path.join(BANK_DATA_DIR, fn)
        structured = structure_bank(p)
        with open(p, "w", encoding="utf-8") as f:
            f.write(structured)
        print(f"  {fn}: done")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    run()

