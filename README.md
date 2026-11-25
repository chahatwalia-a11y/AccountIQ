# AccountIQ

Customer Account Profitability Intelligence

Illustrative prototype using synthetic data. Not actual Roche or customer financial information.

## Overview

AccountIQ measures the contribution profit of 30 fictional hospital and laboratory accounts for a diagnostics business that sells reagents, places instruments at customer sites, and services those instruments. It combines reagent revenue, commercial discounts, instrument capital, and service costs to show which accounts are truly profitable, then flags margin improvement opportunities with suggested management actions.

The model is built three ways: in Python (Pandas), in SQL (SQLite), and as a formula-driven Excel workbook. All three reconcile to the cent.

## Contents

- app.py: Streamlit and Plotly dashboard
- generate_data.py: synthetic data generator (seeded, reproducible)
- calculations.py: profitability engine, opportunity rules, and documented limitations
- database.py: builds the SQLite database, runs queries.sql, and reconciles results with Pandas
- build_excel.py: builds the Excel workbook
- queries.sql: SQL analysis queries
- requirements.txt: Python dependencies
- customer_accounts.csv, revenue_data.csv, instrument_costs.csv, service_costs.csv: synthetic data
- accountiq.db: SQLite database
- AccountIQ_Financial_Model.xlsx: Excel financial model

## Running the project

The data, database, and workbook are already included. To open the dashboard:

```
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at http://localhost:8501.

To rebuild everything from scratch, run the scripts in this order:

```
python generate_data.py
python calculations.py
python database.py
python build_excel.py
streamlit run app.py
```

## Calculations

- Net Revenue = Gross Reagent Revenue - Discounts
- Allocated Instrument Cost = Instrument Purchase Cost / Useful Life (years)
- Service Costs = Maintenance Expense + Repair Expense
- Contribution Profit = Net Revenue - Allocated Instrument Cost - Service Costs
- Contribution Margin = Contribution Profit / Net Revenue

Useful life defaults to 5 years and can be changed in the dashboard, in the Excel Read Me sheet, or with `python database.py --life 7`.

Instrument cost is pro-rated for the months an instrument was in service during FY2025 and within its useful life. An instrument placed in April 2025 carries 9 of 12 months of allocation. An instrument older than its useful life carries none.

## Avoiding double counting

- Discounts reduce revenue once and are not deducted again as a cost.
- Instrument purchase cost reaches profit only through the annual allocation. The full purchase price is reported separately as instrument investment.
- Maintenance and repair are operating expenses, kept separate from the instrument allocation.
- The code checks that annual totals equal the monthly build, and that SQL results match Pandas for every account. The Excel dashboard includes check cells that must equal zero.

## Limitations

- Straight-line allocation ignores salvage value, the time value of money, financing cost, and actual contract terms.
- A single useful life applies to all instrument models, although real fleets vary by model and utilization.
- Fully allocated older instruments carry no cost, which can make older placements look more profitable than a replacement-cost view would.
- Contribution profit excludes reagent cost of goods sold, sales and field labor, freight, overhead, and taxes, so margins are higher than a full P&L would show. The metric is designed to compare accounts.
- Service costs are taken as recorded by account. Shared field service costs and warranty recoveries are not allocated.
- Discounts are modeled as a single line. Rebates, free goods, and pricing tiers are not modeled.
- The data is synthetic and covers 12 months. Results illustrate the method and are not benchmarks.

## Margin opportunity rules

Default thresholds, adjustable in the dashboard:

- High revenue, low margin: net revenue at or above the 60th percentile and contribution margin below 65%
- Excessive discounting: discounts above 20% of gross revenue
- High service costs: service costs above 20% of net revenue
- High instrument cost relative to revenue: allocated instrument cost above 25% of net revenue

Each finding shows a profit gap, defined as the profit recovered if the account met the threshold exactly. Findings can overlap, so profit gaps are not added across categories.

## Excel workbook

The workbook has seven sheets: Read Me, Customer Accounts, Revenue Data, Instrument Costs, Service Costs, Account Profitability, and Executive Dashboard. Raw data is entered as inputs, and all calculations are live formulas driven by the assumption cells on the Read Me sheet. The workbook includes conditional formatting, a profitability ranking, a monthly trend, top and bottom ten account tables, and charts.

## SQL

queries.sql contains queries for revenue, discounts, service costs, instrument costs, and contribution profit by account, plus the top ten profitable accounts. Useful life is read from the assumptions table. Run all queries with `python database.py`.
