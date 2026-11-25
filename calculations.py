"""
AccountIQ - financial calculations engine (Pandas).

Definitions (FY2025, annual figures per account):
    Net Revenue                = Gross Reagent Revenue - Discounts
    Allocated Instrument Cost  = Instrument Purchase Cost / Useful Life (years)
                                 (straight-line; pro-rated for months in service during the fiscal year)
    Service Costs              = Maintenance Expense + Repair Expense
    Contribution Profit        = Net Revenue - Allocated Instrument Cost - Service Costs
    Contribution Margin        = Contribution Profit / Net Revenue

No double counting:
    * Discounts reduce revenue once; they are NOT also subtracted as a cost.
    * Instrument purchase cost enters profit ONLY through the annual allocation, never as a
      lump sum. The full purchase cost is shown separately as "instrument investment" (capital),
      not deducted from profit.
    * Maintenance and repair are operating expenses, expensed in the month incurred, and are not
      part of the instrument allocation.

Month convention: an instrument placed on the 1st of month M is allocated from month M onward,
and stops once it has been allocated for (useful_life_years * 12) months.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
# Data files may sit in a data/ folder or directly in the project root (e.g. after a flat GitHub upload).
DATA_DIR = ROOT / "data" if (ROOT / "data" / "customer_accounts.csv").exists() else ROOT
FISCAL_YEAR = 2025
DEFAULT_USEFUL_LIFE_YEARS = 5


@dataclass
class Thresholds:
    """Rules used to flag margin opportunities. Tune freely."""
    high_revenue_percentile: float = 0.60   # top 40% of accounts by net revenue = "high revenue"
    low_margin: float = 0.65                # contribution margin below this = "low margin"
    excessive_discount_rate: float = 0.20   # discounts > 20% of gross revenue
    high_service_ratio: float = 0.20        # service costs > 20% of net revenue
    high_instrument_ratio: float = 0.25     # allocated instrument cost > 25% of net revenue


LIMITATIONS = [
    "Straight-line allocation spreads purchase cost evenly over the useful life. It ignores salvage "
    "value, the time value of money, financing cost and the actual contract term.",
    "A single useful life is applied to every instrument model. Real fleets differ by model and "
    "utilization, and an instrument can be redeployed to another account.",
    "Fully allocated instruments (older than the useful life) carry zero allocated cost, which can "
    "make older placements look more profitable than a replacement-cost view would.",
    "This is contribution profit, not net profit. It excludes cost of goods sold for reagents, "
    "sales and field-support labor, freight, overhead and taxes.",
    "Service costs are taken as recorded by account. Shared field-service costs and warranty "
    "reimbursements are not allocated.",
    "Discounts are treated as a single line. Rebates, free goods and price-tier effects are not modeled.",
    "Twelve months of synthetic data. Results show the method; they are not benchmarks.",
]

MANAGEMENT_ACTIONS = {
    "High revenue, low margin": [
        "Run a full account P&L review with sales and service leadership.",
        "Renegotiate pricing tiers or volume commitments at the next renewal.",
        "Tie future discounts and capital placements to margin-based hurdles.",
    ],
    "Excessive discounting": [
        "Benchmark the discount rate against peer accounts of similar volume.",
        "Replace blanket discounts with tiered, volume-linked pricing.",
        "Require deal-desk approval for discounts above the policy threshold.",
    ],
    "High service costs": [
        "Analyze repair frequency for chronic instrument issues; consider a refurbish or swap.",
        "Shift to preventive maintenance scheduling to cut unplanned repairs.",
        "Review service-contract pricing and pass-through terms at renewal.",
    ],
    "High instrument cost relative to revenue": [
        "Assess utilization; consolidate or redeploy under-used instruments.",
        "Add minimum reagent purchase commitments to placement agreements.",
        "Consider reagent-rental or leasing structures for new placements.",
    ],
}


@dataclass
class ModelResults:
    accounts: pd.DataFrame          # one row per account, all profitability metrics
    monthly: pd.DataFrame           # portfolio monthly P&L
    monthly_by_account: pd.DataFrame
    instruments: pd.DataFrame       # per-instrument allocation detail
    findings: pd.DataFrame          # flagged margin opportunities
    useful_life_years: float
    thresholds: Thresholds = field(default_factory=Thresholds)


def load_data(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    d = {
        "accounts": pd.read_csv(data_dir / "customer_accounts.csv", parse_dates=["contract_start"]),
        "revenue": pd.read_csv(data_dir / "revenue_data.csv", parse_dates=["month"]),
        "instruments": pd.read_csv(data_dir / "instrument_costs.csv", parse_dates=["placement_date"]),
        "service": pd.read_csv(data_dir / "service_costs.csv", parse_dates=["month"]),
    }
    return d


def months_in_service(placement: pd.Series, useful_life_years: float, fiscal_year: int = FISCAL_YEAR) -> pd.Series:
    """Months during the fiscal year in which the instrument is in service AND still within its useful life."""
    start_idx = (placement.dt.year - fiscal_year) * 12 + placement.dt.month   # 1 = Jan of FY
    end_idx = start_idx + int(round(useful_life_years * 12)) - 1              # last allocated month
    return (np.minimum(12, end_idx) - np.maximum(1, start_idx) + 1).clip(lower=0)


def instrument_allocation(instruments: pd.DataFrame, useful_life_years: float) -> pd.DataFrame:
    if useful_life_years <= 0:
        raise ValueError("useful_life_years must be positive")
    df = instruments.copy()
    df["annual_allocation_full_year"] = df["purchase_cost"] / useful_life_years
    df["months_allocated_in_fy"] = months_in_service(df["placement_date"], useful_life_years)
    df["allocated_instrument_cost"] = df["annual_allocation_full_year"] * df["months_allocated_in_fy"] / 12
    return df


def _monthly_instrument_cost(inst: pd.DataFrame, useful_life_years: float) -> pd.DataFrame:
    """Spread each instrument's allocation into the specific FY months it covers."""
    rows = []
    life_m = int(round(useful_life_years * 12))
    for r in inst.itertuples():
        start = (r.placement_date.year - FISCAL_YEAR) * 12 + r.placement_date.month
        for m in range(1, 13):
            if start <= m <= start + life_m - 1:
                rows.append((r.account_id, pd.Timestamp(FISCAL_YEAR, m, 1), r.purchase_cost / useful_life_years / 12))
    out = pd.DataFrame(rows, columns=["account_id", "month", "allocated_instrument_cost"])
    return out.groupby(["account_id", "month"], as_index=False).sum()


def safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b != 0, a / b, np.nan)


def build_model(useful_life_years: float = DEFAULT_USEFUL_LIFE_YEARS,
                thresholds: Thresholds | None = None,
                data: dict[str, pd.DataFrame] | None = None) -> ModelResults:
    thresholds = thresholds or Thresholds()
    data = data or load_data()
    acc, rev, inst, svc = (data[k].copy() for k in ("accounts", "revenue", "instruments", "service"))

    # --- monthly, by account ---
    rev["net_revenue"] = rev["gross_reagent_revenue"] - rev["discount_amount"]
    svc["service_costs"] = svc["maintenance_expense"] + svc["repair_expense"]
    m_inst = _monthly_instrument_cost(inst, useful_life_years)
    mba = (rev.merge(svc, on=["account_id", "month"], how="outer")
              .merge(m_inst, on=["account_id", "month"], how="left")
              .fillna({"allocated_instrument_cost": 0.0}))
    mba["contribution_profit"] = mba["net_revenue"] - mba["allocated_instrument_cost"] - mba["service_costs"]

    # --- annual, by account ---
    inst_alloc = instrument_allocation(inst, useful_life_years)
    inst_by_acct = inst_alloc.groupby("account_id").agg(
        instrument_investment=("purchase_cost", "sum"),
        allocated_instrument_cost=("allocated_instrument_cost", "sum"),
    )
    rev_by_acct = rev.groupby("account_id")[["gross_reagent_revenue", "discount_amount", "net_revenue"]].sum()
    svc_by_acct = svc.groupby("account_id")[["maintenance_expense", "repair_expense", "service_costs"]].sum()

    a = (acc.set_index("account_id")
            .join(rev_by_acct).join(inst_by_acct).join(svc_by_acct)
            .fillna(0.0))
    a["contribution_profit"] = a["net_revenue"] - a["allocated_instrument_cost"] - a["service_costs"]
    a["contribution_margin"] = safe_div(a["contribution_profit"], a["net_revenue"])
    a["discount_rate"] = safe_div(a["discount_amount"], a["gross_reagent_revenue"])
    a["service_cost_ratio"] = safe_div(a["service_costs"], a["net_revenue"])
    a["instrument_cost_ratio"] = safe_div(a["allocated_instrument_cost"], a["net_revenue"])
    a["profit_rank"] = a["contribution_profit"].rank(ascending=False, method="min").astype(int)
    a = a.reset_index().sort_values("profit_rank")

    # sanity check: annual totals reconcile to the monthly build (guards against double counting)
    assert np.isclose(a["contribution_profit"].sum(), mba["contribution_profit"].sum()), "Annual vs monthly mismatch"

    monthly = (mba.groupby("month")[["gross_reagent_revenue", "discount_amount", "net_revenue",
                                     "allocated_instrument_cost", "service_costs", "contribution_profit"]]
                  .sum().reset_index())

    findings = identify_opportunities(a, thresholds)
    return ModelResults(a, monthly, mba, inst_alloc, findings, useful_life_years, thresholds)


def identify_opportunities(a: pd.DataFrame, t: Thresholds) -> pd.DataFrame:
    rev_cut = a["net_revenue"].quantile(t.high_revenue_percentile)
    # gap_to_threshold: profit $ that would be recovered if the account moved exactly to the threshold.
    # Gaps are NOT additive across finding types (they overlap), so never sum them across categories.
    rules = [
        ("High revenue, low margin",
         (a["net_revenue"] >= rev_cut) & (a["contribution_margin"] < t.low_margin),
         lambda r: f"Net revenue ${r.net_revenue/1e6:,.2f}M (top {1-t.high_revenue_percentile:.0%}) "
                   f"but margin of {r.contribution_margin:.1%} vs {t.low_margin:.0%} target",
         lambda r: t.low_margin * r.net_revenue - r.contribution_profit),
        ("Excessive discounting",
         a["discount_rate"] > t.excessive_discount_rate,
         lambda r: f"Discounts are {r.discount_rate:.1%} of gross revenue "
                   f"(${r.discount_amount/1e3:,.0f}K) vs {t.excessive_discount_rate:.0%} policy",
         lambda r: r.discount_amount - t.excessive_discount_rate * r.gross_reagent_revenue),
        ("High service costs",
         a["service_cost_ratio"] > t.high_service_ratio,
         lambda r: f"Service costs are {r.service_cost_ratio:.1%} of net revenue "
                   f"(${r.service_costs/1e3:,.0f}K; repairs ${r.repair_expense/1e3:,.0f}K)",
         lambda r: r.service_costs - t.high_service_ratio * r.net_revenue),
        ("High instrument cost relative to revenue",
         a["instrument_cost_ratio"] > t.high_instrument_ratio,
         lambda r: f"Allocated instrument cost is {r.instrument_cost_ratio:.1%} of net revenue "
                   f"(${r.instrument_investment/1e3:,.0f}K installed base)",
         lambda r: r.allocated_instrument_cost - t.high_instrument_ratio * r.net_revenue),
    ]
    out = []
    for name, mask, detail, gap in rules:
        for r in a[mask].itertuples():
            out.append(dict(account_id=r.account_id, account_name=r.account_name, region=r.region,
                            customer_type=r.customer_type, finding=name, detail=detail(r),
                            net_revenue=r.net_revenue, contribution_margin=r.contribution_margin,
                            contribution_profit=r.contribution_profit, gap_to_threshold=gap(r),
                            actions=" | ".join(MANAGEMENT_ACTIONS[name])))
    cols = ["account_id", "account_name", "region", "customer_type", "finding", "detail",
            "net_revenue", "contribution_margin", "contribution_profit", "gap_to_threshold", "actions"]
    return pd.DataFrame(out, columns=cols)


def portfolio_kpis(a: pd.DataFrame) -> dict[str, float]:
    net = a["net_revenue"].sum()
    return dict(
        total_net_revenue=net,
        total_contribution_profit=a["contribution_profit"].sum(),
        avg_contribution_margin=float(np.nanmean(a["contribution_margin"])) if len(a) else np.nan,  # simple avg across accounts
        weighted_contribution_margin=a["contribution_profit"].sum() / net if net else np.nan,
        total_instrument_investment=a["instrument_investment"].sum(),
        total_service_expenses=a["service_costs"].sum(),
        account_count=len(a),
    )


if __name__ == "__main__":
    res = build_model()
    k = portfolio_kpis(res.accounts)
    print(f"Useful life: {res.useful_life_years} years")
    for key, v in k.items():
        print(f"  {key:<30} {v:,.4f}" if isinstance(v, float) else f"  {key:<30} {v}")
    cols = ["account_name", "net_revenue", "discount_rate", "allocated_instrument_cost", "service_costs",
            "contribution_profit", "contribution_margin", "profit_rank"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(res.accounts[cols].round(3).to_string(index=False))
        print("\nFindings:", len(res.findings))
        print(res.findings.groupby("finding").size())
