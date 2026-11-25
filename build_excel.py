"""
AccountIQ - Excel financial model builder.

    python build_excel.py

Writes excel/AccountIQ_Financial_Model.xlsx. Raw data is written as values (blue inputs);
every calculation (net revenue, allocations, service totals, profit, margin, ranks, flags,
dashboard KPIs, monthly trend, top/bottom 10) is a live Excel formula driven by the
assumption cells on the Read Me sheet (yellow).
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

from calculations import (DEFAULT_USEFUL_LIFE_YEARS, FISCAL_YEAR, LIMITATIONS, MANAGEMENT_ACTIONS,
                          Thresholds, build_model, load_data)

OUT = Path(__file__).parent / "excel" / "AccountIQ_Financial_Model.xlsx"

NAVY, MUTED, LIGHT, PALE = "1B2A4A", "4A6FA5", "DCE6F2", "F4F7FB"
FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_LINK = Font(name=FONT, size=10, color="008000")
F_HDR = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_BOLD = Font(name=FONT, size=10, bold=True)
F_TITLE = Font(name=FONT, size=16, bold=True, color=NAVY)
F_SUB = Font(name=FONT, size=11, bold=True, color=MUTED)
F_NOTE = Font(name=FONT, size=9, italic=True, color="666666")
FILL_HDR = PatternFill("solid", fgColor=NAVY)
FILL_SEC = PatternFill("solid", fgColor=LIGHT)
FILL_YELLOW = PatternFill("solid", fgColor="FFFF00")
THIN = Side(style="thin", color="C8D3E3")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)

CUR = '$#,##0;($#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
DATE = "mmm yyyy"
DATE_D = "yyyy-mm-dd"


def header(ws, row: int, labels: list[str], widths: list[int] | None = None):
    for c, lab in enumerate(labels, 1):
        cell = ws.cell(row=row, column=c, value=lab)
        cell.font, cell.fill, cell.border = F_HDR, FILL_HDR, BOX
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30
    if widths:
        for c, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(c)].width = w


def put(ws, row, col, value, font=F_BASE, fmt=None, fill=None, bold=False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name=FONT, size=font.size, bold=bold or font.bold, color=font.color, italic=font.italic)
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    return cell


def add_name(wb, name, ref):
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def build(useful_life: float = DEFAULT_USEFUL_LIFE_YEARS, out: Path = OUT) -> Path:
    t = Thresholds()
    d = load_data()
    model = build_model(useful_life, t, d)
    order = model.accounts["account_id"].tolist()           # profit-rank order for presentation
    acc = d["accounts"].set_index("account_id").loc[order].reset_index()
    rev, ins, svc = d["revenue"], d["instruments"], d["service"]
    n_acc, n_rev, n_ins, n_svc = len(acc), len(rev), len(ins), len(svc)

    wb = Workbook()

    # ------------------------------------------------------------------ 1. Read Me
    ws = wb.active
    ws.title = "Read Me"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 70
    put(ws, 2, 2, "AccountIQ", F_TITLE)
    put(ws, 3, 2, "Customer Account Profitability Intelligence: Financial Model (FY2025)", F_SUB)
    put(ws, 4, 2, "Illustrative prototype using synthetic data. Not actual Roche or customer financial information.",
        Font(name=FONT, size=10, bold=True, color="B5473A"))

    put(ws, 6, 2, "ASSUMPTIONS (edit the yellow cells; the whole model recalculates)", F_BOLD, fill=FILL_SEC)
    ws.cell(row=6, column=3).fill = FILL_SEC
    ws.cell(row=6, column=4).fill = FILL_SEC
    assumptions = [
        ("Instrument useful life (years)", useful_life, "0.0", "UsefulLife",
         "Straight-line allocation period. Default 5 years."),
        ("Fiscal year start", f"=DATE({FISCAL_YEAR},1,1)", DATE_D, "FYStart",
         "12-month analysis window (Jan to Dec)."),
        ("High-revenue cut-off (net revenue percentile)", t.high_revenue_percentile, "0%", "HighRevPct",
         "Accounts at or above this percentile of net revenue count as high revenue."),
        ("Low-margin threshold", t.low_margin, "0%", "LowMargin",
         "Contribution margin below this is flagged as low margin."),
        ("Excessive discount threshold (% of gross)", t.excessive_discount_rate, "0%", "DiscPolicy",
         "Discount rate above this is flagged."),
        ("High service-cost threshold (% of net revenue)", t.high_service_ratio, "0%", "SvcLimit",
         "Service costs above this share of net revenue are flagged."),
        ("High instrument-cost threshold (% of net revenue)", t.high_instrument_ratio, "0%", "InstLimit",
         "Allocated instrument cost above this share of net revenue is flagged."),
    ]
    for i, (label, val, fmt, name, note) in enumerate(assumptions):
        r = 7 + i
        put(ws, r, 2, label)
        c = put(ws, r, 3, val, F_INPUT, fmt, FILL_YELLOW)
        c.border = BOX
        c.comment = Comment("Assumption chosen for this illustrative model (not sourced). Edit freely.", "AccountIQ")
        put(ws, r, 4, note, F_NOTE)
        add_name(wb, name, f"'Read Me'!$C${r}")

    r = 15
    put(ws, r, 2, "FORMULAS", F_BOLD, fill=FILL_SEC); ws.cell(row=r, column=3).fill = FILL_SEC; ws.cell(row=r, column=4).fill = FILL_SEC
    formulas = [
        ("Net Revenue", "Gross Reagent Revenue - Discounts"),
        ("Allocated Instrument Cost", "Purchase Cost / Useful Life x (months in service in FY, within useful life / 12)"),
        ("Service Costs", "Maintenance Expense + Repair Expense"),
        ("Contribution Profit", "Net Revenue - Allocated Instrument Cost - Service Costs"),
        ("Contribution Margin", "Contribution Profit / Net Revenue"),
    ]
    for i, (k, v) in enumerate(formulas):
        put(ws, r + 1 + i, 2, k, F_BOLD)
        put(ws, r + 1 + i, 3, v)

    r = 22
    put(ws, r, 2, "NO DOUBLE COUNTING", F_BOLD, fill=FILL_SEC); ws.cell(row=r, column=3).fill = FILL_SEC; ws.cell(row=r, column=4).fill = FILL_SEC
    nodc = [
        "Discounts reduce revenue once and are not subtracted again as a cost.",
        "Instrument purchase cost reaches profit only through the annual allocation. Total investment is shown as capital, not expensed.",
        "Maintenance and repair are operating expenses and are not part of the instrument allocation.",
    ]
    for i, v in enumerate(nodc):
        put(ws, r + 1 + i, 2, f"- {v}")

    r = 27
    put(ws, r, 2, "LIMITATIONS OF THE SIMPLIFIED ALLOCATION", F_BOLD, fill=FILL_SEC); ws.cell(row=r, column=3).fill = FILL_SEC; ws.cell(row=r, column=4).fill = FILL_SEC
    for i, v in enumerate(LIMITATIONS):
        put(ws, r + 1 + i, 2, f"- {v}")

    r = 28 + len(LIMITATIONS) + 1
    put(ws, r, 2, "SHEET GUIDE", F_BOLD, fill=FILL_SEC); ws.cell(row=r, column=3).fill = FILL_SEC; ws.cell(row=r, column=4).fill = FILL_SEC
    guide = [
        ("Customer Accounts", "30 fictional accounts: type, region, contract start, instrument count."),
        ("Revenue Data", "Monthly gross reagent revenue and discounts (inputs); net revenue (formula)."),
        ("Instrument Costs", "Each placed instrument: cost, placement date, months allocated and FY allocation (formulas)."),
        ("Service Costs", "Monthly maintenance and repair expense (inputs); total (formula)."),
        ("Account Profitability", "Full P&L per account via SUMIFS, ranking and opportunity flags."),
        ("Executive Dashboard", "Portfolio KPIs, P&L bridge, monthly trend, top 10 and bottom 10."),
    ]
    for i, (k, v) in enumerate(guide):
        put(ws, r + 1 + i, 2, k, F_BOLD)
        put(ws, r + 1 + i, 3, v)

    r = r + len(guide) + 2
    put(ws, r, 2, "COLOR KEY", F_BOLD, fill=FILL_SEC); ws.cell(row=r, column=3).fill = FILL_SEC; ws.cell(row=r, column=4).fill = FILL_SEC
    put(ws, r + 1, 2, "Blue text = hard-coded input (synthetic data)", F_INPUT)
    put(ws, r + 2, 2, "Black text = formula")
    put(ws, r + 3, 2, "Green text = link to another sheet", F_LINK)
    put(ws, r + 4, 2, "Yellow fill = key assumption you can edit", fill=FILL_YELLOW)

    # ------------------------------------------------------------------ 2. Customer Accounts
    ws = wb.create_sheet("Customer Accounts")
    header(ws, 1, ["Account ID", "Account Name", "Customer Type", "Region", "Contract Start", "Instrument Count"],
           [12, 34, 26, 13, 15, 13])
    for i, row in enumerate(acc.itertuples(), 2):
        put(ws, i, 1, row.account_id, F_INPUT)
        put(ws, i, 2, row.account_name, F_INPUT)
        put(ws, i, 3, row.customer_type, F_INPUT)
        put(ws, i, 4, row.region, F_INPUT)
        put(ws, i, 5, row.contract_start.to_pydatetime(), F_INPUT, DATE_D)
        put(ws, i, 6, f"=COUNTIF('Instrument Costs'!$B$2:$B${n_ins + 1},A{i})", F_LINK, "0")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:F{n_acc + 1}"

    # ------------------------------------------------------------------ 3. Revenue Data
    ws = wb.create_sheet("Revenue Data")
    header(ws, 1, ["Account ID", "Month", "Gross Reagent Revenue ($)", "Discounts ($)", "Net Revenue ($)", "Discount Rate"],
           [12, 12, 20, 16, 18, 13])
    for i, row in enumerate(rev.itertuples(), 2):
        put(ws, i, 1, row.account_id, F_INPUT)
        put(ws, i, 2, row.month.to_pydatetime(), F_INPUT, DATE)
        put(ws, i, 3, row.gross_reagent_revenue, F_INPUT, CUR)
        put(ws, i, 4, row.discount_amount, F_INPUT, CUR)
        put(ws, i, 5, f"=C{i}-D{i}", fmt=CUR)
        put(ws, i, 6, f"=IF(C{i}=0,0,D{i}/C{i})", fmt=PCT)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{n_rev + 1}"

    # ------------------------------------------------------------------ 4. Instrument Costs
    ws = wb.create_sheet("Instrument Costs")
    header(ws, 1, ["Instrument ID", "Account ID", "Instrument Model", "Placement Date", "Purchase Cost ($)",
                   "Placement Month Index (1 = Jan FY)", "Months Allocated in FY", "Full-Year Allocation ($)",
                   "Allocated Instrument Cost FY ($)"],
           [13, 12, 17, 15, 17, 18, 14, 18, 20])
    for i, row in enumerate(ins.itertuples(), 2):
        put(ws, i, 1, row.instrument_id, F_INPUT)
        put(ws, i, 2, row.account_id, F_INPUT)
        put(ws, i, 3, row.instrument_model, F_INPUT)
        put(ws, i, 4, row.placement_date.to_pydatetime(), F_INPUT, DATE_D)
        put(ws, i, 5, row.purchase_cost, F_INPUT, CUR)
        put(ws, i, 6, f"=(YEAR(D{i})-YEAR(FYStart))*12+MONTH(D{i})", fmt="0")
        put(ws, i, 7, f"=MAX(0,MIN(12,F{i}+ROUND(UsefulLife*12,0)-1)-MAX(1,F{i})+1)", fmt="0")
        put(ws, i, 8, f"=E{i}/UsefulLife", fmt=CUR)
        put(ws, i, 9, f"=H{i}*G{i}/12", fmt=CUR)
    tr = n_ins + 2
    put(ws, tr, 1, "Total", F_BOLD)
    for col in (5, 9):
        L = get_column_letter(col)
        put(ws, tr, col, f"=SUM({L}2:{L}{n_ins + 1})", F_BOLD, CUR)
    put(ws, tr + 2, 1, "Note: an instrument is allocated from its placement month through the end of its useful life. "
                       "Instruments older than the useful life carry zero FY cost.", F_NOTE)
    ws.freeze_panes = "A2"

    # ------------------------------------------------------------------ 5. Service Costs
    ws = wb.create_sheet("Service Costs")
    header(ws, 1, ["Account ID", "Month", "Maintenance Expense ($)", "Repair Expense ($)", "Total Service Costs ($)"],
           [12, 12, 20, 18, 20])
    for i, row in enumerate(svc.itertuples(), 2):
        put(ws, i, 1, row.account_id, F_INPUT)
        put(ws, i, 2, row.month.to_pydatetime(), F_INPUT, DATE)
        put(ws, i, 3, row.maintenance_expense, F_INPUT, CUR)
        put(ws, i, 4, row.repair_expense, F_INPUT, CUR)
        put(ws, i, 5, f"=C{i}+D{i}", fmt=CUR)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{n_svc + 1}"

    # ------------------------------------------------------------------ 6. Account Profitability
    ws = wb.create_sheet("Account Profitability")
    cols = ["Account ID", "Account Name", "Region", "Customer Type", "Gross Reagent Revenue ($)", "Discounts ($)",
            "Net Revenue ($)", "Discount Rate", "Instrument Investment ($)", "Allocated Instrument Cost ($)",
            "Maintenance ($)", "Repair ($)", "Service Costs ($)", "Contribution Profit ($)", "Contribution Margin",
            "Profit Rank", "Service Cost % Net Rev", "Instrument Cost % Net Rev",
            "High Rev / Low Margin", "Excessive Discount", "High Service Cost", "High Instrument Cost", "# Flags"]
    header(ws, 1, cols, [11, 32, 11, 24, 15, 13, 15, 10, 15, 15, 13, 12, 13, 15, 12, 9, 11, 11, 11, 11, 11, 11, 8])
    last = n_acc + 1
    RV, SV, IV = f"'Revenue Data'", f"'Service Costs'", f"'Instrument Costs'"
    rv_n, sv_n, iv_n = n_rev + 1, n_svc + 1, n_ins + 1
    for i in range(2, last + 1):
        put(ws, i, 1, f"='Customer Accounts'!A{i}", F_LINK)
        put(ws, i, 2, f"='Customer Accounts'!B{i}", F_LINK)
        put(ws, i, 3, f"='Customer Accounts'!D{i}", F_LINK)
        put(ws, i, 4, f"='Customer Accounts'!C{i}", F_LINK)
        put(ws, i, 5, f"=SUMIFS({RV}!$C$2:$C${rv_n},{RV}!$A$2:$A${rv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 6, f"=SUMIFS({RV}!$D$2:$D${rv_n},{RV}!$A$2:$A${rv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 7, f"=E{i}-F{i}", fmt=CUR)
        put(ws, i, 8, f"=IF(E{i}=0,0,F{i}/E{i})", fmt=PCT)
        put(ws, i, 9, f"=SUMIFS({IV}!$E$2:$E${iv_n},{IV}!$B$2:$B${iv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 10, f"=SUMIFS({IV}!$I$2:$I${iv_n},{IV}!$B$2:$B${iv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 11, f"=SUMIFS({SV}!$C$2:$C${sv_n},{SV}!$A$2:$A${sv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 12, f"=SUMIFS({SV}!$D$2:$D${sv_n},{SV}!$A$2:$A${sv_n},$A{i})", F_LINK, CUR)
        put(ws, i, 13, f"=K{i}+L{i}", fmt=CUR)
        put(ws, i, 14, f"=G{i}-J{i}-M{i}", fmt=CUR, bold=True)
        put(ws, i, 15, f"=IF(G{i}=0,0,N{i}/G{i})", fmt=PCT, bold=True)
        put(ws, i, 16, f"=RANK(N{i},$N$2:$N${last},0)", fmt="0")
        put(ws, i, 17, f"=IF(G{i}=0,0,M{i}/G{i})", fmt=PCT)
        put(ws, i, 18, f"=IF(G{i}=0,0,J{i}/G{i})", fmt=PCT)
        put(ws, i, 19, f'=IF(AND(G{i}>=PERCENTILE($G$2:$G${last},HighRevPct),O{i}<LowMargin),"Yes","")')
        put(ws, i, 20, f'=IF(H{i}>DiscPolicy,"Yes","")')
        put(ws, i, 21, f'=IF(Q{i}>SvcLimit,"Yes","")')
        put(ws, i, 22, f'=IF(R{i}>InstLimit,"Yes","")')
        put(ws, i, 23, f'=COUNTIF(S{i}:V{i},"Yes")', fmt="0")
        for c in range(19, 24):
            ws.cell(row=i, column=c).alignment = Alignment(horizontal="center")
    tr = last + 1
    put(ws, tr, 2, "Portfolio total", F_BOLD)
    for col in (5, 6, 7, 9, 10, 11, 12, 13, 14):
        L = get_column_letter(col)
        put(ws, tr, col, f"=SUM({L}2:{L}{last})", F_BOLD, CUR)
    put(ws, tr, 8, f"=IF(E{tr}=0,0,F{tr}/E{tr})", F_BOLD, PCT)
    put(ws, tr, 15, f"=IF(G{tr}=0,0,N{tr}/G{tr})", F_BOLD, PCT)
    for c in range(1, len(cols) + 1):
        ws.cell(row=tr, column=c).border = Border(top=Side(style="medium", color=NAVY))
    put(ws, tr + 2, 2, "Rows ordered by FY profit rank at build time; the Profit Rank column is a live formula. "
                       "Flags use the thresholds on Read Me.", F_NOTE)
    # conditional formatting
    rng = lambda L: f"{L}2:{L}{last}"
    ws.conditional_formatting.add(rng("O"), ColorScaleRule(start_type="min", start_color="F4CCCC",
                                                           mid_type="percentile", mid_value=50, mid_color="FFFFFF",
                                                           end_type="max", end_color="B7D7A8"))
    ws.conditional_formatting.add(rng("N"), DataBarRule(start_type="min", end_type="max", color=MUTED, showValue=True))
    ws.conditional_formatting.add(rng("N"), CellIsRule(operator="lessThan", formula=["0"], font=Font(color="B5473A", bold=True)))
    ws.conditional_formatting.add(rng("P"), CellIsRule(operator="lessThanOrEqual", formula=["10"],
                                                       fill=PatternFill("solid", fgColor="D9EAD3"), font=Font(color="274E13", bold=True)))
    ws.conditional_formatting.add(f"S2:V{last}", CellIsRule(operator="equal", formula=['"Yes"'],
                                                            fill=PatternFill("solid", fgColor="F4CCCC"), font=Font(color="990000", bold=True)))
    ws.conditional_formatting.add(rng("H"), FormulaRule(formula=[f"H2>DiscPolicy"], font=Font(color="990000")))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last}"

    # ------------------------------------------------------------------ 7. Executive Dashboard
    ws = wb.create_sheet("Executive Dashboard")
    ws.sheet_view.showGridLines = False
    for L, w in zip("ABCDEFGHIJKL", [2, 30, 17, 3, 30, 17, 17, 17, 17, 17, 17, 3]):
        ws.column_dimensions[L].width = w
    AP = "'Account Profitability'"
    put(ws, 2, 2, "AccountIQ: Executive Dashboard (FY2025)", F_TITLE)
    put(ws, 3, 2, "Illustrative prototype using synthetic data. Not actual Roche or customer financial information.",
        Font(name=FONT, size=9, italic=True, color="B5473A"))
    put(ws, 4, 2, "Useful life (years):", F_NOTE)
    put(ws, 4, 3, "=UsefulLife", F_LINK, "0.0")

    put(ws, 6, 2, "EXECUTIVE OVERVIEW", F_BOLD, fill=FILL_SEC); ws.cell(row=6, column=3).fill = FILL_SEC
    kpis = [
        ("Total net revenue", f"=SUM({AP}!G2:G{last})", CUR),
        ("Total contribution profit", f"=SUM({AP}!N2:N{last})", CUR),
        ("Average contribution margin (simple)", f"=AVERAGE({AP}!O2:O{last})", PCT),
        ("Portfolio contribution margin (weighted)", "=IF(C7=0,0,C8/C7)", PCT),
        ("Total instrument investment", f"=SUM({AP}!I2:I{last})", CUR),
        ("Total service expenses", f"=SUM({AP}!M2:M{last})", CUR),
        ("Number of customer accounts", f"=COUNTA({AP}!A2:A{last})", "0"),
        ("Accounts with at least one flag", f'=COUNTIF({AP}!W2:W{last},">0")', "0"),
    ]
    for i, (k, f, fmt) in enumerate(kpis):
        put(ws, 7 + i, 2, k)
        c = put(ws, 7 + i, 3, f, F_LINK if "!" in f else F_BASE, fmt, bold=True)
        c.border = BOX

    put(ws, 6, 5, "REVENUE VS COSTS (P&L BRIDGE)", F_BOLD, fill=FILL_SEC); ws.cell(row=6, column=6).fill = FILL_SEC
    bridge = [
        ("Gross reagent revenue", f"=SUM({AP}!E2:E{last})"),
        ("Less: discounts", f"=-SUM({AP}!F2:F{last})"),
        ("Net revenue", "=F7+F8"),
        ("Less: allocated instrument cost", f"=-SUM({AP}!J2:J{last})"),
        ("Less: service costs", f"=-SUM({AP}!M2:M{last})"),
        ("Contribution profit", "=F9+F10+F11"),
        ("Check: equals overview total (should be 0)", "=ROUND(F12-C8,2)"),
    ]
    for i, (k, f) in enumerate(bridge):
        put(ws, 7 + i, 5, k, F_BOLD if k in ("Net revenue", "Contribution profit") else F_BASE)
        put(ws, 7 + i, 6, f, F_LINK if "!" in f else F_BASE, CUR, bold=k in ("Net revenue", "Contribution profit"))

    # Monthly trend
    r0 = 17
    put(ws, r0, 2, "MONTHLY TREND", F_BOLD, fill=FILL_SEC)
    for c in range(3, 8):
        ws.cell(row=r0, column=c).fill = FILL_SEC
    hdrs = ["Month", "Gross Revenue ($)", "", "Net Revenue ($)", "Instrument Alloc. ($)", "Service Costs ($)", "Contribution ($)"]
    for c, h in enumerate(hdrs, 2):
        if h:
            cell = put(ws, r0 + 1, c, h, F_HDR, fill=FILL_HDR)
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
    IVr = f"{IV}!$F$2:$F${iv_n}"
    for m in range(12):
        r = r0 + 2 + m
        put(ws, r, 2, f"=DATE(YEAR(FYStart),{m + 1},1)", fmt=DATE)
        put(ws, r, 3, f"=SUMIFS({RV}!$C$2:$C${rv_n},{RV}!$B$2:$B${rv_n},$B{r})", F_LINK, CUR)
        put(ws, r, 5, f"=SUMIFS({RV}!$E$2:$E${rv_n},{RV}!$B$2:$B${rv_n},$B{r})", F_LINK, CUR)
        put(ws, r, 6, f"=SUMPRODUCT({IV}!$E$2:$E${iv_n}/UsefulLife/12*({IVr}<={m + 1})*({IVr}+ROUND(UsefulLife*12,0)-1>={m + 1}))",
            F_LINK, CUR)
        put(ws, r, 7, f"=SUMIFS({SV}!$E$2:$E${sv_n},{SV}!$B$2:$B${sv_n},$B{r})", F_LINK, CUR)
        put(ws, r, 8, f"=E{r}-F{r}-G{r}", fmt=CUR)
    rt = r0 + 14
    put(ws, rt, 2, "FY total", F_BOLD)
    for c in (3, 5, 6, 7, 8):
        L = get_column_letter(c)
        put(ws, rt, c, f"=SUM({L}{r0 + 2}:{L}{r0 + 13})", F_BOLD, CUR)
    put(ws, rt + 1, 2, "Check: monthly contribution equals annual (should be 0)", F_NOTE)
    put(ws, rt + 1, 8, f"=ROUND(H{rt}-C8,2)", fmt=CUR)

    # Top 10 / Bottom 10
    r1 = rt + 4
    put(ws, r1, 2, "TOP 10 MOST PROFITABLE ACCOUNTS", F_BOLD, fill=FILL_SEC); ws.cell(row=r1, column=3).fill = FILL_SEC
    put(ws, r1, 5, "BOTTOM 10 LOWEST-MARGIN ACCOUNTS", F_BOLD, fill=FILL_SEC)
    for c in (6, 7):
        ws.cell(row=r1, column=c).fill = FILL_SEC
    for c, h in [(2, "Account"), (3, "Contribution ($)"), (5, "Account"), (6, "Contribution Margin"), (7, "Net Revenue ($)")]:
        cell = put(ws, r1 + 1, c, h, F_HDR, fill=FILL_HDR)
        cell.alignment = Alignment(horizontal="center")
    names, prof, marg, netr = (f"{AP}!$B$2:$B${last}", f"{AP}!$N$2:$N${last}",
                               f"{AP}!$O$2:$O${last}", f"{AP}!$G$2:$G${last}")
    for k in range(1, 11):
        r = r1 + 1 + k
        put(ws, r, 3, f"=LARGE({prof},{k})", F_LINK, CUR)
        put(ws, r, 2, f"=INDEX({names},MATCH(C{r},{prof},0))", F_LINK)
        put(ws, r, 6, f"=SMALL({marg},{k})", F_LINK, PCT)
        put(ws, r, 5, f"=INDEX({names},MATCH(F{r},{marg},0))", F_LINK)
        put(ws, r, 7, f"=INDEX({netr},MATCH(F{r},{marg},0))", F_LINK, CUR)
    ws.conditional_formatting.add(f"C{r1 + 2}:C{r1 + 11}", DataBarRule(start_type="num", start_value=0, end_type="max", color=MUTED))
    ws.conditional_formatting.add(f"F{r1 + 2}:F{r1 + 11}", ColorScaleRule(start_type="min", start_color="F4CCCC",
                                                                       end_type="max", end_color="FFFFFF"))

    # Charts
    ch = LineChart()
    ch.title = "Monthly net revenue vs contribution ($)"
    ch.y_axis.title = "$"
    ch.height, ch.width = 7.5, 17
    ch.add_data(Reference(ws, min_col=5, min_row=r0 + 1, max_row=r0 + 13), titles_from_data=True)
    ch.add_data(Reference(ws, min_col=8, min_row=r0 + 1, max_row=r0 + 13), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=2, min_row=r0 + 2, max_row=r0 + 13))
    ch.series[0].graphicalProperties.line.solidFill = NAVY
    ch.series[1].graphicalProperties.line.solidFill = "8FAAD1"
    for s in ch.series:
        s.graphicalProperties.line.width = 22000
        s.smooth = False
    ch.y_axis.numFmt = "$#,##0"
    ch.x_axis.number_format = "mmm"
    ch.legend.position = "b"
    _clean_chart(ch)
    ws.add_chart(ch, "J6")

    bc = BarChart()
    bc.type = "bar"
    bc.title = "Top 10 accounts by contribution profit ($)"
    bc.height, bc.width = 9, 17
    bc.add_data(Reference(ws, min_col=3, min_row=r1 + 1, max_row=r1 + 11), titles_from_data=True)
    bc.set_categories(Reference(ws, min_col=2, min_row=r1 + 2, max_row=r1 + 11))
    bc.series[0].graphicalProperties.solidFill = NAVY
    bc.y_axis.numFmt = "$#,##0"
    bc.x_axis.scaling.orientation = "maxMin"
    bc.legend = None
    bc.gapWidth = 60
    _clean_chart(bc)
    ws.add_chart(bc, "J22")

    # sheet order
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def _clean_chart(ch):
    ch.roundedCorners = False
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    if ch.legend is not None:
        ch.legend.overlay = False
    if ch.title is not None and hasattr(ch.title, "overlay"):
        ch.title.overlay = False
    ch.style = 2


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p}")
