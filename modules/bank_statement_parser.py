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
   printed balance on that line. In this path the counterparty/note split is
   not attempted (the whole description is put in `note`, counterparty left
   blank) since without column positions that split can't be done reliably —
   the review screen in the app lets the owner fix these by hand.

Every parsed row is a dict: date (ISO), counterparty, note, debit, credit,
running_balance, source_line (for debugging/review).
"""
import re
from datetime import date as date_cls

import pdfplumber

AMOUNT_RE = re.compile(r"-?\d{1,3}(?:,\d{3})*\.\d{2}")
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
    transactions = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if not table or len(table) < 2:
                continue
            col_map = _classify_header(table[0])
            if "date" not in col_map or "balance" not in col_map:
                continue  # not a transaction table

            pending = None
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
                    # continuation row (wrapped description, no new date)
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
