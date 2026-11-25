"""
AccountIQ - SQLite database builder and query runner.

    python database.py              build database/accountiq.db, run every query in queries.sql,
                                    and reconcile SQL results against the Pandas model
    python database.py --life 7     same, with a different useful life
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from calculations import DEFAULT_USEFUL_LIFE_YEARS, FISCAL_YEAR, build_model, load_data

ROOT = Path(__file__).parent
DB_PATH = ROOT / "database" / "accountiq.db"
SQL_PATH = ROOT / "queries.sql"

SCHEMA = """
DROP TABLE IF EXISTS customer_accounts;
DROP TABLE IF EXISTS revenue_data;
DROP TABLE IF EXISTS instrument_costs;
DROP TABLE IF EXISTS service_costs;
DROP TABLE IF EXISTS assumptions;

CREATE TABLE customer_accounts (
    account_id       TEXT PRIMARY KEY,
    account_name     TEXT NOT NULL,
    customer_type    TEXT NOT NULL,
    region           TEXT NOT NULL,
    contract_start   TEXT NOT NULL,
    instrument_count INTEGER NOT NULL
);
CREATE TABLE revenue_data (
    account_id            TEXT NOT NULL REFERENCES customer_accounts(account_id),
    month                 TEXT NOT NULL,
    gross_reagent_revenue REAL NOT NULL,
    discount_amount       REAL NOT NULL,
    PRIMARY KEY (account_id, month)
);
CREATE TABLE instrument_costs (
    instrument_id    TEXT PRIMARY KEY,
    account_id       TEXT NOT NULL REFERENCES customer_accounts(account_id),
    instrument_model TEXT NOT NULL,
    placement_date   TEXT NOT NULL,
    purchase_cost    REAL NOT NULL
);
CREATE TABLE service_costs (
    account_id          TEXT NOT NULL REFERENCES customer_accounts(account_id),
    month               TEXT NOT NULL,
    maintenance_expense REAL NOT NULL,
    repair_expense      REAL NOT NULL,
    PRIMARY KEY (account_id, month)
);
CREATE TABLE assumptions (
    useful_life_years REAL NOT NULL,
    fiscal_year       INTEGER NOT NULL
);
"""


def build_database(useful_life_years: float = DEFAULT_USEFUL_LIFE_YEARS, db_path: Path = DB_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    d = load_data()
    fmt = lambda s: s.dt.strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA)
        acc = d["accounts"].assign(contract_start=fmt(d["accounts"]["contract_start"]))
        rev = d["revenue"].assign(month=fmt(d["revenue"]["month"]))
        ins = d["instruments"].assign(placement_date=fmt(d["instruments"]["placement_date"]))
        svc = d["service"].assign(month=fmt(d["service"]["month"]))
        acc.to_sql("customer_accounts", con, if_exists="append", index=False)
        rev.to_sql("revenue_data", con, if_exists="append", index=False)
        ins.to_sql("instrument_costs", con, if_exists="append", index=False)
        svc.to_sql("service_costs", con, if_exists="append", index=False)
        con.execute("INSERT INTO assumptions VALUES (?, ?)", (useful_life_years, FISCAL_YEAR))
    return db_path


def load_queries(sql_path: Path = SQL_PATH) -> dict[str, str]:
    text = sql_path.read_text()
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_query(name: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    sql = load_queries()[name]
    with sqlite3.connect(db_path) as con:
        return pd.read_sql_query(sql, con)


def reconcile(useful_life_years: float, db_path: Path = DB_PATH) -> None:
    """SQL contribution profit must match the Pandas engine account by account."""
    sql_df = run_query("contribution_profit_by_account", db_path).set_index("account_id")
    py_df = build_model(useful_life_years).accounts.set_index("account_id")
    diff = (sql_df["contribution_profit"] - py_df.loc[sql_df.index, "contribution_profit"]).abs().max()
    assert diff < 0.01, f"SQL vs Pandas mismatch: max diff {diff}"
    print(f"Reconciliation OK: SQL and Pandas contribution profit agree for {len(sql_df)} accounts "
          f"(max diff ${diff:.4f}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--life", type=float, default=DEFAULT_USEFUL_LIFE_YEARS, help="useful life in years")
    args = ap.parse_args()
    path = build_database(args.life)
    print(f"Built {path.relative_to(ROOT)} (useful life = {args.life} years)\n")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        for name in load_queries():
            df = run_query(name)
            print(f"--- {name} ({len(df)} rows) ---")
            print(df.head(5).to_string(index=False), "\n")
    reconcile(args.life)
