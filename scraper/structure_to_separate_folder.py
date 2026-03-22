"""
Create strict structured datasets in a separate folder.

Raw data is read from bank_data/ and never modified.
Structured files are written to bank_data_structured/.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.getenv("STRUCTURE_INPUT_DIR", str(BASE_DIR / "bank_data")))
OUT_DIR = Path(os.getenv("STRUCTURE_OUTPUT_DIR", str(BASE_DIR / "bank_data_structured")))

RAW_SECTIONS = ("CREDITS & LOANS", "DEPOSITS & SAVINGS", "BRANCH LOCATIONS")

LOAN_TITLE_KWS = (
    "հիփոթեք",
    "սպառողական",
    "օվերդրաֆտ",
    "վարկային գիծ",
    "ավտովարկ",
    "ավտոմեքենայի ձեռքբերման վարկ",
    "վերաֆինանս",
    "բիզնես վարկ",
    "ուսանողական",
    "լիզինգ",
    "ագրո",
    "առևտրային վարկ",
    "commercial loan",
    "mortgage",
    "consumer",
    "overdraft",
    "credit line",
    "car loan",
)

DEPOSIT_TITLE_KWS = (
    "ավանդ",
    "դեպոզիտ",
    "խնայողական",
    "խնայող",
    "կուտակային",
    "մանկական",
    "դասական",
    "շահավետ",
    "savings",
    "deposit",
)

BAD_TITLE_PARTS = (
    "տեղեկատվական",
    "հաշվիչ",
    "պատմություն",
    "հայտ",
    "իրավունք",
    "տույժ",
    "տուգանք",
    "պայմանագր",
    "նախահաշիվ",
    "կարգ",
    "ուշադրություն",
    "հարց",
    "faq",
    "pdf",
    "ուղեցույց",
    "ցանկ",
    "նկարագր",
    "լրացուցիչ",
    "ծանուցում",
    "վկայ",
    "անձնական տվյալ",
    "պայմաններ",
    "ենթակա",
    "ամսական",
    "հարց ու պատասխան",
    "հաշվարկ",
    "բանկի կողմից",
)

NOISE_EXACT = {
    "pdf",
    "իմանալ ավելին",
    "տեսնել ավելին",
    "ավելին",
    "դիմել հիմա",
    "դիմիր օնլայն",
    "հայ",
    "en",
    "ru",
    "ir",
}

RE_SPACE = re.compile(r"\s+")
RE_DIGIT = re.compile(r"\d")
RE_TIME = re.compile(r"\d{2}[:։]\d{2}")
RE_INLINE_BRANCH = re.compile(r"^(?P<name>[^\d:]{2,60}?)(?P<rest>Հասցե.+)$")
RE_MULTI_DASH = re.compile(r"-{2,}")

LABEL_RULES = (
    ("Տարեկան անվանական տոկոսադրույք", ("տարեկան անվանական տոկոս",)),
    ("Տարեկան փաստացի տոկոսադրույք", ("տարեկան փաստացի տոկոս",)),
    ("Անվանական տոկոսադրույք", ("անվանական տոկոս",)),
    ("Փաստացի տոկոսադրույք", ("փաստացի տոկոս",)),
    ("Տոկոսադրույք", ("տոկոսադրույք",)),
    ("Տոկոս", ("տոկոս",)),
    ("Առավելագույն գումար", ("առավելագույն գումար",)),
    ("Նվազագույն գումար", ("նվազագույն գումար",)),
    ("Վարկի գումար", ("վարկի գումար",)),
    ("Գումար", ("գումար",)),
    ("Մինիմալ կանխավճար", ("մինիմալ կանխավճար",)),
    ("Նվազագույն կանխավճար", ("նվազագույն կանխավճար",)),
    ("Կանխավճար", ("կանխավճար",)),
    ("Առավելագույն ժամկետ", ("առավելագույն ժամկետ",)),
    ("Վարկի ժամկետ", ("վարկի ժամկետ",)),
    ("Ժամկետ", ("ժամկետ",)),
    ("Արժույթ", ("արժույթ",)),
    ("Վարկի արժույթ", ("վարկի արժույթ",)),
    ("Տրամադրում", ("տրամադրում",)),
    ("Սուբսիդավորում", ("սուբսիդավորում",)),
    ("Վաղաժամկետ մարման տույժ", ("վաղաժամկետ մարման տույժ", "վաղաժամկետ մարման դեպքում")),
)

VALUE_STOP_MARKERS = (
    "դիմել",
    "առավելություններ",
    "վարկեր",
    "ավանդներ",
    "ներբեռնել",
    "տեղեկատվական",
    "պայմաններ",
    "հաշվիչ",
)

LOAN_TITLE_TOKENS = {
    "վարկ",
    "վարկեր",
    "հիփոթեքային",
    "օվերդրաֆտ",
    "վարկային",
    "ավտովարկ",
    "ավտովարկեր",
    "լիզինգ",
    "վերաֆինանսավորում",
}

DEPOSIT_TITLE_TOKENS = {
    "ավանդ",
    "ավանդներ",
    "դեպոզիտ",
    "խնայողական",
    "կուտակային",
    "շահավետ",
}

TITLE_WHITELIST: dict[str, dict[str, tuple[str, ...]]] = {
    "ameriabank": {
        "loan": (
            "Սպառողական վարկ",
            "Օվերդրաֆտ",
            "Վարկային գիծ",
            "Գրավով ապահովված սպառողական վարկ",
            "Հիփոթեքային վարկեր Սփյուռքի համար",
            "Հիփոթեքային վարկ առաջնային շուկայից",
            "Հիփոթեքային վարկ երկրորդային շուկայից",
            "Օնլայն հիփոթեք",
            "Վերանորոգման վարկ",
            "Ավտովարկ՝ առանց բանկ այցելելու",
            "Ավտովարկ առաջնային շուկայից",
            "Ավտովարկ երկրորդային շուկայից",
        ),
        "deposit": ("Ժամկետային ավանդ", "Անժամկետ", "խնայողական"),
    },
    "amio": {
        "loan": (
            "Սպառողական վարկեր",
            "Հիփոթեքային վարկեր",
            "Ավտովարկեր",
            "Վերաֆինանսավորում",
            "Օնլայն վարկ",
            "Գրավով վարկի վերաֆինանսավորում",
            "Հիփոթեքային վարկի առաջնային շուկա",
            "Ավտովարկ՝ առաջնային շուկա",
            "Անգրավ վարկի վերաֆինանսավորում",
        ),
        "deposit": ("Ֆիզիկական անձանց ժամկետային ավանդներ", "Ավանդ «Շահավետ"),
    },
    "fast bank": {
        "loan": (
            "ԱԶԳԱՅԻՆ ՀԻՓՈԹԵՔԱՅԻՆ ՎԱՐԿԵՐ",
            "ՎԱՐԿԵՐ ԵՐԻՏԱՍԱՐԴ ԸՆՏԱՆԻՔՆԵՐԻՆ",
            "ՀԻՓՈԹԵՔԱՅԻՆ ՎԱՐԿԵՐ",
            "ՀԻՓՈԹԵՔԱՅԻՆ ՎԱՐԿԵՐ ԱՐՑԱԽԻՑ ՏԵՂԱՀԱՆՎԱԾ ԸՆՏԱՆԻՔՆԵՐԻ ՀԱՄԱՐ",
            "ԱՌԵՎՏՐԱՅԻՆ ՏԱՐԱԾՔԻ ՀԻՓՈԹԵՔԱՅԻՆ ՎԱՐԿԵՐ",
            "ԱՌԱՋՆԱՅԻՆ ՇՈՒԿԱՅԻՑ ԱՎՏՈՄԵՔԵՆԱՅԻ ՁԵՌՔԲԵՐՄԱՆ ՎԱՐԿ",
            "ԱՆԳՐԱՎ ՍՊԱՌՈՂԱԿԱՆ ՎԱՐԿ",
            "Քարտային վարկային գիծ",
        ),
        "deposit": ("Համալրվող ավանդ", "Ժամկետային ավանդ"),
    },
}


def norm(s: str) -> str:
    return RE_SPACE.sub(" ", s.replace("\u00a0", " ")).strip()


def is_noise(s: str) -> bool:
    low = s.lower()
    if not low:
        return True
    if low in NOISE_EXACT:
        return True
    if low.startswith("http://") or low.startswith("https://") or low.startswith("www."):
        return True
    return False


def parse_raw_sections(lines: list[str]) -> dict[str, list[str]]:
    out = {k: [] for k in RAW_SECTIONS}
    current: str | None = None
    for raw in lines:
        s = norm(raw)
        if not s:
            continue
        if s in RAW_SECTIONS:
            current = s
            continue
        if current:
            out[current].append(s)
    return out


def has_any(text: str, keywords: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


def has_token(text: str, tokens: set[str]) -> bool:
    parts = {p.strip("«»\"'`()[]{}.,:;").lower() for p in text.split()}
    return any(t in parts for t in tokens)


def title_ok(s: str, section_kind: str) -> bool:
    s = norm(s)
    if len(s) < 3 or len(s) > 85:
        return False
    if ":" in s or "/" in s:
        return False
    if s.startswith("-") or s.startswith("•"):
        return False
    if any(ch in s for ch in (";", "`", "“", "”")):
        return False
    if RE_DIGIT.search(s):
        return False
    if len(s.split()) > 9:
        return False
    low = s.lower()
    if any(b in low for b in BAD_TITLE_PARTS):
        return False
    if section_kind == "loan":
        return has_token(s, LOAN_TITLE_TOKENS) or has_any(s, LOAN_TITLE_KWS)
    return has_token(s, DEPOSIT_TITLE_TOKENS) or has_any(s, DEPOSIT_TITLE_KWS)


def canonical_label(s: str) -> str | None:
    t = norm(s).strip("- ").strip(":")
    low = t.lower()
    for canonical, variants in LABEL_RULES:
        if low == canonical.lower():
            return canonical
        for v in variants:
            if low == v:
                return canonical
            if low.startswith(v + " "):
                return canonical
            if v in low and len(low) <= 45:
                return canonical
    return None


def clean_value(v: str) -> str:
    s = norm(v).strip("- ").strip()
    if not s:
        return ""
    low = s.lower()
    for marker in VALUE_STOP_MARKERS:
        idx = low.find(" " + marker + " ")
        if idx > 0:
            s = s[:idx].strip()
            low = s.lower()
    # Cut obvious next-card bleed, e.g. "... մինչև 5 տարի Ավտովարկեր Տոկոս ..."
    bleed = re.search(r"\s(?=(Հիփոթեք|Ավտովարկ|Օնլայն վարկ|Սպառողական վարկ|Վերաֆինանս))", s, flags=re.I)
    if bleed:
        s = s[: bleed.start()].strip()
    return s


def looks_like_value(v: str) -> bool:
    low = v.lower()
    if len(v) > 95:
        return False
    if any(b in low for b in ("հաճախորդ", "պայմանագր", "տեղեկատվ", "ծանուց", "պատմություն")):
        return False
    if RE_DIGIT.search(v):
        return True
    return any(t in low for t in ("դրամ", "amd", "usd", "%", "ամիս", "տարի", "օր", "չի կիրառվում", "սկսած"))


def compact_numeric_value(v: str) -> bool:
    s = clean_value(v)
    if not s:
        return False
    if len(s) > 50:
        return False
    if len(s.split()) > 9:
        return False
    if re.fullmatch(r"\d+(\.\d+)+\.?", s):
        return False
    low = s.lower()
    if any(x in low for x in ("եթե", "որի", "հաճախորդ", "պայմանագր", "ծրագր", "կառուցապատող")):
        return False
    if re.fullmatch(r"[\d\s,.\-]+", s):
        digits = re.sub(r"\D", "", s)
        if not digits:
            return False
        if int(digits) < 1000:
            return False
    return RE_DIGIT.search(s) is not None or "չի կիրառվում" in low


def extract_field_pair(cur: str, nxt: str) -> tuple[str, str] | None:
    s = norm(cur)
    n = norm(nxt)
    if not s:
        return None

    # Label: Value
    if ":" in s:
        left, right = [x.strip() for x in s.split(":", 1)]
        lbl = canonical_label(left)
        clean_right = clean_value(right)
        if lbl and clean_right and looks_like_value(clean_right):
            return (lbl, clean_right)

    # Label value in same line
    lbl = canonical_label(s)
    if lbl and s.lower().startswith(lbl.lower()):
        rest = clean_value(s[len(lbl):])
        if rest and looks_like_value(rest):
            return (lbl, rest)

    # Label line + value next line
    if lbl and n and looks_like_value(n):
        return (lbl, clean_value(n))

    return None


def has_nearby_fields(lines: list[str], i: int) -> bool:
    window = lines[i + 1 : i + 12]
    count = 0
    for s in window:
        if canonical_label(s):
            count += 1
    return count >= 2


def compact_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    prev = ""
    for raw in lines:
        s = norm(raw)
        if not s or is_noise(s):
            continue
        if RE_MULTI_DASH.fullmatch(s):
            continue
        if s == prev:
            continue
        out.append(s)
        prev = s
    return out


def structure_financial(lines: list[str], section_kind: str) -> list[dict]:
    lines = compact_lines(lines)
    title_idx = [i for i, s in enumerate(lines) if title_ok(s, section_kind) and has_nearby_fields(lines, i)]
    if not title_idx:
        return []

    rows: list[dict] = []
    for p, start in enumerate(title_idx):
        end = title_idx[p + 1] if p + 1 < len(title_idx) else min(len(lines), start + 60)
        title = lines[start]
        desc: list[str] = []
        fields: list[tuple[str, str]] = []
        i = start + 1
        while i < end:
            s = lines[i]
            nxt = lines[i + 1] if i + 1 < end else ""
            pair = extract_field_pair(s, nxt)
            if pair:
                fields.append(pair)
                if canonical_label(s) and looks_like_value(clean_value(nxt)) and ":" not in s:
                    i += 2
                    continue
                i += 1
                continue
            if len(desc) < 1 and len(s) <= 110 and not RE_DIGIT.search(s) and not canonical_label(s):
                desc.append(s)
            i += 1

        seen = set()
        uniq: list[tuple[str, str]] = []
        key_types = set()
        for k, v in fields:
            cv = clean_value(v)
            if not cv or not looks_like_value(cv):
                continue
            if k in {
                "Տոկոս",
                "Տոկոսադրույք",
                "Անվանական տոկոսադրույք",
                "Տարեկան անվանական տոկոսադրույք",
                "Տարեկան փաստացի տոկոսադրույք",
                "Փաստացի տոկոսադրույք",
                "Գումար",
                "Վարկի գումար",
                "Առավելագույն գումար",
                "Նվազագույն գումար",
                "Ժամկետ",
                "Վարկի ժամկետ",
                "Առավելագույն ժամկետ",
                "Կանխավճար",
                "Նվազագույն կանխավճար",
                "Մինիմալ կանխավճար",
            } and not compact_numeric_value(cv):
                continue
            sig = (k.lower(), cv.lower())
            if sig in seen:
                continue
            seen.add(sig)
            uniq.append((k, cv))
            key_types.add(k)

        quality = len(uniq)
        if quality < 3:
            continue
        if len(key_types) < 2:
            continue
        rows.append({"title": title, "desc": desc, "fields": uniq})

    # Merge same titles and keep cleaner set.
    merged: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        key = row["title"].lower()
        if key not in merged:
            merged[key] = {"title": row["title"], "desc": row["desc"][:], "fields": []}
            order.append(key)
        merged[key]["fields"].extend(row["fields"])
        if not merged[key]["desc"] and row["desc"]:
            merged[key]["desc"] = row["desc"][:]

    cleaned: list[dict] = []
    for key in order:
        row = merged[key]
        seen = set()
        uniq = []
        for k, v in row["fields"]:
            sig = (k.lower(), v.lower())
            if sig in seen:
                continue
            seen.add(sig)
            uniq.append((k, v))
        if len(uniq) >= 3:
            cleaned.append({"title": row["title"], "desc": row["desc"], "fields": uniq[:16]})
    return cleaned


def fallback_financial(lines: list[str], title: str) -> list[dict]:
    lines = compact_lines(lines)
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        s = norm(lines[i])
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        p = extract_field_pair(s, nxt)
        if p:
            pairs.append(p)
            if canonical_label(s) and looks_like_value(clean_value(nxt)) and ":" not in s:
                i += 2
                continue
        i += 1
    seen = set()
    uniq = []
    for k, v in pairs:
        sig = (k.lower(), v.lower())
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append((k, v))
    if len(uniq) < 2:
        return []
    return [{"title": title, "desc": [], "fields": uniq[:30]}]


def filter_rows_by_bank(bank: str, section_kind: str, rows: list[dict]) -> list[dict]:
    b = bank.lower()
    cfg: tuple[str, ...] | None = None
    for k, sections in TITLE_WHITELIST.items():
        if k in b:
            cfg = sections.get(section_kind)
            break
    if not cfg:
        return [r for r in rows if len(r["title"].split()) >= 2]

    filtered = [r for r in rows if any(r["title"].lower().startswith(p.lower()) for p in cfg)]
    if filtered:
        return filtered
    return [r for r in rows if len(r["title"].split()) >= 2]


def get_bank_whitelist(bank: str, section_kind: str) -> tuple[str, ...] | None:
    b = bank.lower()
    for k, sections in TITLE_WHITELIST.items():
        if k in b:
            return sections.get(section_kind)
    return None


def extract_known_rows(lines: list[str], titles: tuple[str, ...]) -> list[dict]:
    seq = compact_lines(lines)
    found: list[tuple[str, int]] = []
    used = set()
    for title in titles:
        t_low = title.lower()
        idx = -1
        for i, s in enumerate(seq):
            if i in used:
                continue
            if s.lower().startswith(t_low):
                idx = i
                break
        if idx >= 0:
            found.append((seq[idx], idx))
            used.add(idx)
    found.sort(key=lambda x: x[1])
    if not found:
        return []

    rows: list[dict] = []
    for p, (title_line, start) in enumerate(found):
        next_start = found[p + 1][1] if p + 1 < len(found) else min(len(seq), start + 80)
        end = min(next_start, start + 80)
        desc: list[str] = []
        fields: list[tuple[str, str]] = []
        i = start + 1
        while i < end:
            s = seq[i]
            nxt = seq[i + 1] if i + 1 < end else ""
            pair = extract_field_pair(s, nxt)
            if pair:
                k, v = pair
                if k in {
                    "Տոկոս",
                    "Տոկոսադրույք",
                    "Անվանական տոկոսադրույք",
                    "Տարեկան անվանական տոկոսադրույք",
                    "Տարեկան փաստացի տոկոսադրույք",
                    "Փաստացի տոկոսադրույք",
                    "Գումար",
                    "Վարկի գումար",
                    "Առավելագույն գումար",
                    "Նվազագույն գումար",
                    "Ժամկետ",
                    "Վարկի ժամկետ",
                    "Առավելագույն ժամկետ",
                    "Կանխավճար",
                    "Նվազագույն կանխավճար",
                    "Մինիմալ կանխավճար",
                } and not compact_numeric_value(v):
                    i += 1
                    continue
                fields.append((k, clean_value(v)))
            elif len(desc) < 1 and len(s) <= 100 and not RE_DIGIT.search(s) and not canonical_label(s):
                desc.append(s)
            i += 1

        seen = set()
        uniq: list[tuple[str, str]] = []
        for k, v in fields:
            sig = (k.lower(), v.lower())
            if sig in seen:
                continue
            seen.add(sig)
            uniq.append((k, v))
        if len(uniq) >= 2:
            rows.append({"title": title_line, "desc": desc, "fields": uniq[:12]})
    return rows


def branch_detail_kind(line: str) -> tuple[str, str] | None:
    s = norm(line)
    low = s.lower()
    if not s:
        return None
    if low.startswith("հասցե"):
        return ("Հասցե", clean_value(s.replace("Հասցե", "", 1)))
    if "հեռ" in low or "+374" in low:
        return ("Հեռախոս", s)
    if RE_TIME.search(s) or "սպասարկում" in low or "ժամ" in low:
        return ("Աշխատանքային ժամ", s)
    if "կառավարիչ" in low:
        return ("Կառավարիչ", clean_value(s.replace("Կառավարիչ", "", 1)))
    if "ք." in low or "ք․" in low or "փող" in low or "պող" in low:
        return ("Հասցե", s)
    return None


def branch_title_ok(s: str) -> bool:
    s = norm(s)
    if len(s) < 2 or len(s) > 70:
        return False
    if ":" in s or RE_DIGIT.search(s) or RE_TIME.search(s):
        return False
    low = s.lower()
    if any(x in low for x in ("հասցե", "հեռ", "կառավարիչ", "սպասարկում", "բանկոմատ", "քարտեզ")):
        return False
    if "մ/ճ" in low or "գրասենյակ" in low:
        return True
    if len(s.split()) <= 4 and s == s.upper():
        return True
    return len(s.split()) <= 5


def structure_branches(lines: list[str]) -> list[dict]:
    lines = compact_lines(lines)
    rows: list[dict] = []
    current: dict | None = None
    generic_idx = 1

    def flush():
        nonlocal current
        if current and current["details"]:
            # dedupe
            seen = set()
            uniq = []
            for k, v in current["details"]:
                sig = (k.lower(), norm(v).lower())
                if sig in seen:
                    continue
                seen.add(sig)
                uniq.append((k, v))
            if uniq:
                current["details"] = uniq
                rows.append(current)
        current = None

    for s in lines:
        s = norm(s)
        if is_noise(s) or s == "---":
            continue

        m = RE_INLINE_BRANCH.match(s)
        if m:
            flush()
            name = norm(m.group("name"))
            rest = norm(m.group("rest"))
            current = {"title": name, "details": []}
            detail = branch_detail_kind(rest)
            if detail:
                current["details"].append(detail)
            continue

        if s.startswith("«") and "մ/ճ" in s.lower():
            flush()
            name = norm(s.split("մ/ճ", 1)[0] + "մ/ճ")
            rest = norm(s.split("մ/ճ", 1)[1]) if "մ/ճ" in s else ""
            current = {"title": name, "details": []}
            if rest:
                current["details"].append(("Հասցե", rest))
            continue

        if ("մ/ճ" in s.lower() or "գրասենյակ" in s.lower()) and "ք." in s:
            flush()
            parts = s.split("ք.", 1)
            name = norm(parts[0]) if parts else s
            addr = "ք." + parts[1] if len(parts) > 1 else s
            current = {"title": name, "details": [("Հասցե", norm(addr))]}
            continue

        if branch_title_ok(s):
            flush()
            current = {"title": s, "details": []}
            continue

        if current is None and ("ք." in s or "ք․" in s or "ՀՀ," in s):
            current = {"title": f"Մասնաճյուղ {generic_idx}", "details": []}
            generic_idx += 1

        if current is None:
            continue
        d = branch_detail_kind(s)
        if d:
            current["details"].append(d)

    flush()
    pruned: list[dict] = []
    for r in rows:
        addr = [x for x in r["details"] if x[0] == "Հասցե"][:1]
        phone = [x for x in r["details"] if x[0] == "Հեռախոս"][:1]
        hours = [x for x in r["details"] if x[0] == "Աշխատանքային ժամ"][:1]
        details = addr + phone + hours
        if details:
            pruned.append({"title": r["title"], "details": details})
    return pruned


def fallback_branches(lines: list[str]) -> list[dict]:
    lines = compact_lines(lines)
    details: list[tuple[str, str]] = []
    for s in lines:
        d = branch_detail_kind(s)
        if d:
            details.append(d)
    seen = set()
    uniq = []
    for k, v in details:
        sig = (k.lower(), norm(v).lower())
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append((k, v))
    if not uniq:
        return []
    return [{"title": "Մասնաճյուղեր", "details": uniq[:120]}]


def render_structured(bank: str, parsed: dict[str, list[str]]) -> str:
    out: list[str] = [f"BANK: {bank}", ""]

    out.append("SECTION: LOANS & CREDITS")
    loan_wl = get_bank_whitelist(bank, "loan")
    loan_rows = extract_known_rows(parsed["CREDITS & LOANS"], loan_wl) if loan_wl else []
    if not loan_rows:
        loan_rows = structure_financial(parsed["CREDITS & LOANS"], "loan")
        loan_rows = filter_rows_by_bank(bank, "loan", loan_rows)
    if not loan_rows:
        loan_rows = fallback_financial(parsed["CREDITS & LOANS"], "Ընդհանուր վարկային պայմաններ")
    for row in loan_rows:
        out.append(f"SUBSECTION: {row['title']}")
        for d in row["desc"]:
            out.append(d)
        for k, v in row["fields"]:
            out.append(f"-{k} - {v}")
        out.append("")
    if not loan_rows:
        out.append("SUBSECTION: Չի հայտնաբերվել")
        out.append("")
    out.append("")

    out.append("SECTION: DEPOSITS")
    dep_wl = get_bank_whitelist(bank, "deposit")
    dep_rows = extract_known_rows(parsed["DEPOSITS & SAVINGS"], dep_wl) if dep_wl else []
    if not dep_rows:
        dep_rows = structure_financial(parsed["DEPOSITS & SAVINGS"], "deposit")
        dep_rows = filter_rows_by_bank(bank, "deposit", dep_rows)
    if not dep_rows:
        dep_rows = fallback_financial(parsed["DEPOSITS & SAVINGS"], "Ընդհանուր ավանդային պայմաններ")
    for row in dep_rows:
        out.append(f"SUBSECTION: {row['title']}")
        for d in row["desc"]:
            out.append(d)
        for k, v in row["fields"]:
            out.append(f"-{k} - {v}")
        out.append("")
    if not dep_rows:
        out.append("SUBSECTION: Չի հայտնաբերվել")
        out.append("")
    out.append("")

    out.append("SECTION: BRANCHES")
    br_rows = structure_branches(parsed["BRANCH LOCATIONS"])
    if not br_rows:
        br_rows = fallback_branches(parsed["BRANCH LOCATIONS"])
    for row in br_rows:
        out.append(f"SUBSECTION: {row['title']}")
        for k, v in row["details"]:
            out.append(f"-{k} - {v}")
        out.append("")
    if not br_rows:
        out.append("SUBSECTION: Չի հայտնաբերվել")
        out.append("")

    # normalize blank lines
    final: list[str] = []
    prev_blank = False
    for line in out:
        s = norm(line)
        if not s:
            if not prev_blank:
                final.append("")
            prev_blank = True
            continue
        final.append(s)
        prev_blank = False
    while final and final[-1] == "":
        final.pop()
    return "\n".join(final) + "\n"


def process_file(path: Path) -> str:
    raw_text = path.read_text(encoding="utf-8")
    raw_lines = raw_text.splitlines()
    bank_name = path.stem
    if raw_lines and raw_lines[0].startswith("BANK:"):
        bank_name = norm(raw_lines[0].split(":", 1)[1])
        base_lines = raw_lines[1:]
    else:
        base_lines = raw_lines
    parsed = parse_raw_sections(base_lines)
    return render_structured(bank_name, parsed)


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("*.txt"))
    print("Structuring datasets into separate folder (strict mode)")
    print("=" * 60)
    print(f"Input : {RAW_DIR}")
    print(f"Output: {OUT_DIR}")
    for p in files:
        out_text = process_file(p)
        out_path = OUT_DIR / p.name
        out_path.write_text(out_text, encoding="utf-8")
        print(f"  {p.name} -> {out_path.name}")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    run()
