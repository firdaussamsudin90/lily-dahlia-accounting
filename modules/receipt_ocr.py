"""
Best-effort OCR for receipt/invoice images, used only to suggest a candidate
amount when matching an uploaded document to a ledger transaction — never to
auto-commit anything. Degrades to "no text" if pytesseract or the tesseract
binary isn't available (e.g. local dev without the system package); the
caller always still has the WhatsApp caption text to fall back on.
"""
import io
import re

AMOUNT_RE = re.compile(r"(?:RM|MYR)?\s*\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2}", re.IGNORECASE)
TOTAL_LINE_RE = re.compile(r"total|jumlah|amount due", re.IGNORECASE)


def extract_text(image_bytes):
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
    except Exception:
        return None


def extract_amount(text):
    """Picks the amount most likely to be the receipt total: the largest
    money-shaped number on a line mentioning 'total'/'jumlah'/'amount due',
    else the largest money-shaped number anywhere in the text. Returns None
    if no money-shaped number is found."""
    if not text:
        return None

    total_candidates = []
    all_candidates = []
    for line in text.splitlines():
        found = [_to_float(m) for m in AMOUNT_RE.findall(line)]
        found = [f for f in found if f is not None]
        all_candidates.extend(found)
        if found and TOTAL_LINE_RE.search(line):
            total_candidates.extend(found)

    if total_candidates:
        return max(total_candidates)
    if all_candidates:
        return max(all_candidates)
    return None


def _to_float(match_str):
    cleaned = re.sub(r"[^\d.]", "", match_str)
    try:
        return float(cleaned)
    except ValueError:
        return None
