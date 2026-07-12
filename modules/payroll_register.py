"""
Monthly Payroll Register: every person paid in a month (staff wages, live
host wages, owner drawings) as line items. No statutory deduction columns
(EPF/SOCSO/EIS) — all staff are informal/casual per the owner.

Regenerating a month's register is idempotent: existing rows for that month
are replaced.
"""
import json
import re

from modules.db import get_connection

FIXED_PERSON_BY_SUBCATEGORY = {
    "Owner Salary - Diyanna": "Diyanna",
    "Salary - Firdaus": "Firdaus",
    "Salary - Nur Farahiyah": "Nur Farahiyah",
    "Part-Timer Wages - Kak Yana": "Kak Yana",
}

ROLE_BY_SUBCATEGORY = {
    "Owner Salary - Diyanna": "owner",
    "Salary - Firdaus": "staff",
    "Salary - Nur Farahiyah": "staff",
    "Part-Timer Wages - Kak Yana": "staff",
    "Part-Timer Wages - Live Host": "live_host",
    "Claims/Reimbursement": "staff",
}

# Subcategories under Staff Cost that are vendor expenses, not person payroll.
NON_PAYROLL_SUBCATEGORIES = {"Staff Meals"}

PAYROLL_CATEGORIES = ("Staff Cost", "Owner Transactions")


def _clean_counterparty(counterparty):
    if not counterparty:
        return "Unknown"
    return re.sub(r"\*+$", "", counterparty).strip()


def build_payroll_register(month, conn=None):
    """Computes (without persisting) the payroll line items for a month.
    Returns a list of dicts: person_name, role, amount, transaction_ids, notes."""
    own_conn = conn is None
    conn = conn or get_connection()

    rows = conn.execute(
        """SELECT * FROM transactions
           WHERE month = %s AND category IN ({}) AND debit IS NOT NULL AND debit > 0
        """.format(",".join("%s" for _ in PAYROLL_CATEGORIES)),
        (month, *PAYROLL_CATEGORIES),
    ).fetchall()

    groups = {}
    for r in rows:
        subcat = r["subcategory"] or ""
        if subcat in NON_PAYROLL_SUBCATEGORIES:
            continue

        person = FIXED_PERSON_BY_SUBCATEGORY.get(subcat) or _clean_counterparty(r["counterparty"])
        role = ROLE_BY_SUBCATEGORY.get(subcat, "staff")

        key = (person, role)
        if key not in groups:
            groups[key] = {"person_name": person, "role": role, "amount": 0.0,
                           "transaction_ids": [], "notes_parts": set()}
        groups[key]["amount"] += float(r["debit"])
        groups[key]["transaction_ids"].append(r["id"])
        if subcat:
            groups[key]["notes_parts"].add(subcat)

    if own_conn:
        conn.close()

    result = []
    for g in groups.values():
        result.append({
            "person_name": g["person_name"],
            "role": g["role"],
            "amount": round(g["amount"], 2),
            "transaction_ids": g["transaction_ids"],
            "notes": ", ".join(sorted(g["notes_parts"])),
        })
    result.sort(key=lambda x: (x["role"], -x["amount"]))
    return result


def generate_and_save(month):
    conn = get_connection()
    conn.execute("DELETE FROM payroll_register WHERE month = %s", (month,))

    lines = build_payroll_register(month, conn=conn)
    for line in lines:
        conn.execute(
            """INSERT INTO payroll_register (month, person_name, role, amount, transaction_ids, notes)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (month, line["person_name"], line["role"], line["amount"],
             json.dumps(line["transaction_ids"]), line["notes"]),
        )
    conn.commit()
    conn.close()
    return lines


def get_saved_register(month, conn=None):
    own_conn = conn is None
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM payroll_register WHERE month = %s ORDER BY role, amount DESC", (month,)
    ).fetchall()
    if own_conn:
        conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["amount"] = float(d["amount"])
        result.append(d)
    return result
