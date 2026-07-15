"""
Suggests a ledger transaction to match an uploaded/imported document to, by
date proximity and (if known) amount. Never auto-commits a match — callers
always show the suggestion and its confidence to a human before saving,
per the Upload Documents review step.
"""
from datetime import date, datetime, timedelta

AMOUNT_TOLERANCE = 0.01
DATE_WINDOW_DAYS = 3


def _parse_date(d):
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


def find_candidates(conn, target_date, amount=None, window_days=DATE_WINDOW_DAYS):
    """Transactions within `window_days` of target_date. Amount-matching ones
    (if amount is given) sort first, then by closeness of date."""
    target = _parse_date(target_date)
    low = (target - timedelta(days=window_days)).isoformat()
    high = (target + timedelta(days=window_days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE date BETWEEN %s AND %s ORDER BY date ASC",
        (low, high),
    ).fetchall()
    rows = [dict(r) for r in rows]

    def sort_key(r):
        day_diff = abs((_parse_date(r["date"]) - target).days)
        r_amount = r["debit"] if r["debit"] else r["credit"]
        amount_match = (
            amount is not None and r_amount is not None
            and abs(float(r_amount) - amount) <= AMOUNT_TOLERANCE
        )
        return (0 if amount_match else 1, day_diff)

    rows.sort(key=sort_key)
    return rows


def best_match(conn, target_date, amount=None, window_days=DATE_WINDOW_DAYS):
    """Returns (transaction_dict_or_None, confidence, reason).
    confidence: None (exact date+amount — high confidence), 'yellow'
    (plausible, needs a human look), or 'red' (no confident candidate)."""
    candidates = find_candidates(conn, target_date, amount, window_days)
    if not candidates:
        return None, "red", "No transactions within 3 days of this receipt's date."

    top = candidates[0]
    target = _parse_date(target_date)
    day_diff = abs((_parse_date(top["date"]) - target).days)
    top_amount = top["debit"] if top["debit"] else top["credit"]
    amount_match = (
        amount is not None and top_amount is not None
        and abs(float(top_amount) - amount) <= AMOUNT_TOLERANCE
    )

    if amount_match and day_diff == 0:
        return top, None, "Exact date and amount match."
    if amount_match:
        return top, "yellow", f"Amount matches a transaction {day_diff} day(s) away — check the date."
    if day_diff == 0:
        return top, "yellow", "Same-day transaction found, but no amount could be confirmed."
    return None, "red", "No confident date+amount match — review manually."
