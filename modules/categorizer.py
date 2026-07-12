"""
Applies categorization_rules to a transaction (counterparty + note) and
returns the category/subcategory/flag/needs_document to store. See
db/seed_categorization_rules.py for the matching semantics of match_field
('counterparty' / 'note' / 'both' / 'either') and match_pattern (substring,
or prefix when suffixed with '*').

Rules are evaluated in id order; the first match wins. A transaction that
matches nothing is left uncategorized and lands in the Review Queue.
"""
from modules.db import get_connection

NEEDS_DOCUMENT_BY_CATEGORY = {
    "COGS": True,
    "Marketing": True,
    "Operating Expenses": True,
    "Logistics": True,
    "Owner Transactions": False,
    "Staff Cost": False,
    "Financing": False,
    "Revenue": False,
}


def _field_matches(pattern, value):
    if not value:
        return False
    value_l = value.lower()
    if pattern.endswith("*"):
        return value_l.startswith(pattern[:-1].lower())
    return pattern.lower() in value_l


def rule_matches(rule, counterparty, note):
    field = rule["match_field"]
    pattern = rule["match_pattern"]

    if field == "counterparty":
        return _field_matches(pattern, counterparty)
    if field == "note":
        return _field_matches(pattern, note)
    if field == "both":
        cp_pattern, _, note_pattern = pattern.partition("::")
        return _field_matches(cp_pattern, counterparty) and _field_matches(note_pattern, note)
    if field == "either":
        return _field_matches(pattern, counterparty) or _field_matches(pattern, note)
    return False


def load_rules(conn=None):
    own_conn = conn is None
    conn = conn or get_connection()
    rules = conn.execute("SELECT * FROM categorization_rules ORDER BY id ASC").fetchall()
    if own_conn:
        conn.close()
    return rules


def categorize(counterparty, note, rules=None):
    """Returns dict: category, subcategory, flag_color, flag_note, needs_document, matched_rule_id.
    All None/False if nothing matched (review queue candidate)."""
    if rules is None:
        rules = load_rules()

    for rule in rules:
        if rule_matches(rule, counterparty, note):
            category = rule["category"]
            needs_document = bool(rule["needs_document"])
            return {
                "category": category,
                "subcategory": rule["subcategory"],
                "flag_color": rule["default_flag"],
                "flag_note": rule["notes"],
                "needs_document": needs_document,
                "matched_rule_id": rule["id"],
            }

    return {
        "category": None,
        "subcategory": None,
        "flag_color": None,
        "flag_note": None,
        "needs_document": False,
        "matched_rule_id": None,
    }


def categorize_transactions(transactions):
    """Mutates and returns a list of transaction dicts with categorization fields filled in."""
    rules = load_rules()
    for t in transactions:
        result = categorize(t.get("counterparty"), t.get("note"), rules)
        t.update(result)
    return transactions
