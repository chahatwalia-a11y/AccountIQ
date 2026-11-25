-- =====================================================================
-- AccountIQ - SQL analysis queries (SQLite)
-- Database: database/accountiq.db   (build with: python database.py)
-- Fiscal year FY2025 (Jan-Dec). Useful life is read from the `assumptions` table.
-- Each query starts with a "-- name:" tag so database.py can run them one by one.
--
-- Instrument allocation = purchase_cost / useful_life_years, pro-rated for the
-- months in FY2025 the instrument is in service and still inside its useful life.
-- month index: 1 = Jan FY2025; placement month counts as a full month.
-- =====================================================================


-- name: revenue_by_account
SELECT a.account_id,
       a.account_name,
       ROUND(SUM(r.gross_reagent_revenue), 2)                     AS gross_reagent_revenue,
       ROUND(SUM(r.discount_amount), 2)                           AS discounts,
       ROUND(SUM(r.gross_reagent_revenue - r.discount_amount), 2) AS net_revenue
FROM customer_accounts a
JOIN revenue_data r ON r.account_id = a.account_id
GROUP BY a.account_id, a.account_name
ORDER BY net_revenue DESC;


-- name: discounts_by_account
SELECT a.account_id,
       a.account_name,
       ROUND(SUM(r.discount_amount), 2)                                   AS discounts,
       ROUND(SUM(r.discount_amount) / SUM(r.gross_reagent_revenue), 4)    AS discount_rate
FROM customer_accounts a
JOIN revenue_data r ON r.account_id = a.account_id
GROUP BY a.account_id, a.account_name
ORDER BY discount_rate DESC;


-- name: service_costs_by_account
SELECT a.account_id,
       a.account_name,
       ROUND(SUM(s.maintenance_expense), 2)                        AS maintenance_expense,
       ROUND(SUM(s.repair_expense), 2)                             AS repair_expense,
       ROUND(SUM(s.maintenance_expense + s.repair_expense), 2)     AS service_costs
FROM customer_accounts a
JOIN service_costs s ON s.account_id = a.account_id
GROUP BY a.account_id, a.account_name
ORDER BY service_costs DESC;


-- name: instrument_costs_by_account
WITH params AS (
    SELECT useful_life_years, fiscal_year FROM assumptions LIMIT 1
),
inst AS (
    SELECT i.*,
           (CAST(strftime('%Y', i.placement_date) AS INTEGER) - p.fiscal_year) * 12
             + CAST(strftime('%m', i.placement_date) AS INTEGER)            AS start_idx,
           p.useful_life_years
    FROM instrument_costs i CROSS JOIN params p
),
alloc AS (
    SELECT account_id,
           purchase_cost,
           MAX(0, MIN(12, start_idx + CAST(ROUND(useful_life_years * 12) AS INTEGER) - 1)
                  - MAX(1, start_idx) + 1)                                  AS months_allocated,
           purchase_cost / useful_life_years                                AS full_year_allocation
    FROM inst
)
SELECT a.account_id,
       a.account_name,
       COUNT(*)                                                      AS instruments,
       ROUND(SUM(al.purchase_cost), 2)                               AS instrument_investment,
       ROUND(SUM(al.full_year_allocation * al.months_allocated / 12.0), 2) AS allocated_instrument_cost
FROM customer_accounts a
JOIN alloc al ON al.account_id = a.account_id
GROUP BY a.account_id, a.account_name
ORDER BY allocated_instrument_cost DESC;


-- name: contribution_profit_by_account
WITH params AS (
    SELECT useful_life_years, fiscal_year FROM assumptions LIMIT 1
),
rev AS (
    SELECT account_id,
           SUM(gross_reagent_revenue)                   AS gross_reagent_revenue,
           SUM(discount_amount)                         AS discounts,
           SUM(gross_reagent_revenue - discount_amount) AS net_revenue
    FROM revenue_data GROUP BY account_id
),
svc AS (
    SELECT account_id, SUM(maintenance_expense + repair_expense) AS service_costs
    FROM service_costs GROUP BY account_id
),
inst AS (
    SELECT i.account_id, i.purchase_cost, p.useful_life_years,
           (CAST(strftime('%Y', i.placement_date) AS INTEGER) - p.fiscal_year) * 12
             + CAST(strftime('%m', i.placement_date) AS INTEGER) AS start_idx
    FROM instrument_costs i CROSS JOIN params p
),
ins AS (
    SELECT account_id,
           SUM(purchase_cost / useful_life_years
               * MAX(0, MIN(12, start_idx + CAST(ROUND(useful_life_years * 12) AS INTEGER) - 1)
                        - MAX(1, start_idx) + 1) / 12.0) AS allocated_instrument_cost
    FROM inst GROUP BY account_id
)
SELECT a.account_id,
       a.account_name,
       a.region,
       a.customer_type,
       ROUND(rev.net_revenue, 2)                                                        AS net_revenue,
       ROUND(COALESCE(ins.allocated_instrument_cost, 0), 2)                             AS allocated_instrument_cost,
       ROUND(COALESCE(svc.service_costs, 0), 2)                                         AS service_costs,
       ROUND(rev.net_revenue - COALESCE(ins.allocated_instrument_cost, 0)
                             - COALESCE(svc.service_costs, 0), 2)                       AS contribution_profit,
       ROUND((rev.net_revenue - COALESCE(ins.allocated_instrument_cost, 0)
                              - COALESCE(svc.service_costs, 0)) / NULLIF(rev.net_revenue, 0), 4) AS contribution_margin
FROM customer_accounts a
JOIN rev      ON rev.account_id = a.account_id
LEFT JOIN svc ON svc.account_id = a.account_id
LEFT JOIN ins ON ins.account_id = a.account_id
ORDER BY contribution_profit DESC;


-- name: top_10_profitable_accounts
WITH params AS (
    SELECT useful_life_years, fiscal_year FROM assumptions LIMIT 1
),
rev AS (
    SELECT account_id, SUM(gross_reagent_revenue - discount_amount) AS net_revenue
    FROM revenue_data GROUP BY account_id
),
svc AS (
    SELECT account_id, SUM(maintenance_expense + repair_expense) AS service_costs
    FROM service_costs GROUP BY account_id
),
inst AS (
    SELECT i.account_id, i.purchase_cost, p.useful_life_years,
           (CAST(strftime('%Y', i.placement_date) AS INTEGER) - p.fiscal_year) * 12
             + CAST(strftime('%m', i.placement_date) AS INTEGER) AS start_idx
    FROM instrument_costs i CROSS JOIN params p
),
ins AS (
    SELECT account_id,
           SUM(purchase_cost / useful_life_years
               * MAX(0, MIN(12, start_idx + CAST(ROUND(useful_life_years * 12) AS INTEGER) - 1)
                        - MAX(1, start_idx) + 1) / 12.0) AS allocated_instrument_cost
    FROM inst GROUP BY account_id
),
profit AS (
    SELECT a.account_id, a.account_name, a.region, a.customer_type,
           rev.net_revenue,
           rev.net_revenue - COALESCE(ins.allocated_instrument_cost, 0) - COALESCE(svc.service_costs, 0) AS contribution_profit
    FROM customer_accounts a
    JOIN rev      ON rev.account_id = a.account_id
    LEFT JOIN svc ON svc.account_id = a.account_id
    LEFT JOIN ins ON ins.account_id = a.account_id
)
SELECT RANK() OVER (ORDER BY contribution_profit DESC)     AS profit_rank,
       account_id,
       account_name,
       region,
       customer_type,
       ROUND(net_revenue, 2)                               AS net_revenue,
       ROUND(contribution_profit, 2)                       AS contribution_profit,
       ROUND(contribution_profit / net_revenue, 4)         AS contribution_margin
FROM profit
ORDER BY contribution_profit DESC
LIMIT 10;
