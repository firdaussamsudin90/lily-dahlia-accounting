-- Lily Dahlia Enterprise Accounting App — Postgres schema (Supabase)
-- Matches the data model in Lily_Dahlia_Accounting_App_Spec.md, section 3.
-- All tables from the spec are created up front (even Phase 2/3 tables) so later
-- phases don't require a migration; only Phase 1 modules populate/use them for now.
--
-- Money fields use NUMERIC(12,2) rather than floating point, now that a real
-- database makes that easy — avoids binary-float rounding drift on financial
-- amounts that the original SQLite/REAL prototype carried.

-- Tracks each uploaded bank statement PDF and its verification status.
-- Not in the spec's core table list, but needed to support the Phase 1
-- requirement to "auto-verify balance chain ... hard stop if mismatched"
-- and to know which month/statement a batch of transactions came from.
CREATE TABLE IF NOT EXISTS bank_statements (
    id SERIAL PRIMARY KEY,
    month TEXT NOT NULL,                  -- "2026-01"
    filename TEXT NOT NULL,
    storage_path TEXT,                    -- path within the Supabase Storage bucket
    opening_balance NUMERIC(12,2) NOT NULL,
    closing_balance NUMERIC(12,2) NOT NULL,
    statement_total_debit NUMERIC(12,2),
    statement_total_credit NUMERIC(12,2),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    upload_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT,
    storage_path TEXT,                    -- path within the Supabase Storage bucket
    uploaded_date TEXT NOT NULL,
    document_type TEXT,                   -- 'invoice'/'receipt'/'ad_confirmation'/'other'
    linked_transaction_id INTEGER,
    linked_sales_record_id INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    month TEXT NOT NULL,                  -- "2026-01"
    date TEXT NOT NULL,                   -- ISO "2026-01-31"
    counterparty TEXT,
    note TEXT,
    debit NUMERIC(12,2),
    credit NUMERIC(12,2),
    running_balance NUMERIC(12,2),
    category TEXT,
    subcategory TEXT,
    flag_color TEXT,                      -- 'yellow' / 'red' / NULL
    flag_note TEXT,
    needs_document BOOLEAN NOT NULL DEFAULT FALSE,
    document_id INTEGER REFERENCES documents(id),
    source TEXT NOT NULL DEFAULT 'bank_statement',
    bank_statement_id INTEGER REFERENCES bank_statements(id)
);

CREATE TABLE IF NOT EXISTS sales_records (
    id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,               -- 'tiktok' / 'shopee' / 'shopify'
    order_id TEXT,
    order_date TEXT,
    gross_amount NUMERIC(12,2),
    platform_fee NUMERIC(12,2),
    net_settlement_amount NUMERIC(12,2),
    settlement_transaction_id INTEGER REFERENCES transactions(id),
    status TEXT                           -- 'settled' / 'pending' / 'refunded'
);

-- documents.linked_transaction_id / linked_sales_record_id are deliberately
-- plain integers, not FK constraints: transactions/sales_records are created
-- after documents (to satisfy transactions.document_id -> documents.id), and
-- Postgres has no "ADD CONSTRAINT IF NOT EXISTS", so a back-reference here
-- would break the idempotent CREATE TABLE IF NOT EXISTS pattern used
-- everywhere else in this file. Enforced at the application layer instead.

CREATE TABLE IF NOT EXISTS vouchers (
    id SERIAL PRIMARY KEY,
    voucher_number TEXT NOT NULL UNIQUE,  -- "PV-2026-001" / "CV-2026-001"
    voucher_type TEXT NOT NULL,           -- 'payment' / 'claim'
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    document_id INTEGER REFERENCES documents(id),
    prepared_by TEXT,
    approved_by TEXT,
    date_generated TEXT NOT NULL,
    storage_path TEXT                     -- path within the Supabase Storage bucket
);

CREATE TABLE IF NOT EXISTS payroll_register (
    id SERIAL PRIMARY KEY,
    month TEXT NOT NULL,
    person_name TEXT NOT NULL,
    role TEXT NOT NULL,                   -- 'owner' / 'staff' / 'live_host'
    amount NUMERIC(12,2) NOT NULL,
    transaction_ids TEXT,                 -- JSON list of FKs
    notes TEXT
);

CREATE TABLE IF NOT EXISTS inventory_counts (
    id SERIAL PRIMARY KEY,
    month TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity_on_hand NUMERIC(12,2),
    unit_cost NUMERIC(12,2),
    total_value NUMERIC(12,2)
);

CREATE TABLE IF NOT EXISTS categorization_rules (
    id SERIAL PRIMARY KEY,
    match_pattern TEXT NOT NULL,
    match_field TEXT NOT NULL,            -- 'counterparty' / 'note' / 'both' / 'either'
    category TEXT NOT NULL,
    subcategory TEXT,
    default_flag TEXT,                    -- 'yellow' / 'red' / NULL
    needs_document BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_month ON transactions(month);
CREATE INDEX IF NOT EXISTS idx_transactions_needs_doc ON transactions(needs_document, document_id);
CREATE INDEX IF NOT EXISTS idx_transactions_flag ON transactions(flag_color);
