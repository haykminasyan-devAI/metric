import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DATA_DIR = os.path.join(BASE_DIR, "bank_data")

SECTION_HEADERS = ["CREDITS & LOANS", "DEPOSITS & SAVINGS", "BRANCH LOCATIONS"]
MAX_CHARS_PER_SECTION = 15000


def _extract_sections(text: str) -> str:
    """Extract each section (loans/deposits/branches) and cap each at MAX_CHARS_PER_SECTION."""
    lines = text.splitlines(keepends=True)
    sections = {}
    current_section = None
    buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped in SECTION_HEADERS:
            if current_section and buffer:
                sections[current_section] = "".join(buffer)
            current_section = stripped
            buffer = [line]
        elif current_section:
            buffer.append(line)

    if current_section and buffer:
        sections[current_section] = "".join(buffer)

    parts = []
    for header in SECTION_HEADERS:
        if header in sections:
            chunk = sections[header]
            if len(chunk) > MAX_CHARS_PER_SECTION:
                chunk = chunk[:MAX_CHARS_PER_SECTION] + "\n[... truncated ...]"
            parts.append(chunk)

    return "\n\n".join(parts) if parts else text[:15000]


def load_bank_data() -> str:
    if not os.path.exists(BANK_DATA_DIR):
        raise FileNotFoundError(
            f"bank_data/ folder not found at {BANK_DATA_DIR}."
            "Run the scraper first: python scraper/scrape_banks.py"
        )

    all_text = []

    for filename in sorted(os.listdir(BANK_DATA_DIR)):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(BANK_DATA_DIR, filename)
        with open(filepath, "r",encoding = "utf-8") as f:
            content = f.read().strip()

        if content:
            content = _extract_sections(content)
            all_text.append(content)

    if not all_text:
        raise ValueError(
            "No bank data files found in bank_data/ ."
            "Run the scraper first: python scraper/scrape_banks.py"
        )

    separator = "\n\n" + "═" * 60 + "\n\n"
    return separator.join(all_text)