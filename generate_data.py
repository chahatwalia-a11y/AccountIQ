"""
AccountIQ - synthetic data generator.

Creates 12 months (FY2025, Jan-Dec) of fictional data for 30 fictional
hospital and laboratory accounts. Every name, number and date is invented.
No real company or customer information is used.

Outputs (CSV, in ./data):
    customer_accounts.csv   one row per account
    revenue_data.csv        one row per account per month (gross reagent revenue, discounts)
    instrument_costs.csv    one row per placed instrument (purchase cost, placement date)
    service_costs.csv       one row per account per month (maintenance, repair)

Run:  python generate_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
FISCAL_YEAR = 2025
DATA_DIR = Path(__file__).parent / "data"

REGIONS = ["West", "Southwest", "Midwest", "Northeast", "Southeast"]
CUSTOMER_TYPES = [
    "Academic Medical Center",
    "Community Hospital",
    "Reference Laboratory",
    "Independent Pathology Lab",
]

# Fictional instrument catalogue: (model name, list price range in $)
INSTRUMENTS = {
    "Stainer S-200": (180_000, 220_000),
    "Stainer S-400": (280_000, 340_000),
    "Analyzer A-900": (450_000, 550_000),
}

# Fictional account names (invented; any resemblance is coincidental)
ACCOUNT_NAMES = [
    "Saguaro Valley Medical Center", "Redrock Regional Hospital", "Pinecrest University Health",
    "Lakeshore Pathology Partners", "Copper Mesa Diagnostics", "Bluewater Community Hospital",
    "Northfield Reference Labs", "Granite Peak Health System", "Silver Creek Medical Center",
    "Harborview Clinical Laboratory", "Prairie Plains Hospital", "Summit Academic Medical",
    "Cedar Hollow Pathology", "Ironwood Regional Medical", "Meadowbrook Community Health",
    "Atlas Reference Diagnostics", "Riverbend University Hospital", "Juniper Ridge Lab Services",
    "Oakmont General Hospital", "Coastal Precision Pathology", "Highland Medical Center",
    "Sterling Diagnostic Labs", "Willow Park Hospital", "Canyon State Health Sciences",
    "Evergreen Pathology Group", "Beacon Hill Medical Center", "Mesa Verde Clinical Lab",
    "Starlight Children's Hospital", "Keystone Regional Laboratory", "Driftwood Community Hospital",
]

# Archetypes drive the variety of financial profiles.
#   rev       : annual gross reagent revenue range ($)
#   disc      : discount rate range (share of gross)
#   inst      : (instrument models to place)
#   maint     : monthly maintenance $ per instrument range
#   repair_p  : monthly probability of a repair event per instrument
#   repair    : repair event $ range
ARCHETYPES = {
    "Star performer": dict(rev=(1_600_000, 2_300_000), disc=(0.05, 0.10),
                           inst=["Stainer S-200", "Stainer S-400", "Analyzer A-900"], maint=(2_500, 3_500),
                           repair_p=0.06, repair=(2_000, 6_000)),
    "Discount-heavy": dict(rev=(1_600_000, 2_200_000), disc=(0.32, 0.40),
                           inst=["Stainer S-400", "Stainer S-400", "Analyzer A-900", "Analyzer A-900"],
                           maint=(2_500, 3_500), repair_p=0.08, repair=(2_000, 6_000)),
    "Service-heavy": dict(rev=(1_200_000, 1_600_000), disc=(0.10, 0.15),
                          inst=["Stainer S-200", "Stainer S-400"], maint=(7_000, 9_000),
                          repair_p=0.60, repair=(10_000, 25_000)),
    "Capital-heavy": dict(rev=(900_000, 1_300_000), disc=(0.10, 0.15),
                          inst=["Analyzer A-900", "Analyzer A-900", "Stainer S-400", "Stainer S-400"],
                          maint=(2_500, 3_500), repair_p=0.08, repair=(2_000, 6_000)),
    "Steady mid-size": dict(rev=(700_000, 1_100_000), disc=(0.08, 0.14),
                            inst=["Stainer S-200", "Stainer S-400"], maint=(2_500, 3_500),
                            repair_p=0.07, repair=(1_500, 5_000)),
    "Small / underutilized": dict(rev=(250_000, 450_000), disc=(0.12, 0.20),
                                  inst=["Stainer S-200", "Stainer S-400"], maint=(2_500, 3_500),
                                  repair_p=0.10, repair=(2_000, 7_000)),
}
# 30 accounts: counts per archetype
ARCHETYPE_MIX = (["Star performer"] * 7 + ["Discount-heavy"] * 5 + ["Service-heavy"] * 4
                 + ["Capital-heavy"] * 4 + ["Steady mid-size"] * 6 + ["Small / underutilized"] * 4)

TYPE_BY_ARCHETYPE = {
    "Star performer": ["Academic Medical Center", "Reference Laboratory"],
    "Discount-heavy": ["Academic Medical Center", "Reference Laboratory", "Community Hospital"],
    "Service-heavy": ["Community Hospital", "Independent Pathology Lab"],
    "Capital-heavy": ["Academic Medical Center", "Reference Laboratory"],
    "Steady mid-size": ["Community Hospital", "Independent Pathology Lab"],
    "Small / underutilized": ["Community Hospital", "Independent Pathology Lab"],
}


def _random_placement(rng: np.random.Generator, new_account: bool) -> pd.Timestamp:
    """Placement on the 1st of a month. New accounts were placed during FY2025."""
    if new_account:
        return pd.Timestamp(FISCAL_YEAR, int(rng.integers(2, 7)), 1)
    year = int(rng.integers(2021, FISCAL_YEAR))  # 2021-2024
    return pd.Timestamp(year, int(rng.integers(1, 13)), 1)


def generate(seed: int = SEED, out_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    months = pd.date_range(f"{FISCAL_YEAR}-01-01", periods=12, freq="MS")
    seasonality = 1 + 0.06 * np.sin(np.arange(12) / 12 * 2 * np.pi - 1.2)  # mild seasonality

    archetypes = list(ARCHETYPE_MIX)
    rng.shuffle(archetypes)
    # Two accounts were onboarded during FY2025 (ramping revenue, partial-year instruments)
    new_idx = set(rng.choice([i for i, a in enumerate(archetypes) if a == "Steady mid-size"],
                             size=2, replace=False).tolist())

    accounts, revenue, instruments, service = [], [], [], []
    inst_counter = 1
    for i, (name, arch) in enumerate(zip(ACCOUNT_NAMES, archetypes)):
        p = ARCHETYPES[arch]
        acct_id = f"ACC-{i + 1:03d}"
        is_new = i in new_idx
        region = REGIONS[int(rng.integers(0, len(REGIONS)))]
        ctype = str(rng.choice(TYPE_BY_ARCHETYPE[arch]))

        # --- instruments ---
        first_placement = None
        acct_instruments = []
        for model in p["inst"]:
            lo, hi = INSTRUMENTS[model]
            placed = _random_placement(rng, is_new)
            first_placement = placed if first_placement is None else min(first_placement, placed)
            cost = round(float(rng.uniform(lo, hi)), -2)
            acct_instruments.append(dict(instrument_id=f"INS-{inst_counter:03d}", account_id=acct_id,
                                         instrument_model=model, placement_date=placed.date(),
                                         purchase_cost=cost))
            inst_counter += 1
        instruments += acct_instruments

        accounts.append(dict(account_id=acct_id, account_name=name, customer_type=ctype, region=region,
                             contract_start=first_placement.date(), instrument_count=len(acct_instruments)))

        # --- monthly revenue & discounts ---
        annual = rng.uniform(*p["rev"])
        disc_rate = rng.uniform(*p["disc"])
        growth = rng.uniform(-0.01, 0.015)  # monthly trend
        for m_idx, month in enumerate(months):
            active = month >= first_placement
            if not active:
                gross = 0.0
            else:
                ramp = 1.0
                if is_new:  # new accounts ramp to run-rate over ~4 months
                    months_live = (month.year - first_placement.year) * 12 + month.month - first_placement.month
                    ramp = min(1.0, 0.35 + 0.18 * months_live)
                noise = rng.normal(1, 0.05)
                gross = annual / 12 * seasonality[m_idx] * (1 + growth) ** m_idx * ramp * noise
            gross = round(max(gross, 0), 2)
            disc = round(gross * float(np.clip(rng.normal(disc_rate, 0.01), 0, 0.5)), 2)
            revenue.append(dict(account_id=acct_id, month=month.date(),
                                gross_reagent_revenue=gross, discount_amount=disc))

            # --- monthly service costs (only for instruments in service) ---
            maint = repair = 0.0
            for ins in acct_instruments:
                if pd.Timestamp(ins["placement_date"]) <= month:
                    maint += rng.uniform(*p["maint"])
                    if rng.random() < p["repair_p"]:
                        repair += rng.uniform(*p["repair"])
            service.append(dict(account_id=acct_id, month=month.date(),
                                maintenance_expense=round(maint, 2), repair_expense=round(repair, 2)))

    frames = {
        "customer_accounts": pd.DataFrame(accounts),
        "revenue_data": pd.DataFrame(revenue),
        "instrument_costs": pd.DataFrame(instruments),
        "service_costs": pd.DataFrame(service),
    }
    for fname, df in frames.items():
        df.to_csv(out_dir / f"{fname}.csv", index=False)
    return frames


if __name__ == "__main__":
    f = generate()
    for k, v in f.items():
        print(f"{k:<18} {len(v):>4} rows  -> data/{k}.csv")
