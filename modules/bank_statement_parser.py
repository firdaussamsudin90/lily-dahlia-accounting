"""
Parses a Maybank bank statement PDF into a list of raw transaction rows plus
the printed opening/closing balance.

Two extraction strategies are tried, in order:

1. Table extraction (pdfplumber's line/ruling-based table detector). Most bank
   e-statements are real tables, so this is tried first. The header row is
   matched against a keyword map to find the Date/Description/Debit/Credit/
   Balance columns regardless of exact wording or column order.
2. Text-line fallback: scans raw text for date-prefixed lines and trailing
   money amounts, and infers debit vs. credit by checking whether adding or
   subtracting the transaction amount from the running balance reproduces the
   printed balance on that line. Without real table columns, counterparty and
   note are both embedded in one blob of text; TRANSACTION_PREFIX_RE strips
   the leading transaction-type phrase Maybank statements use (e.g.
   "TRANSFER FR A/C -", "INTER-BANK PAYMENT INTO A/C +"), and the counterparty
   name is taken as the text up to the next '*' marker, which Maybank always
   prints right after it. Page-footer legal boilerplate ("BAKI LEGAR...",
   "PROTECTED BY PIDM...") that sometimes gets merged into a transaction's
   wrapped note (or occasionally misparsed as its own bogus "transaction",
   when a date-like fragment in the footer text starts its own line) is
   stripped via FOOTER_RE; a "transaction" left with no note and no amounts
   afterwards is footer noise and is dropped. None of this is guaranteed to
   fit every Maybank statement layout — the review screen in the app lets the
   owner fix any row this gets wrong before saving.

Every parsed row is a dict: date (ISO), counterparty, note, debit, credit,
running_balance, source_line (for debugging/review).
"""
import re
from datetime import date as date_cls

import pdfplumber


# Matches either a properly comma-grouped number (1,234.56) or a plain digit
# run with no separators (1234.56) — NOT `\d{1,3}(?:,\d{3})*` alone, which
# silently truncates a comma-less 4+-digit amount to its last 3 digits before
# the decimal (e.g. "1865.98" -> "865.98") because \d{1,3} only ever consumes
# up to 3 digits and there's no comma group to absorb the rest. The lookbehind/
# lookahead stop a match from starting or ending mid-number in either case.
AMOUNT_RE = re.compile(r"(?<!\d)-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)")
DATE_LINE_RE = re.compile(r"^(\d{2})[/-](\d{2})(?:[/-](\d{2,4}))?\b")

HEADER_KEYWORDS = {
    "date": ["date", "tarikh"],
    "desc": ["description", "particular", "transaction", "detail", "butiran", "narration"],
    "debit": ["debit", "withdrawal", "keluar"],
    "credit": ["credit", "deposit", "masuk"],
    "balance": ["balance", "baki"],
}

OPENING_KEYWORDS = ["opening balance", "balance b/f", "beginning balance", "baki bawa ke hadapan"]
CLOSING_KEYWORDS = ["closing balance", "balance c/f", "ending balance", "baki bawa ke hadapan berikut"]

# Leading transaction-type phrase Maybank statements print before the
# counterparty name, observed across "TRANSFER FR/TO A/C", "PAYMENT FR/TO
# A/C", "INTER-BANK PAYMENT INTO/FROM A/C", "ELECTRONIC REMITTANCE - GIR -",
# "CMS - CR PYMT MARS +", "ESI PAYMENT DEBIT .NN-" style statement lines.
TRANSACTION_PREFIX_RE = re.compile(
    r"^(?:"
    r"TRANSFER (?:FR|TO) A/C\s*[-+]|"
    r"PAYMENT (?:FR|TO) A/C\s*[-+]|"
    r"INTER-BANK (?:PAYMENT (?:INTO|FROM)|GIRO PAYMENT)\s*A/C\s*[-+]|"
    r"ELECTRONIC REMITTANCE\s*-\s*GIR\s*-|"
    r"CMS\s*-\s*CR PYMT MARS\s*\+|"
    r"ESI PAYMENT DEBIT\s*\.?\d*\s*-"
    r")\s*",
    re.IGNORECASE,
)

# Recurring page-footer legal/disclaimer boilerplate that can get merged into
# a transaction's note (wrapped continuation lines) or, rarely, misparsed as
# its own bogus transaction when a date-like fragment inside it starts a line.
FOOTER_MARKERS = [
    "BAKI LEGAR", "PROTECTED BY PIDM", "Maybank Islamic Berhad", "TARIKH PENYATA",
    "Semua maklumat dan baki", "IBS KOTA KEMUNING", "Overdrawn balances",
]
FOOTER_RE = re.compile("|".join(re.escape(m) for m in FOOTER_MARKERS), re.IGNORECASE)


def _split_counterparty_from_blob(text):
    """Splits a Maybank statement line's combined description into
    (counterparty, note), or (None, cleaned_text) if no known transaction-type
    prefix is recognized (caller decides what to do with that case)."""
    if not text:
        return None, text

    m = FOOTER_RE.search(text)
    if m:
        text = text[: m.start()].strip()

    stripped = TRANSACTION_PREFIX_RE.sub("", text, count=1)
    if stripped == text:
        return None, text  # no recognized prefix; leave whole thing as note

    if "*" in stripped:
        counterparty, _, note = stripped.partition("*")
        return counterparty.strip() or None, note.strip() or None
    return None, stripped.strip() or None


def _to_float(text):
    return float(text.replace(",", ""))


def _find_balance_near_keywords(full_text_lower, keywords):
    for kw in keywords:
        idx = full_text_lower.find(kw)
        if idx == -1:
            continue
        window = full_text_lower[idx: idx + 120]
        m = AMOUNT_RE.search(window)
        if m:
            return _to_float(m.group())
    return None


def _split_counterparty_note(desc):
    """Best-effort split of a combined description blob. Used only when a real
    table gave us a single description column instead of separate ones."""
    parts = desc.split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return desc, None


def _classify_header(header_row):
    col_map = {}
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        cell_l = str(cell).strip().lower()
        for field, keywords in HEADER_KEYWORDS.items():
            if any(kw in cell_l for kw in keywords):
                col_map[field] = i
                break
    return col_map


def _parse_via_tables(pdf):
    # `pending` (the transaction currently accumulating wrapped continuation
    # lines) is intentionally shared across every table on every page, not
    # reset per table/page. A transaction's date+amount+balance row can be
    # the last row on a page while its wrapped description continues as the
    # first (dateless) row of the next page's table — resetting pending at
    # a table/page boundary would flush that transaction early with an empty
    # note and then silently drop the continuation, since it's a dateless
    # row arriving with no pending transaction left to attach it to.
    transactions = []
    pending = None
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if not table or len(table) < 2:
                continue
            col_map = _classify_header(table[0])
            if "date" not in col_map or "balance" not in col_map:
                # Doesn't look like a proper transaction table — most likely
                # this page didn't repeat the column header, and what pdfplumber
                # grabbed here is actually the tail end of a wrapped description
                # that started on the previous page. Rather than silently
                # dropping it, fold it into whatever transaction is still open.
                if pending:
                    for row in table:
                        extra = " ".join(str(c) for c in row if c).strip()
                        if extra and not FOOTER_RE.search(extra):
                            pending["note"] = (pending["note"] + " " + extra) if pending["note"] else extra
                continue

            for row in table[1:]:
                date_cell = row[col_map["date"]] if col_map["date"] < len(row) else None
                balance_cell = row[col_map["balance"]] if col_map["balance"] < len(row) else None

                has_date = bool(date_cell and DATE_LINE_RE.match(str(date_cell).strip()))

                if has_date:
                    if pending:
                        transactions.append(pending)
                    desc = ""
                    if "desc" in col_map and col_map["desc"] < len(row) and row[col_map["desc"]]:
                        desc = str(row[col_map["desc"]]).strip()
                    counterparty, note = _split_counterparty_note(desc) if desc else (None, None)

                    debit = credit = balance = None
                    if "debit" in col_map and col_map["debit"] < len(row) and row[col_map["debit"]]:
                        m = AMOUNT_RE.search(str(row[col_map["debit"]]))
                        debit = _to_float(m.group()) if m else None
                    if "credit" in col_map and col_map["credit"] < len(row) and row[col_map["credit"]]:
                        m = AMOUNT_RE.search(str(row[col_map["credit"]]))
                        credit = _to_float(m.group()) if m else None
                    if balance_cell:
                        m = AMOUNT_RE.search(str(balance_cell))
                        balance = _to_float(m.group()) if m else None

                    pending = {
                        "date_raw": str(date_cell).strip(),
                        "counterparty": counterparty,
                        "note": note,
                        "debit": debit,
                        "credit": credit,
                        "running_balance": balance,
                        "source_line": " | ".join(str(c) for c in row if c),
                    }
                elif pending:
                    # continuation row (wrapped description, no new date) — may
                    # belong to the same page/table as the transaction it
                    # continues, or (when a page break splits the description)
                    # the next page's table instead.
                    extra = ""
                    if "desc" in col_map and col_map["desc"] < len(row) and row[col_map["desc"]]:
                        extra = str(row[col_map["desc"]]).strip()
                    elif any(row):
                        extra = " ".join(str(c) for c in row if c).strip()
                    if extra:
                        pending["note"] = (pending["note"] + " " + extra) if pending["note"] else extra
    if pending:
        transactions.append(pending)
    return transactions


def _parse_via_text(pdf):
    full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    transactions = []
    pending = None
    for line in lines:
        m = DATE_LINE_RE.match(line)
        if m:
            if pending:
                transactions.append(pending)
            rest = line[m.end():].strip()
            amounts = AMOUNT_RE.findall(rest)
            desc = AMOUNT_RE.sub("", rest).strip()
            pending = {
                "date_raw": line[: m.end()].strip(),
                "counterparty": None,
                "note": desc if desc else None,
                "amounts": amounts,
                "source_line": line,
            }
        elif pending:
            amounts = AMOUNT_RE.findall(line)
            desc_part = AMOUNT_RE.sub("", line).strip()
            if desc_part:
                pending["note"] = (pending["note"] + " " + desc_part) if pending["note"] else desc_part
            pending["amounts"].extend(amounts)
            pending["source_line"] += " | " + line
    if pending:
        transactions.append(pending)

    # Split each transaction's combined description into counterparty/note, and
    # drop entries that turn out to be pure page-footer noise (no note content
    # left after stripping boilerplate, and no amounts were ever found either —
    # a real transaction always has at least an amount and a balance).
    split_transactions = []
    for t in transactions:
        counterparty, note = _split_counterparty_from_blob(t["note"])
        if not note and not t["amounts"]:
            continue
        t["counterparty"] = counterparty
        t["note"] = note
        split_transactions.append(t)
    transactions = split_transactions

    # Resolve debit/credit/balance from trailing amounts using the running-balance heuristic.
    resolved = []
    running_balance = None
    for t in transactions:
        amounts = t.pop("amounts", [])
        debit = credit = balance = None
        if len(amounts) >= 2:
            txn_amount = _to_float(amounts[-2])
            balance = _to_float(amounts[-1])
            if running_balance is not None:
                if abs((running_balance + txn_amount) - balance) < 0.01:
                    credit = txn_amount
                elif abs((running_balance - txn_amount) - balance) < 0.01:
                    debit = txn_amount
                else:
                    # can't tell from the balance chain — leave both blank for manual review
                    pass
            running_balance = balance
        elif len(amounts) == 1:
            balance = _to_float(amounts[0])
            running_balance = balance
        t["debit"] = debit
        t["credit"] = credit
        t["running_balance"] = balance
        resolved.append(t)
    return resolved


def _resolve_dates(transactions, year_hint, month_hint):
    out = []
    for t in transactions:
        m = DATE_LINE_RE.match(t["date_raw"])
        if not m:
            continue
        day, month, yr = m.groups()
        if yr:
            yr = yr if len(yr) == 4 else f"20{yr}"
        else:
            yr = str(year_hint)
        try:
            iso_date = date_cls(int(yr), int(month), int(day)).isoformat()
        except ValueError:
            continue
        t["date"] = iso_date
        out.append(t)
    return out


def parse_statement(filepath, year_hint, month_hint):
    """Returns dict: opening_balance, closing_balance, transactions (list), method used."""
    with pdfplumber.open(filepath) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        full_text_lower = full_text.lower()

        opening_balance = _find_balance_near_keywords(full_text_lower, OPENING_KEYWORDS)
        closing_balance = _find_balance_near_keywords(full_text_lower, CLOSING_KEYWORDS)

        transactions = _parse_via_tables(pdf)
        method = "table"
        if not transactions:
            transactions = _parse_via_text(pdf)
            method = "text"

    transactions = _resolve_dates(transactions, year_hint, month_hint)

    return {
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "transactions": transactions,
        "method": method,
    }
