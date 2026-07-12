"""
Seeds `categorization_rules` from the existing Category Reference and
Reconciliation Notes tabs in Lily_Dahlia_Enterprise_Ledger_2026.xlsx — a direct
port per the spec, not a rebuild.

Matching semantics (see modules/categorizer.py):
  - match_field = 'counterparty' or 'note': match_pattern is looked up as a
    case-insensitive substring of that field, UNLESS match_pattern ends with
    '*', in which case it's a case-insensitive prefix match (e.g. 'ttads*'
    matches any note starting with "ttads").
  - match_field = 'both': match_pattern is "COUNTERPARTY_SUBSTR::NOTE_SUBSTR" —
    both halves must be found (as substrings) in their respective fields.
  - match_field = 'either': match_pattern is looked up as a substring of
    EITHER counterparty OR note. Real statements are inconsistent about
    whether a given vendor's name lands in the counterparty column or gets
    embedded in the transaction note/reference instead — 'either' is for
    vendors observed in both places across different statements.

Rules are tried in id order (i.e. the order below); the first match wins. More
specific rules are listed before broader/generic ones so they aren't shadowed.
"""
# (match_pattern, match_field, category, subcategory, default_flag, needs_document, notes)
RULES = [
    # --- Revenue (settlement platforms) — no document expected ---
    ("Moneymatch", "either", "Revenue", "TikTok Shop Settlement (Net)", None, False,
     "MoneyMatch inflows - net of TikTok commission/fees, NOT gross sales."),
    ("Pipo (My)", "either", "Revenue", "TikTok Shop Settlement (Net)", None, False,
     "Second TikTok Shop settlement channel confirmed Apr 2026, runs parallel to MoneyMatch."),
    ("Airpay", "either", "Revenue", "Shopee Settlement (Net)", None, False,
     "Airpay inflows - net of Shopee commission/fees, NOT gross sales. Some statement lines "
     "don't print a '*' marker after this name, so counterparty doesn't always get split out."),
    ("Billplz", "either", "Revenue", "Website Settlement - FPX", None, False,
     "FPX/online banking checkout on the Demiglow website. Some statement lines don't print a "
     "'*' marker after this name, so counterparty doesn't always get split out."),
    ("Stripe", "either", "Revenue", "Website Settlement - Credit Card", None, False,
     "Credit card checkout on the Demiglow website."),
    ("DMS A3", "note", "Revenue", "Website Settlement - Credit Card", None, False,
     "Credit card checkout settlement label."),
    ("Mohd Firdaus Bin ZA", "counterparty", "Revenue", "Other Business Income (Car Rental)", "yellow", False,
     "Confirmed Aug 2025: income from a separate side car rental business, not Demiglow."),
    ("Erra Afira Binti", "counterparty", "Revenue", "Direct Bank Transfer Sale", None, False,
     "Confirmed Jul 2025: genuine sale settled via direct bank transfer, not a settlement platform."),
    ("Mawaddatuw Warahmah", "counterparty", "Revenue", "Direct Bank Transfer Sale", None, False,
     "Confirmed Apr 2026: direct customer purchase, not through any settlement platform."),
    ("Refund Demiglow", "note", "Revenue", "Sales Returns/Refunds (Damaged Product)", "yellow", False,
     "Refund paid to a customer for a damaged/returned product - reduces Net Revenue."),
    ("Norhayati Binti Awa", "counterparty", "Revenue", "Sales Returns/Refunds (Damaged Product)", None, False,
     "Confirmed Nov 2025: contra-revenue refund for a damaged/returned product."),

    # --- Uncategorized standing rules (checked early so nothing else shadows them) ---
    ("Shopee Mobile Malays", "either", "Uncategorized",
     "Shopee Mobile Malaysia - NEEDS CONFIRMATION EACH TIME", "red", False,
     "STANDING RULE: do NOT auto-categorize as Phone Bill. This merchant code has been both a "
     "genuine phone bill and Shopee purchases for packaging/stock. Always confirm with owner. "
     "(Checked against both counterparty and note - some statements put the merchant name in one, "
     "some in the other.)"),
    ("spaylater", "note", "Uncategorized", "Shopee SPayLater (Mixed Business/Personal)", "red", False,
     "Standing rule: any SPayLater payment is always flagged red - mixed business/personal, portion unknown."),

    # --- COGS — document (invoice/receipt) expected ---
    ("Gemilang Parcel::stock", "both", "COGS", "China Buffer Stock (Agent)", None, True,
     "Gemilang Parcel buffer/stock purchase (distinguished from their shipping fees by note wording)."),
    ("Gemilang Parcel::buffer", "both", "COGS", "China Buffer Stock (Agent)", None, True,
     "'Buffer' = Glitter Nail Buffer product line stock purchase via Gemilang Parcel."),
    ("Firdaus::Stock buffer", "both", "COGS", "China Buffer Stock (Agent)", "yellow", True,
     "Same wording as Gemilang Parcel's usual stock buffer payments but routed via Firdaus."),
    ("Swam Beauty", "counterparty", "COGS", "Local Supplier Purchase", None, True,
     "Nail oil supplier, incl. purchases made via Diyanna."),
    ("Iam Worldwide", "counterparty", "COGS", "Packaging/Box/AWB Supplier", None, True,
     "Protective/outer boxes supplier."),
    ("Print Expert", "counterparty", "COGS", "Packaging/Box/AWB Supplier", None, True, "Labels supplier."),
    ("Sarman Printing", "counterparty", "COGS", "Packaging/Box/AWB Supplier", None, True,
     "Nail buffer box + nail oil box supplier."),
    ("Hamidah Binti Yusso", "counterparty", "COGS", "Packaging/Box/AWB Supplier", None, True,
     "Confirmed Sep 2025: brand's product designer - payments are design costs, filed under Packaging."),
    ("Alibaba", "either", "COGS", "China Buffer Stock (Agent)", "yellow", True,
     "Direct Alibaba.com purchase - flagged pending confirmation of what was bought."),
    ("Nail oil purchase Shopee", "note", "COGS", "Local Supplier Purchase", "yellow", True,
     "Shopee-sourced nail oil purchase - no specific supplier named beyond the marketplace."),
    ("Stock purchase Tq cards", "note", "COGS", "Packaging/Box/AWB Supplier", "yellow", True,
     "Likely thank-you cards for order inserts - no supplier named."),
    ("buffe", "note", "COGS", "China Buffer Stock (Agent)", "yellow", True,
     "Note mentions 'buffer'/'buffe' stock - matches the Glitter Nail Buffer product line pattern, "
     "checked before the generic 'stock purchase' fallback below."),
    ("nail oil", "note", "COGS", "Local Supplier Purchase", "yellow", True,
     "Generic nail oil stock purchase note, no supplier named - flagged pending confirmation."),
    ("nail stock", "note", "COGS", "Local Supplier Purchase", "yellow", True,
     "Generic nail stock purchase note, no supplier named - flagged pending confirmation."),
    ("stock purchase", "note", "COGS", "Local Supplier Purchase", "yellow", True,
     "Generic stock purchase note with no supplier named - flagged pending confirmation."),

    # --- Marketing — document (ad account confirmation) expected ---
    ("ttads*", "note", "Marketing", "TikTok Ads", None, True,
     "Paid via either Firdaus's or Diyanna's account (confirmed May 2026, dual-channel); identify by "
     "'ttads'-prefixed note regardless of payer."),
    ("fbads*", "note", "Marketing", "Meta/Facebook Ads", None, True, "Paid via Firdaus's credit card."),
    ("shoppeads*", "note", "Marketing", "Shopee Ads", None, True, "Paid via Firdaus's credit card."),
    ("shopeeads*", "note", "Marketing", "Shopee Ads", None, True, "Paid via Firdaus's credit card."),
    ("Shopee Malaysia", "either", "Marketing", "Shopee Ads", "yellow", True,
     "New Mar 2026: direct Shopee Ads payment channel via distinct numeric merchant codes, all noted "
     "'Shopee Malaysia' - flagged pending confirmation this is genuinely ad spend."),
    ("Affiliate bonu", "note", "Marketing", "Affiliate Marketing", "yellow", True,
     "Demiglow affiliate marketing program bonus payout."),
    ("Affil Bonus", "note", "Marketing", "Affiliate Marketing", "yellow", True,
     "Demiglow affiliate marketing program bonus payout."),
    ("Demiglow Affiliate", "counterparty", "Marketing", "Affiliate Marketing", "yellow", True,
     "Demiglow affiliate marketing program payout."),

    # --- Staff Cost — no document required (covered by Payroll Register) ---
    # Kak Yana must be checked before Diyanna::Salary below: Diyanna often pays her with a note like
    # "Staff salary Kak Yana", which would otherwise also match the generic Diyanna+Salary rule.
    ("Kak Yana", "either", "Staff Cost", "Part-Timer Wages - Kak Yana", None, False,
     "Operations part-timer ('Kakak'), variable/irregular pay - RM1,300/mo typical. Often paid by "
     "Diyanna with 'Kak Yana' named in the note."),
    ("Firdaus::Salary", "both", "Staff Cost", "Salary - Firdaus", None, False,
     "Firdaus's own salary, incl. Allianz/car service-labelled entries per established pattern."),
    ("Diyanna::Salary", "both", "Owner Transactions", "Owner Salary - Diyanna", None, False,
     "Diyanna 'Salary' transfers, incl. personal items (school fees/insurance/Coway/Ustazah/TNB) "
     "bundled in per instruction."),
    ("Nur Farahiyah::salary", "both", "Staff Cost", "Salary - Nur Farahiyah", None, False,
     "Nur Farahiyah's salary."),
    ("claim", "note", "Staff Cost", "Claims/Reimbursement", None, False,
     "'Claims' notes from Diyanna, Firdaus, or Nur Farahiyah."),
    ("Miza Husnina", "counterparty", "Staff Cost", "Part-Timer Wages - Live Host", None, False, None),
    ("Anis Syamimi", "counterparty", "Staff Cost", "Part-Timer Wages - Live Host", None, False, None),
    ("Nurul Balqish", "counterparty", "Staff Cost", "Part-Timer Wages - Live Host", None, False, None),
    ("Seri Purnama Baidur", "counterparty", "Staff Cost", "Part-Timer Wages - Live Host", None, False, None),
    ("Demiglow Live", "note", "Staff Cost", "Part-Timer Wages - Live Host", None, False,
     "Generic Demiglow live-hosting session payment note."),

    # --- Owner Transactions ---
    ("Direct Lending Sdn", "counterparty", "Owner Transactions", "Owner Salary - Diyanna", None, False,
     "Confirmed May 2026: Diyanna's personal loan repayment for medical reasons (SHAS_ codes)."),
    ("Duit kak Siti", "note", "Owner Transactions", "Owner Salary - Diyanna", None, False,
     "Confirmed Apr 2026: always treated as Owner Salary - Diyanna."),

    # --- Operating Expenses — document expected ---
    ("Lim Aik Say", "counterparty", "Operating Expenses", "Home Office Rent", None, True,
     "Confirmed Apr 2026: established landlord for the home office rental, RM1,900/month typical."),
    ("Rent", "note", "Operating Expenses", "Home Office Rent", None, True,
     "RM1,900/month, incl. 'Half Rent'/'Rent Partial' style split payments."),
    ("CelcomDigi Mobile", "counterparty", "Operating Expenses", "Phone Bill (Business)", None, True,
     "Confirmed Apr 2026: phone bill, recurring since 2025 (distinct from Celcom Mobile / WiFi)."),
    ("Celcom Mobile", "counterparty", "Operating Expenses", "Internet/WiFi Bill (Business)", None, True,
     "Confirmed Apr 2026: WiFi bill, recurring since 2025 (distinct from CelcomDigi Mobile / phone)."),
    ("Celcom", "note", "Operating Expenses", "Phone Bill (Business)", "yellow", True,
     "Bare 'Celcom' note (no distinct vendor counterparty matched above) - historically Diyanna's "
     "direct phone bill payment; kept yellow since WiFi vs phone can't be told apart from this alone."),
    ("Tenaga Nasional", "either", "Operating Expenses", "Electricity Bill (Business)", None, True,
     "TNB - business electricity, when billed as a standalone payment."),
    ("TNB", "note", "Operating Expenses", "Electricity Bill (Business)", None, True,
     "TNB abbreviation for Tenaga Nasional Berhad electricity bill."),
    ("Pengurusan Air", "either", "Operating Expenses", "Water Bill (Business)", "yellow", True,
     "Confirmed Oct 2025: genuine utility (water) bill."),
    ("Indah Water Konsorti", "either", "Operating Expenses", "Water Bill (Business)", "yellow", True,
     "Sewerage/water utility bill, same treatment as Pengurusan Air Selangor."),
    ("Atma Shopify", "note", "Personal/Non-business", "Other Business/Personal Use", None, False,
     "Confirmed Jul 2025: payment for a separate, non-Demiglow business - recurring monthly pattern."),
    ("Shopify Atma", "note", "Personal/Non-business", "Other Business/Personal Use", None, False,
     "Confirmed Jul 2025: payment for a separate, non-Demiglow business - recurring monthly pattern."),
    ("Shopify", "either", "Operating Expenses", "Software/Platform Fees", None, True,
     "Website platform / SaaS tool. New category, started Feb 2025."),
    ("Claude Code", "note", "Operating Expenses", "Software/Platform Fees", None, True,
     "AI software subscription confirmed Apr 2026 as a business cost."),
    ("Higgsfield", "note", "Operating Expenses", "Software/Platform Fees", None, True,
     "AI software subscription confirmed Apr 2026 as a business cost."),
    ("Norhidayah Binti Mo", "counterparty", "Operating Expenses", "Repairs/Maintenance", "yellow", True,
     "New Mar 2026: aircon/electrical servicing, tentatively business premises expense pending confirmation."),
    ("Stationary cla", "note", "Operating Expenses", "Office Supplies", "yellow", True,
     "New Mar 2026: tentatively office supplies expense, via Diyanna, pending confirmation."),
    ("Kerabat Digital", "counterparty", "Operating Expenses", "Training/Education", None, True,
     "Confirmed Oct 2025: paid TikTok class/course."),
    ("Web Impian", "counterparty", "Operating Expenses", "Training/Education", None, True,
     "Confirmed Oct 2025: paid TikTok class/course."),
    ("Mentorads Resources", "counterparty", "Operating Expenses", "Training/Education", None, True,
     "TikTok class/course provider."),
    ("Tik tok class", "note", "Operating Expenses", "Training/Education", None, True, None),

    # --- Logistics — document expected ---
    ("NH Vertex", "counterparty", "Logistics", "Shipping/Courier", None, True,
     "Confirmed Apr 2026 (after 4 months unconfirmed, Jan-Apr): genuine courier vendor."),
    ("Jacsy Logistics", "counterparty", "Logistics", "Shipping/Courier", None, True,
     "Established courier vendor (same VIP PJS-prefixed tracking code pattern as NH Vertex)."),
    ("Gemilang Parcel", "counterparty", "Logistics", "Shipping/Courier", None, True,
     "Shipping/courier fees (stock/buffer purchases via Gemilang Parcel are filed under COGS instead - "
     "see the more specific rules above)."),
    ("lalamov", "either", "Logistics", "Postage/Fuel/Delivery", None, True,
     "Matches 'Lalamove' and shorthand/typo'd 'Lalamov' - in either the counterparty (e.g. "
     "'Lalamove Malaysia Sdn Bhd') or the note (top-up notes with a numeric-only counterparty)."),
    ("TNG", "note", "Logistics", "Postage/Fuel/Delivery", None, True,
     "Toll/delivery top-up ('Top up TNG', 'TNG top up'), same pattern as established Lalamove top-ups."),
    ("Grab", "note", "Logistics", "Postage/Fuel/Delivery", None, True, None),
    ("Petrol", "note", "Logistics", "Postage/Fuel/Delivery", None, True, None),
    ("Postage", "note", "Logistics", "Postage/Fuel/Delivery", None, True, None),

    # --- Financing — no document required ---
    ("100332", "note", "Financing", "Business Term Loan - Facility A (ref ...100332)", "yellow", False,
     "Maybank Maxi Term installment, ~RM1,042/month."),
    ("201949", "note", "Financing", "Business Term Loan - Facility B (ref ...201949)", None, False,
     "ESI Payment Debit installment, ~RM1,075/month."),
    ("ESI Payment Debit", "counterparty", "Financing", "Business Term Loan - Facility B (ref ...201949)", None, False,
     "Fallback match when the note doesn't carry the ...201949 reference number."),
    ("Shopee debt", "note", "Financing", "Trade/Platform Debt Repayment", None, False, None),
    ("Debt repayment", "note", "Financing", "Trade/Platform Debt Repayment", None, False, None),
    ("loan", "note", "Financing", "Loan In / Repayment (Diyanna & Firdaus)", "yellow", False,
     "STANDING RULE (from Oct 2025): flag every such entry yellow for ongoing visibility, regardless "
     "of whether purpose is known."),

    # --- Personal/Non-business — no document required ---
    ("Lembaga Zakat Selang", "either", "Personal/Non-business", "Zakat (Selangor)", None, False, None),

    # --- Admin & Bank — no document required ---
    ("Visa Card", "note", "Admin & Bank", "Credit Card Payment", None, False, "Maybank Visa Card settlement."),
]


def seed_if_empty(conn):
    """Takes an already-open connection (see modules/db.py's init_db) so this
    module never has to import modules.db itself — that would form a circular
    import (modules.db -> db.seed_categorization_rules -> modules.db) which
    Streamlit's local-module reload watcher chases into runaway recursion."""
    count = conn.execute("SELECT COUNT(*) AS count FROM categorization_rules").fetchone()["count"]
    if count == 0:
        conn.executemany(
            """INSERT INTO categorization_rules
               (match_pattern, match_field, category, subcategory, default_flag, needs_document, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            RULES,
        )
        conn.commit()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from modules.db import get_connection

    conn = get_connection()
    seed_if_empty(conn)
    conn.close()
    print(f"Seeded {len(RULES)} categorization rules.")
