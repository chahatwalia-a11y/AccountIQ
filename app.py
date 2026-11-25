"""
AccountIQ - Customer Account Profitability Intelligence (Streamlit dashboard)

    streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculations import (DEFAULT_USEFUL_LIFE_YEARS, LIMITATIONS, MANAGEMENT_ACTIONS, Thresholds,
                          build_model, identify_opportunities, load_data)

# ----------------------------------------------------------------------------- look & feel
NAVY, BLUE, LIGHT, PALE = "#1B2A4A", "#4A6FA5", "#9DB4D3", "#F4F7FB"
RED, GRAY, GRID = "#B5473A", "#8A94A6", "#E6EBF2"
# Paste your GitHub repository URL here after creating it, e.g. "https://github.com/yourname/AccountIQ".
GITHUB_URL = ""

DISCLAIMER = "Illustrative prototype using synthetic data. Not actual Roche or customer financial information."

st.set_page_config(page_title="AccountIQ | Account Profitability", layout="wide")

st.markdown(f"""
<style>
  html, body, [class*="css"] {{ font-family: "Inter", "Helvetica Neue", Arial, sans-serif; }}
  .block-container {{ padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1500px; }}
  h1, h2, h3, h4 {{ color: {NAVY}; font-weight: 600; letter-spacing: -0.01em; }}
  .aiq-header {{ display:flex; align-items:baseline; gap:14px; border-bottom: 2px solid {NAVY};
                 padding-bottom: 10px; margin-bottom: 8px; }}
  .aiq-logo {{ font-size: 30px; font-weight: 700; color: {NAVY}; letter-spacing: -0.02em; }}
  .aiq-logo span {{ color: {BLUE}; }}
  .aiq-sub {{ font-size: 15px; color: {GRAY}; }}
  .aiq-disclaimer {{ background: {PALE}; border-left: 3px solid {BLUE}; color: #4b5568; font-size: 12.5px;
                     padding: 7px 12px; margin: 6px 0 18px 0; border-radius: 2px; }}
  .kpi {{ background:#fff; border:1px solid {GRID}; border-top:3px solid {NAVY}; border-radius:6px;
          padding:14px 16px 12px 16px; min-height: 124px; }}
  .kpi.alt {{ border-top-color: {BLUE}; }}
  .kpi.warn {{ border-top-color: {RED}; }}
  .kpi-label {{ font-size:11px; min-height: 30px; text-transform:uppercase; letter-spacing:.06em; color:{GRAY}; font-weight:600; }}
  .kpi-value {{ font-size:26px; font-weight:650; color:{NAVY}; margin-top:4px; line-height:1.15;
                font-variant-numeric: tabular-nums; }}
  .kpi-foot {{ font-size:12px; color:#6b7588; margin-top:3px; }}
  .section {{ font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:{BLUE}; font-weight:700;
              margin: 22px 0 6px 0; }}
  .finding-card {{ border:1px solid {GRID}; border-left:4px solid {RED}; border-radius:6px; padding:12px 16px;
                   margin-bottom:10px; background:#fff; }}
  .finding-title {{ font-weight:650; color:{NAVY}; font-size:15px; }}
  .finding-meta {{ color:#6b7588; font-size:12.5px; margin-top:2px; }}
  .pill {{ display:inline-block; background:{PALE}; color:{NAVY}; border:1px solid {GRID}; border-radius:10px;
           padding:1px 9px; font-size:12px; margin-right:6px; }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {GRID}; }}
  .stTabs [data-baseweb="tab"] {{ font-weight:600; color:{GRAY}; padding: 8px 16px; }}
  .stTabs [aria-selected="true"] {{ color:{NAVY} !important; }}
  section[data-testid="stSidebar"] {{ background: {PALE}; border-right: 1px solid {GRID}; }}
  .how {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin: 0 0 14px 0; }}
  .how div {{ border:1px solid {GRID}; border-radius:6px; padding:10px 14px; font-size:13.5px; color:#4b5568; background:#fff; }}
  .how b {{ display:block; color:{NAVY}; font-size:14px; margin-bottom:2px; }}
  .intro {{ font-size:15px; color:#3b4658; margin: 2px 0 12px 0; max-width: 980px; }}
  @media (max-width: 800px) {{ .how {{ grid-template-columns: 1fr; }} }}
  #MainMenu, footer {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- formatting helpers
def money(x: float, decimals: int | None = None) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    sign = "-" if x < 0 else ""
    v = abs(x)
    if v >= 1e6:
        return f"{sign}${v / 1e6:,.{2 if decimals is None else decimals}f}M"
    if v >= 1e3:
        return f"{sign}${v / 1e3:,.{0 if decimals is None else decimals}f}K"
    return f"{sign}${v:,.0f}"


def pct(x: float, d: int = 1) -> str:
    return "n/a" if x is None or np.isnan(x) else f"{x:.{d}%}"


def kpi(col, label: str, value: str, foot: str = "", variant: str = ""):
    col.markdown(f'<div class="kpi {variant}"><div class="kpi-label">{label}</div>'
                 f'<div class="kpi-value">{value}</div><div class="kpi-foot">{foot}</div></div>',
                 unsafe_allow_html=True)


def section(text: str):
    st.markdown(f'<div class="section">{text}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 360, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=10, t=46 if title else 16, b=10),
        title=dict(text=title, font=dict(size=15, color=NAVY), x=0, xanchor="left") if title else None,
        font=dict(family="Inter, Helvetica Neue, Arial, sans-serif", size=12, color="#3b4658"),
        paper_bgcolor="white", plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=GRID),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=GRAY))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=GRAY))
    return fig


def waterfall(gross, disc, inst, svc, height=360, title=None, compact=False) -> go.Figure:
    net = gross - disc
    profit = net - inst - svc
    fig = go.Figure(go.Waterfall(
        x=(["Gross", "Discounts", "Net", "Instrument", "Service", "Profit"] if compact else
           ["Gross reagent<br>revenue", "Discounts", "Net revenue", "Allocated<br>instrument cost",
            "Service costs", "Contribution<br>profit"]),
        measure=["absolute", "relative", "total", "relative", "relative", "total"],
        y=[gross, -disc, 0, -inst, -svc, 0],
        text=[money(gross), money(-disc), money(net), money(-inst), money(-svc), money(profit)],
        textposition="outside", textfont=dict(size=12, color=NAVY),
        connector=dict(line=dict(color=GRID, width=1)),
        increasing=dict(marker=dict(color=NAVY)),
        decreasing=dict(marker=dict(color="#C98A80")),
        totals=dict(marker=dict(color=BLUE)),
        hovertemplate="%{x}: %{text}<extra></extra>",
    ))
    fig = style_fig(fig, height, title)
    fig.update_yaxes(tickprefix="$", tickformat="~s", range=[0, gross * 1.15])
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=0, tickfont=dict(size=11, color="#3b4658"))
    return fig


# ----------------------------------------------------------------------------- data
@st.cache_data(show_spinner=False)
def get_model(life: float, hr: float, lm: float, dr: float, sr: float, ir: float):
    t = Thresholds(hr, lm, dr, sr, ir)
    res = build_model(life, t, load_data())
    return res.accounts, res.monthly_by_account, res.instruments, res.findings


with st.sidebar:
    st.markdown(f"<div style='font-size:20px;font-weight:700;color:{NAVY}'>Account<span style='color:{BLUE}'>IQ</span></div>",
                unsafe_allow_html=True)
    st.caption("FY2025, 30 fictional accounts")
    st.markdown("#### Filters")
    base = load_data()["accounts"]
    regions = sorted(base["region"].unique())
    types = sorted(base["customer_type"].unique())
    sel_regions = st.multiselect("Region", regions, default=regions)
    sel_types = st.multiselect("Customer type", types, default=types)
    st.markdown("#### Model assumptions")
    life = st.slider("Instrument useful life (years)", 3.0, 10.0, float(DEFAULT_USEFUL_LIFE_YEARS), 0.5,
                     help="Straight-line allocation period for instrument purchase cost.")
    d = Thresholds()
    with st.expander("Opportunity thresholds"):
        lm = st.slider("Low-margin threshold", 0.30, 0.90, d.low_margin, 0.05, format="%.2f")
        hr = st.slider("High-revenue percentile", 0.30, 0.90, d.high_revenue_percentile, 0.05, format="%.2f")
        dr = st.slider("Excessive discount (% of gross)", 0.05, 0.40, d.excessive_discount_rate, 0.01, format="%.2f")
        sr = st.slider("High service cost (% of net rev.)", 0.05, 0.40, d.high_service_ratio, 0.01, format="%.2f")
        ir = st.slider("High instrument cost (% of net rev.)", 0.05, 0.50, d.high_instrument_ratio, 0.01, format="%.2f")
    st.markdown("#### Project files")
    xlsx = Path(__file__).parent / "excel" / "AccountIQ_Financial_Model.xlsx"
    if xlsx.exists():
        st.download_button("Download Excel model", xlsx.read_bytes(), "AccountIQ_Financial_Model.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    if GITHUB_URL:
        st.link_button("View code on GitHub", GITHUB_URL, width="stretch")
    st.caption("Built in Python (Pandas), SQL and Excel. The three versions reconcile to the cent.")
    st.markdown("---")
    st.caption(DISCLAIMER)

accounts_all, mba_all, inst_all, findings_all = get_model(life, hr, lm, dr, sr, ir)
thr = Thresholds(hr, lm, dr, sr, ir)

# header
st.markdown(f"""<div class="aiq-header"><div class="aiq-logo">Account<span>IQ</span></div>
<div class="aiq-sub">Customer Account Profitability Intelligence</div></div>
<div class="aiq-disclaimer">{DISCLAIMER}</div>
<div class="intro">A diagnostics company sells reagents to hospitals and labs, places instruments at their sites and services
them. Revenue alone hides the cost of that support. AccountIQ calculates each account's contribution profit and flags
where margin is leaking.</div>
<div class="how">
  <div><b>1. Review the portfolio</b>Start on Executive Overview for totals, the profit bridge and the revenue vs margin map.</div>
  <div><b>2. Open an account</b>Use Account Analysis to see one account's P&amp;L, issues found and recommended actions.</div>
  <div><b>3. Change the assumptions</b>Use the sidebar to filter accounts or change instrument useful life. Everything recalculates.</div>
</div>""", unsafe_allow_html=True)

if not sel_regions or not sel_types:
    st.warning("Select at least one region and one customer type.")
    st.stop()

mask = accounts_all["region"].isin(sel_regions) & accounts_all["customer_type"].isin(sel_types)
A = accounts_all[mask].copy()
if A.empty:
    st.info("No accounts match the current filters.")
    st.stop()
ids = set(A["account_id"])
M = mba_all[mba_all["account_id"].isin(ids)]
F = findings_all[findings_all["account_id"].isin(ids)]
monthly = M.groupby("month")[["gross_reagent_revenue", "net_revenue", "allocated_instrument_cost",
                              "service_costs", "contribution_profit"]].sum().reset_index()

tab_exec, tab_acct, tab_opp, tab_method = st.tabs(
    ["Executive Overview", "Account Analysis", "Margin Opportunities", "Methodology"])

# ============================================================================= EXECUTIVE OVERVIEW
with tab_exec:
    net, prof = A["net_revenue"].sum(), A["contribution_profit"].sum()
    filtered_note = "" if len(A) == len(accounts_all) else f" (filtered: {len(A)} of {len(accounts_all)})"
    c = st.columns(6)
    kpi(c[0], "Total net revenue", money(net), f"Gross {money(A['gross_reagent_revenue'].sum())}")
    kpi(c[1], "Contribution profit", money(prof), f"After instrument & service", "alt")
    kpi(c[2], "Avg contribution margin", pct(A["contribution_margin"].mean()),
        f"Weighted: {pct(prof / net if net else np.nan)}")
    kpi(c[3], "Instrument investment", money(A["instrument_investment"].sum()),
        f"FY allocation {money(A['allocated_instrument_cost'].sum())}", "alt")
    kpi(c[4], "Service expenses", money(A["service_costs"].sum()),
        f"Repairs {money(A['repair_expense'].sum())}")
    kpi(c[5], "Customer accounts", f"{len(A)}", f"{F['account_id'].nunique()} with margin flags{filtered_note}",
        "warn" if F["account_id"].nunique() else "alt")

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(waterfall(A["gross_reagent_revenue"].sum(), A["discount_amount"].sum(),
                                  A["allocated_instrument_cost"].sum(), A["service_costs"].sum(),
                                  380, "Revenue versus costs: FY P&L bridge"),
                        width="stretch", config={"displayModeBar": False})
    with right:
        fig = go.Figure()
        fig.add_scatter(x=monthly["month"], y=monthly["net_revenue"], name="Net revenue", mode="lines+markers",
                        line=dict(color=NAVY, width=2.5), marker=dict(size=7),
                        hovertemplate="%{x|%b %Y}<br>Net revenue: $%{y:,.0f}<extra></extra>")
        fig.add_scatter(x=monthly["month"], y=monthly["contribution_profit"], name="Contribution profit",
                        mode="lines+markers", line=dict(color=LIGHT, width=2.5), marker=dict(size=7),
                        hovertemplate="%{x|%b %Y}<br>Contribution: $%{y:,.0f}<extra></extra>")
        fig.add_scatter(x=monthly["month"], y=monthly["gross_reagent_revenue"], name="Gross revenue",
                        mode="lines", line=dict(color=GRAY, width=1.5, dash="dot"),
                        hovertemplate="%{x|%b %Y}<br>Gross revenue: $%{y:,.0f}<extra></extra>")
        style_fig(fig, 380, "Monthly revenue trend")
        fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
        fig.update_xaxes(tickformat="%b", dtick="M1")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Profitability map
    left, right = st.columns([1.05, 0.95])
    with left:
        fig = go.Figure()
        flagged = A["account_id"].isin(F["account_id"])
        for is_flag, color, name in [(False, NAVY, "No flags"), (True, RED, "Flagged")]:
            sub = A[flagged == is_flag]
            fig.add_scatter(
                x=sub["net_revenue"], y=sub["contribution_margin"], mode="markers", name=name,
                marker=dict(size=np.sqrt(sub["instrument_investment"]) / 42, color=color, opacity=0.75,
                            line=dict(color="white", width=1.5)),
                customdata=np.stack([sub["account_name"], sub["instrument_investment"]], axis=-1),
                hovertemplate="<b>%{customdata[0]}</b><br>Net revenue: $%{x:,.0f}<br>Margin: %{y:.1%}"
                              "<br>Instrument investment: $%{customdata[1]:,.0f}<extra></extra>")
        cut = accounts_all["net_revenue"].quantile(thr.high_revenue_percentile)
        fig.add_hline(y=thr.low_margin, line=dict(color=GRAY, dash="dash", width=1),
                      annotation_text=f"Margin target {thr.low_margin:.0%}", annotation_font_color=GRAY,
                      annotation_position="bottom right")
        fig.add_vline(x=cut, line=dict(color=GRAY, dash="dash", width=1),
                      annotation_text="High-revenue cut-off", annotation_font_color=GRAY,
                      annotation_position="top left")
        style_fig(fig, 430, "Profitability map: revenue vs margin")
        fig.update_xaxes(tickprefix="$", tickformat="~s", title="Net revenue  (bubble size = instrument investment)", showgrid=True, gridcolor=GRID)
        fig.update_yaxes(tickformat=".0%", title="Contribution margin")
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="right", x=0.99,
                                      bgcolor="rgba(255,255,255,0.85)"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right:
        s = A.sort_values("contribution_margin")
        colors = [RED if m < thr.low_margin else NAVY for m in s["contribution_margin"]]
        fig = go.Figure(go.Bar(x=s["contribution_margin"], y=s["account_name"], orientation="h",
                               marker=dict(color=colors), text=[pct(v) for v in s["contribution_margin"]],
                               textposition="outside", textfont=dict(size=10, color="#3b4658"),
                               hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
        style_fig(fig, max(400, 18 * len(s) + 60), "Contribution margin by account")
        fig.update_xaxes(tickformat=".0%", range=[min(0, s["contribution_margin"].min() * 1.1), 1.0],
                         showgrid=True, gridcolor=GRID)
        fig.update_yaxes(tickfont=dict(size=10.5, color="#3b4658"), gridcolor="rgba(0,0,0,0)")
        fig.add_vline(x=thr.low_margin, line=dict(color=GRAY, dash="dash", width=1))
        fig.update_layout(bargap=0.3)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    left, right = st.columns(2)
    with left:
        top = A.nlargest(10, "contribution_profit").iloc[::-1]
        fig = go.Figure(go.Bar(x=top["contribution_profit"], y=top["account_name"], orientation="h",
                               marker_color=NAVY, text=[money(v) for v in top["contribution_profit"]],
                               textposition="outside", textfont=dict(size=11),
                               customdata=top["contribution_margin"],
                               hovertemplate="%{y}<br>Contribution: $%{x:,.0f}<br>Margin: %{customdata:.1%}<extra></extra>"))
        style_fig(fig, 400, "Top 10 most profitable customers")
        fig.update_xaxes(tickprefix="$", tickformat="~s", range=[0, top["contribution_profit"].max() * 1.18])
        fig.update_layout(bargap=0.35)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right:
        bot = A.nsmallest(10, "contribution_margin").iloc[::-1]
        fig = go.Figure(go.Bar(x=bot["contribution_margin"], y=bot["account_name"], orientation="h",
                               marker_color="#C98A80", text=[pct(v) for v in bot["contribution_margin"]],
                               textposition="outside", textfont=dict(size=11),
                               customdata=bot["net_revenue"],
                               hovertemplate="%{y}<br>Margin: %{x:.1%}<br>Net revenue: $%{customdata:,.0f}<extra></extra>"))
        style_fig(fig, 400, "Bottom 10 lowest-margin customers")
        fig.update_xaxes(tickformat=".0%", range=[min(0, bot["contribution_margin"].min() * 1.2),
                                                 max(1.0, bot["contribution_margin"].max() * 1.2)])
        fig.update_layout(bargap=0.35)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with st.expander("Account profitability table"):
        tbl = A[["profit_rank", "account_name", "region", "customer_type", "gross_reagent_revenue", "discount_amount",
                 "net_revenue", "allocated_instrument_cost", "service_costs", "contribution_profit",
                 "contribution_margin"]].rename(columns={
            "profit_rank": "Rank", "account_name": "Account", "region": "Region", "customer_type": "Type",
            "gross_reagent_revenue": "Gross revenue", "discount_amount": "Discounts", "net_revenue": "Net revenue",
            "allocated_instrument_cost": "Instrument cost", "service_costs": "Service costs",
            "contribution_profit": "Contribution profit", "contribution_margin": "Margin"})
        money_cols = ["Gross revenue", "Discounts", "Net revenue", "Instrument cost", "Service costs", "Contribution profit"]
        st.dataframe(tbl.style.format({**{c: "${:,.0f}" for c in money_cols}, "Margin": "{:.1%}"}),
                     width="stretch", hide_index=True)
        st.download_button("Download CSV", tbl.to_csv(index=False), "accountiq_profitability.csv", "text/csv")

# ============================================================================= ACCOUNT ANALYSIS
with tab_acct:
    options = A.sort_values("account_name")
    labels = {r.account_id: f"{r.account_name} ({r.account_id})" for r in options.itertuples()}
    flagged_here = A[A["account_id"].isin(F["account_id"])]
    default_id = (flagged_here.nlargest(1, "net_revenue") if len(flagged_here) else A.head(1))["account_id"].iloc[0]
    pick = st.selectbox("Select a customer account", list(labels), format_func=labels.get,
                        index=list(labels).index(default_id))
    r = accounts_all.set_index("account_id").loc[pick]
    port_margin = accounts_all["contribution_profit"].sum() / accounts_all["net_revenue"].sum()

    st.markdown(f"<span class='pill'>{r.customer_type}</span><span class='pill'>{r.region}</span>"
                f"<span class='pill'>Profit rank #{r.profit_rank} of {len(accounts_all)}</span>"
                f"<span class='pill'>{int(r.instrument_count)} instruments</span>"
                f"<span class='pill'>Customer since {pd.Timestamp(r.contract_start):%b %Y}</span>",
                unsafe_allow_html=True)
    st.write("")
    c = st.columns(4)
    kpi(c[0], "Gross reagent revenue", money(r.gross_reagent_revenue), "FY2025")
    kpi(c[1], "Discounts", money(r.discount_amount), f"{pct(r.discount_rate)} of gross",
        "warn" if r.discount_rate > thr.excessive_discount_rate else "alt")
    kpi(c[2], "Net revenue", money(r.net_revenue), "Gross less discounts")
    kpi(c[3], "Instrument cost (allocated)", money(r.allocated_instrument_cost),
        f"{money(r.instrument_investment)} invested, {pct(r.instrument_cost_ratio)} of net rev.",
        "warn" if r.instrument_cost_ratio > thr.high_instrument_ratio else "alt")
    st.write("")
    c = st.columns(4)
    kpi(c[0], "Service costs", money(r.service_costs),
        f"Maintenance {money(r.maintenance_expense)}, repair {money(r.repair_expense)}",
        "warn" if r.service_cost_ratio > thr.high_service_ratio else "alt")
    kpi(c[1], "Contribution profit", money(r.contribution_profit), f"Rank #{r.profit_rank}",
        "warn" if r.contribution_profit < 0 else "")
    delta = r.contribution_margin - port_margin
    kpi(c[2], "Contribution margin", pct(r.contribution_margin),
        f"{'+' if delta >= 0 else ''}{delta * 100:.1f} pts vs portfolio {pct(port_margin)}",
        "warn" if r.contribution_margin < thr.low_margin else "")
    acct_f = findings_all[findings_all["account_id"] == pick]
    kpi(c[3], "Margin flags", str(len(acct_f)), ", ".join(acct_f["finding"]) or "None", "warn" if len(acct_f) else "alt")

    left, right = st.columns([1.15, 0.85])
    with left:
        m = mba_all[mba_all["account_id"] == pick].sort_values("month")
        fig = go.Figure()
        fig.add_bar(x=m["month"], y=m["net_revenue"], name="Net revenue", marker_color=NAVY,
                    hovertemplate="%{x|%b}: $%{y:,.0f}<extra>Net revenue</extra>")
        fig.add_bar(x=m["month"], y=m["discount_amount"], name="Discounts", marker_color=LIGHT,
                    hovertemplate="%{x|%b}: $%{y:,.0f}<extra>Discounts</extra>")
        fig.add_scatter(x=m["month"], y=m["contribution_profit"], name="Contribution profit", mode="lines+markers",
                        line=dict(color="#C98A80", width=2.5), marker=dict(size=7),
                        hovertemplate="%{x|%b}: $%{y:,.0f}<extra>Contribution</extra>")
        style_fig(fig, 380, "Monthly revenue (stacked bar = gross revenue)")
        fig.update_layout(barmode="stack", bargap=0.35)
        fig.update_yaxes(tickprefix="$", tickformat="~s")
        fig.update_xaxes(tickformat="%b", dtick="M1")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right:
        st.plotly_chart(waterfall(r.gross_reagent_revenue, r.discount_amount, r.allocated_instrument_cost,
                                  r.service_costs, 380, "Account P&L bridge", compact=True),
                        width="stretch", config={"displayModeBar": False})

    left, right = st.columns([1, 1])
    with left:
        section("Installed instruments")
        ii = inst_all[inst_all["account_id"] == pick][["instrument_id", "instrument_model", "placement_date",
                                                        "purchase_cost", "months_allocated_in_fy",
                                                        "allocated_instrument_cost"]]
        ii = ii.rename(columns={"instrument_id": "ID", "instrument_model": "Model", "placement_date": "Placed",
                                "purchase_cost": "Purchase cost", "months_allocated_in_fy": "Months in FY",
                                "allocated_instrument_cost": "FY allocation"})
        st.dataframe(ii.style.format({"Placed": lambda d: f"{d:%b %Y}", "Purchase cost": "${:,.0f}",
                                      "FY allocation": "${:,.0f}"}), width="stretch", hide_index=True)
    with right:
        section("Findings & recommended actions")
        if acct_f.empty:
            st.success("No margin flags at the current thresholds.")
        for f in acct_f.itertuples():
            acts = "".join(f"<li>{a}</li>" for a in MANAGEMENT_ACTIONS[f.finding])
            st.markdown(f"<div class='finding-card'><div class='finding-title'>{f.finding}</div>"
                        f"<div class='finding-meta'>{f.detail}. Profit gap: {money(f.gap_to_threshold)}</div>"
                        f"<ul style='margin:6px 0 0 0;font-size:13.5px'>{acts}</ul></div>", unsafe_allow_html=True)

# ============================================================================= MARGIN OPPORTUNITIES
with tab_opp:
    st.markdown(f"Rules run automatically against every account. Thresholds can be tuned in the sidebar. "
                f"Profit gap is the profit recovered if an account moved exactly to the threshold. "
                f"Gaps overlap across categories, so they are not added together.")
    order = list(MANAGEMENT_ACTIONS)
    rule_text = {
        "High revenue, low margin": f"Net revenue in top {1 - thr.high_revenue_percentile:.0%} and margin < {thr.low_margin:.0%}",
        "Excessive discounting": f"Discounts > {thr.excessive_discount_rate:.0%} of gross revenue",
        "High service costs": f"Service costs > {thr.high_service_ratio:.0%} of net revenue",
        "High instrument cost relative to revenue": f"Allocated instrument cost > {thr.high_instrument_ratio:.0%} of net revenue",
    }
    c = st.columns(4)
    for col, name in zip(c, order):
        sub = F[F["finding"] == name]
        kpi(col, name, f"{len(sub)} accounts", f"Gap to threshold {money(sub['gap_to_threshold'].sum())}",
            "warn" if len(sub) else "alt")

    for name in order:
        sub = F[F["finding"] == name].sort_values("gap_to_threshold", ascending=False)
        section(f"{name} ({len(sub)})")
        st.caption(f"Rule: {rule_text[name]}")
        if sub.empty:
            st.info("No accounts flagged at the current thresholds.")
            continue
        left, right = st.columns([2.2, 1])
        with left:
            show = sub[["account_name", "gap_to_threshold", "contribution_margin", "detail"]].rename(columns={
                "account_name": "Account", "detail": "Why flagged",
                "contribution_margin": "Margin", "gap_to_threshold": "Profit gap"})
            st.dataframe(show.style.format({"Margin": "{:.1%}", "Profit gap": "${:,.0f}"}),
                         width="stretch", hide_index=True, height=36 * (len(show) + 1) + 4,
                         column_config={"Account": st.column_config.TextColumn(width="medium"),
                                        "Profit gap": st.column_config.Column(width="small"),
                                        "Margin": st.column_config.Column(width="small"),
                                        "Why flagged": st.column_config.TextColumn(width="large")})
        with right:
            acts = "".join(f"<li>{a}</li>" for a in MANAGEMENT_ACTIONS[name])
            st.markdown(f"<div class='finding-card' style='border-left-color:{BLUE}'>"
                        f"<div class='finding-title'>Possible management actions</div>"
                        f"<ul style='margin:6px 0 0 0;font-size:13.5px'>{acts}</ul></div>", unsafe_allow_html=True)

# ============================================================================= METHODOLOGY
with tab_method:
    left, right = st.columns(2)
    with left:
        section("Calculations")
        st.markdown(f"""
| Metric | Definition |
|---|---|
| Net Revenue | Gross Reagent Revenue - Discounts |
| Allocated Instrument Cost | Purchase Cost / Useful Life ({life:g} yrs), pro-rated for months in service during FY2025 |
| Service Costs | Maintenance + Repair Expense |
| Contribution Profit | Net Revenue - Allocated Instrument Cost - Service Costs |
| Contribution Margin | Contribution Profit / Net Revenue |
""")
        section("No double counting")
        st.markdown("""
- Discounts reduce revenue once. They are not also deducted as a cost.
- Instrument purchase cost reaches profit only through the annual allocation. Total investment appears as capital, not as an expense.
- Maintenance and repair are operating expenses, separate from the instrument allocation.
- The model reconciles annual totals with the monthly build, and the SQL and Excel versions match the Python engine to the cent.
""")
    with right:
        section("Limitations of the simplified allocation")
        st.markdown("\n".join(f"- {x}" for x in LIMITATIONS))
        section("Data")
        st.markdown("30 fictional hospital and laboratory accounts, 12 months (January to December 2025), "
                    "with a fictional instrument catalogue. All names and numbers are synthetic.")
    st.caption(DISCLAIMER)
