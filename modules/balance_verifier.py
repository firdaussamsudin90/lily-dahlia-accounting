"""
Verifies the balance chain of a parsed bank statement: opening balance ->
each transaction's running balance -> closing balance, with zero tolerance
for discrepancy (per spec: "hard stop if mismatched").

verify() never raises; it returns a result dict the UI uses to either allow
committing the statement to the database or block with a clear diff of where
the chain breaks.
"""

TOLERANCE = 0.01  # cents rounding


def verify(opening_balance, closing_balance, transactions):
    errors = []

    if opening_balance is None:
        errors.append("Could not find an opening balance on the statement. Enter it manually to proceed.")
    if closing_balance is None:
        errors.append("Could not find a closing balance on the statement. Enter it manually to proceed.")
    if not transactions:
        errors.append("No transactions were parsed from this statement.")

    if errors:
        return {"ok": False, "errors": errors, "row_errors": []}

    running = opening_balance
    row_errors = []
    for i, t in enumerate(transactions):
        debit = t.get("debit") or 0
        credit = t.get("credit") or 0
        expected = running + credit - debit
        printed = t.get("running_balance")

        if printed is None:
            row_errors.append({
                "index": i, "date": t.get("date"), "note": t.get("note"),
                "issue": "missing printed balance", "expected_balance": round(expected, 2),
            })
            running = expected
            continue

        if abs(expected - printed) > TOLERANCE:
            row_errors.append({
                "index": i, "date": t.get("date"), "note": t.get("note"),
                "issue": "running balance mismatch",
                "expected_balance": round(expected, 2), "printed_balance": printed,
                "diff": round(printed - expected, 2),
            })
            # Resync to the printed balance so a single bad row doesn't cascade
            # false mismatches through the rest of the statement.
            running = printed
        else:
            running = printed

    if abs(running - closing_balance) > TOLERANCE:
        errors.append(
            f"Running balance after the last transaction (RM{running:,.2f}) does not match the "
            f"statement's printed closing balance (RM{closing_balance:,.2f})."
        )

    if row_errors:
        errors.append(f"{len(row_errors)} transaction(s) have a balance chain mismatch — see details below.")

    ok = not errors
    return {"ok": ok, "errors": errors, "row_errors": row_errors}
