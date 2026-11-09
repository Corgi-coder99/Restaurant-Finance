PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS branches (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency='VND')
);
-- Recognized net revenue/expenses, not cash movements or raw purchase invoices.
-- Amounts in whole VND; purchases must first be adjusted for inventory.
CREATE TABLE IF NOT EXISTS entries (
 id INTEGER PRIMARY KEY,
 branch_id TEXT NOT NULL REFERENCES branches(id),
 document_id TEXT NOT NULL,
 line_number INTEGER NOT NULL CHECK(line_number > 0),
 recognized_date TEXT NOT NULL CHECK(date(recognized_date) IS NOT NULL AND recognized_date=date(recognized_date)),
 category TEXT NOT NULL CHECK(category IN ('revenue','food','labor','rent','other')),
 amount_vnd INTEGER NOT NULL CHECK(typeof(amount_vnd)='integer' AND amount_vnd > 0),
 source TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(branch_id,document_id,line_number)
);
CREATE INDEX IF NOT EXISTS idx_entries_period ON entries(recognized_date,branch_id);
CREATE VIEW IF NOT EXISTS monthly_pnl AS
SELECT branch_id, substr(recognized_date,1,7) AS month,
 SUM(CASE WHEN category='revenue' THEN amount_vnd ELSE 0 END) AS revenue_vnd,
 SUM(CASE WHEN category='food' THEN amount_vnd ELSE 0 END) AS food_vnd,
 SUM(CASE WHEN category='labor' THEN amount_vnd ELSE 0 END) AS labor_vnd,
 SUM(CASE WHEN category='rent' THEN amount_vnd ELSE 0 END) AS rent_vnd,
 SUM(CASE WHEN category='other' THEN amount_vnd ELSE 0 END) AS other_vnd,
 SUM(CASE WHEN category='revenue' THEN amount_vnd ELSE -amount_vnd END) AS operating_profit_vnd
FROM entries GROUP BY branch_id,substr(recognized_date,1,7);
