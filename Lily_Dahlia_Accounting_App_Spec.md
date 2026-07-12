# Lily Dahlia Enterprise — Accounting App Technical Spec

## 1. Purpose

A local, single-user accounting application replacing the current manual (chat-based) monthly bank
statement processing. The bank statement is always the source of truth; sales reports, receipts,
stock counts, and vouchers all attach evidence to what the bank already shows. Runs entirely on the
owner's own computer — no hosting, no external server, no data leaves the machine unless exported.

## 2. Tech Stack (recommended)

- **Language:** Python 3.11+
- **UI:** Streamlit (simple local web UI, runs at `localhost:8501`, no separate frontend build needed)
- **Database:** SQLite (single file, `ledger.db` — relational, so transactions/receipts/vouchers/sales
  records can reference each other; no server to run)
- **PDF parsing:** `pdfplumber` (bank statements, PDF sales reports)
- **Spreadsheet parsing:** `openpyxl` / `pandas` (Excel/CSV sales reports)
- **Excel output:** `openpyxl` (final ledger/financial statement export, matching existing format)
- **Document storage:** local folder (`/documents/{year}/{month}/`), referenced by path in the DB
- **PDF generation (vouchers, payroll register):** `reportlab` or `weasyprint` (HTML→PDF)

## 3. Data Model (core tables)

```
transactions
  id, month, date, counterparty, note, debit, credit, running_balance,
  category, subcategory, flag_color, flag_note, needs_document (bool),
  document_id (nullable FK), source ("bank_statement")

sales_records
  id, platform ("tiktok"/"shopee"/"shopify"), order_id, order_date,
  gross_amount, platform_fee, net_settlement_amount, settlement_transaction_id (nullable FK),
  status ("settled"/"pending"/"refunded")

documents
  id, filename, filepath, uploaded_date, document_type
  ("invoice"/"receipt"/"ad_confirmation"/"other"), linked_transaction_id (nullable FK),
  linked_sales_record_id (nullable FK), notes

vouchers
  id, voucher_number ("PV-2026-001" / "CV-2026-001"), voucher_type ("payment"/"claim"),
  transaction_id (FK), document_id (nullable FK), prepared_by, approved_by,
  date_generated, pdf_path

payroll_register
  id, month, person_name, role ("owner"/"staff"/"live_host"), amount,
  transaction_ids (list of FKs), notes

inventory_counts
  id, month, product_name, quantity_on_hand, unit_cost (weighted avg), total_value

categorization_rules
  id, match_pattern, match_field ("counterparty"/"note"), category, subcategory,
  default_flag, needs_document (bool), notes
```

## 4. Module Breakdown & Build Phases

### Phase 1 — Bank Statement Processing + Outstanding Documents + Vouchers (BUILD FIRST)
- Upload bank statement PDF → auto-extract all transactions (date, counterparty, note, amount, balance)
- Auto-verify balance chain (opening → closing, matches printed totals) — hard stop if mismatched
- Apply `categorization_rules` table to auto-categorize; anything unmatched goes to a review queue
- Flag rules ported directly from the existing Category Reference / Reconciliation Notes tabs
- For every transaction where `needs_document = true` (COGS, Marketing, Operating Expenses,
  Logistics) and no document is linked yet → appears on the **Outstanding Documents** list
  - Persists across months until resolved
  - Shows: date, counterparty, amount, category, expected document type
- Attach a document (upload photo/PDF, or manually type a reference if no file exists) → clears from
  the outstanding list, auto-generates a **Payment Voucher** or **Claim Voucher** (PDF), auto-numbered
  sequentially per year
- **Monthly Payroll Register** — auto-generated per month listing every person paid (staff wages,
  live host wages, owner drawings as line items), no statutory deduction columns

### Phase 2 — Sales Report Ingestion + Gross vs Settlement Reconciliation
- Upload TikTok/Shopee/Shopify sales reports (CSV/Excel/PDF, format varies per platform — needs a
  small parser per platform)
- Match each sales record to its eventual settlement transaction (by amount/date proximity, confirm
  manually where ambiguous)
- Unmatched sales records with no settlement yet = Accounts Receivable (pending payout)
- Reveals true platform fees (gross − net settlement) as its own tracked figure

### Phase 3 — Monthly Stock Count + Financial Statements
- Simple monthly input: product name + quantity on hand (owner's own estimate, no per-unit tracking)
- Weighted-average cost per product computed from COGS purchase history
- COGS = Opening Inventory + Purchases − Closing Inventory
- **P&L** — now on real (gross) sales, not settlement
- **Balance Sheet** — Inventory, Accounts Receivable, Accounts Payable (unpaid supplier invoices —
  flagged from Outstanding Documents with no payment yet), Fixed Assets (manual entry if any),
  Owner's Capital (opening capital + net profit − drawings)
- **Cash Flow Statement** — derived from P&L + Balance Sheet changes (operating/investing/financing)

### Phase 4 — Tax Summary + Dashboard
- Personal income tax computation (sole proprietorship, pass-through to owner's individual return) —
  approximate estimate, not a filing-ready computation
- Dashboard: sales by channel, expenses by category, ad spend/MER trend, cash position, all the KPIs
  from the existing Insights tabs, now on gross sales

## 5. Categorization Rules — Seed Data

The `categorization_rules` table should be pre-populated from the existing Category Reference and
Reconciliation Notes tabs in `Lily_Dahlia_Enterprise_Ledger_2026.xlsx` — this is a direct port, not a
rebuild. Examples: `SHOPEE MOBILE MALAYS → always red, needs_document=true`; `NH VERTEX → Logistics/
Shipping-Courier, no flag`; `ttads* (either Firdaus or Diyanna) → Marketing/TikTok Ads`.

## 6. needs_document Default Mapping

| Category | Needs Document? |
|---|---|
| COGS | Yes |
| Marketing | Yes |
| Operating Expenses | Yes |
| Logistics | Yes |
| Owner Transactions (drawings) | No |
| Staff Cost (wages) | No — covered by Payroll Register |
| Financing (loans) | No |
| Revenue (settlements) | No |

## 7. Document/Voucher Numbering

- Payment Vouchers: `PV-{year}-{sequential 3-digit}` e.g. `PV-2026-001`
- Claim Vouchers: `CV-{year}-{sequential 3-digit}` e.g. `CV-2026-001`
- Sequential per calendar year, never reused, gaps allowed (e.g. if a voucher is voided)

## 8. Out of Scope / Explicitly Simplified

- No EPF/SOCSO/EIS statutory payroll deductions (all staff informal/casual per owner)
- No per-unit/per-SKU inventory tracking — periodic (monthly count) method only
- Tax summary is an approximation for planning purposes, not a filing-ready LHDN submission
- Single user, no multi-user accounts or permissions system
- No cloud sync/backup built in initially (local file only — recommend owner keeps their own backup)

## 9. Deployment (Local — runs on the owner's own laptop)

Confirmed: the app runs entirely locally. No server, no hosting account, no ongoing cost. Total
footprint (Python + dependencies + database + years of receipt scans) is well under 2GB, so laptop
storage is not a real constraint.

### Requirements
- Python 3.11+ installed on the laptop (one-time install)
- The app folder lives somewhere normal, e.g. `~/Documents/lily-dahlia-accounting/`
- Everything — code, database (`ledger.db`), uploaded documents, generated vouchers — stays in that
  one folder

### Running it
- Claude Code sets up a virtual environment (`venv`) so the app's dependencies don't clash with
  anything else on the laptop
- Starting the app is a single command (`streamlit run app.py`), which opens a browser tab at
  `localhost:8501`
- No HTTPS/password-protection needed — it's never exposed to the internet, only reachable from the
  laptop itself

### Backups
- Since there's no server, backup responsibility shifts to the owner: periodically copy the whole
  app folder (or just `ledger.db` + `documents/` + `vouchers/`) to a USB drive, external HDD, or a
  personal cloud storage folder (Google Drive/Dropbox desktop sync folder works well for this —
  it backs up automatically in the background without any app changes needed)
- Recommend Claude Code add a simple "Export Backup" button in the app itself that zips the whole
  data folder with one click, making manual backups painless

### Future option
- If it's ever useful to check the app from a phone, or let Diyanna access it too, moving to
  Supabase (managed database/storage) + Railway or Render (managed app hosting) is the natural next
  step — but nothing in the local build needs to anticipate this; it's a separate migration later,
  not a design constraint now

## 10. Suggested Repo Structure

```
lily-dahlia-accounting/
├── app.py                    # Streamlit entry point
├── requirements.txt
├── db/
│   ├── schema.sql
│   └── seed_categorization_rules.py
├── modules/
│   ├── bank_statement_parser.py
│   ├── balance_verifier.py
│   ├── categorizer.py
│   ├── outstanding_documents.py
│   ├── voucher_generator.py
│   ├── payroll_register.py
│   ├── sales_report_parser.py
│   ├── reconciliation.py
│   ├── inventory.py
│   ├── financial_statements.py
│   ├── tax_summary.py
│   └── dashboard.py
├── documents/                # uploaded receipts/invoices, organized by year/month
├── vouchers/                 # generated voucher PDFs
└── ledger.db
```
