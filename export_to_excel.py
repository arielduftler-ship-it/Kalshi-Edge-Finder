"""
export_to_excel.py

Exports data/scan_log.csv into data/predictions.xlsx with two sheets:

  - "Data": every logged row, as-is.
  - "Summary": live Excel formulas (not hardcoded numbers) computing signal
    counts, win rate on settled signals, and how much raw edge collapses to
    net edge after fees/spread — so the sheet recalculates automatically as
    new rows get appended by future scans.

Uses only Excel-2007-era functions (SUMIFS/COUNTIFS/AVERAGEIFS/IFERROR) so
formulas evaluate correctly in both Excel and LibreOffice.

Usage:
    python export_to_excel.py
"""

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"
OUT_PATH = Path(__file__).parent / "data" / "predictions.xlsx"

FONT_NAME = "Arial"
PCT_COLS = {"book_fair_prob", "kalshi_price", "entry_price", "raw_edge", "fee_cost", "spread_cost", "net_edge"}


def export():
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH} yet — run run_daily_scan.py first.")
        return

    with open(LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Log file is empty — nothing to export yet.")
        return

    fields = list(rows[0].keys())
    n = len(rows)

    wb = Workbook()

    # ---------- Data sheet ----------
    data_ws = wb.active
    data_ws.title = "Data"

    for col_idx, field in enumerate(fields, start=1):
        cell = data_ws.cell(row=1, column=col_idx, value=field)
        cell.font = Font(name=FONT_NAME, bold=True)

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, field in enumerate(fields, start=1):
            raw_value = row.get(field, "")
            value = raw_value
            if field in PCT_COLS and raw_value not in ("", None):
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value
            cell = data_ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = Font(name=FONT_NAME)
            if field in PCT_COLS:
                cell.number_format = "0.00%"

    for col_idx, field in enumerate(fields, start=1):
        letter = get_column_letter(col_idx)
        data_ws.column_dimensions[letter].width = max(14, len(field) + 4)

    col = {field: get_column_letter(i + 1) for i, field in enumerate(fields)}
    last_row = n + 1  # +1 for header

    # ---------- Summary sheet ----------
    summary_ws = wb.create_sheet("Summary")
    summary_ws.column_dimensions["A"].width = 34
    summary_ws.column_dimensions["B"].width = 16

    def label(r, text):
        cell = summary_ws.cell(row=r, column=1, value=text)
        cell.font = Font(name=FONT_NAME, bold=True)

    def formula(r, f, pct=False):
        cell = summary_ws.cell(row=r, column=2, value=f)
        cell.font = Font(name=FONT_NAME)
        if pct:
            cell.number_format = "0.00%"
        return cell

    net_edge_rng = f"Data!{col['net_edge']}2:{col['net_edge']}{last_row}"
    raw_edge_rng = f"Data!{col['raw_edge']}2:{col['raw_edge']}{last_row}"
    outcome_rng = f"Data!{col['outcome']}2:{col['outcome']}{last_row}"
    side_rng = f"Data!{col['side']}2:{col['side']}{last_row}"
    fair_prob_rng = f"Data!{col['book_fair_prob']}2:{col['book_fair_prob']}{last_row}"
    kalshi_price_rng = f"Data!{col['kalshi_price']}2:{col['kalshi_price']}{last_row}"
    # An "underpriced favorite" is a real favorite (fair prob > 50%) priced by
    # Kalshi as an underdog (price < 50%) — this always implies side="buy_yes".
    # We're only trading this pattern for now, not the mirror "buy_no" case.
    fav_cond = f'({fair_prob_rng}>0.5)*({kalshi_price_rng}<0.5)'

    summary_ws.cell(row=1, column=1, value="Kalshi Edge Finder — Summary").font = Font(name=FONT_NAME, bold=True, size=14)

    label(3, "Total games logged")
    formula(3, f'=COUNTA(Data!{col["scan_timestamp"]}2:{col["scan_timestamp"]}{last_row})')

    label(4, "Underpriced-favorite signals ≥1% net edge")
    formula(4, f'=SUMPRODUCT({fav_cond}*({net_edge_rng}>=0.01))')

    label(5, "...of those, settled (outcome known)")
    formula(5, f'=SUMPRODUCT({fav_cond}*({net_edge_rng}>=0.01)*({outcome_rng}<>""))')

    label(6, "...of those, wins (favorite actually won)")
    formula(6, f'=SUMPRODUCT({fav_cond}*({net_edge_rng}>=0.01)*({outcome_rng}="yes"))')

    label(7, "Win rate on settled underpriced-favorite signals")
    formula(
        7,
        f'=IFERROR(SUMPRODUCT({fav_cond}*({net_edge_rng}>=0.01)*({outcome_rng}="yes"))'
        f'/SUMPRODUCT({fav_cond}*({net_edge_rng}>=0.01)*({outcome_rng}<>"")),"n/a — no settled signals yet")',
        pct=True,
    )

    label(9, "Average raw edge (before fees)")
    formula(9, f'=IFERROR(AVERAGE({raw_edge_rng}),0)', pct=True)

    label(10, "Average net edge (after fees & spread)")
    formula(10, f'=IFERROR(AVERAGE({net_edge_rng}),0)', pct=True)

    label(11, "Average edge lost to fees/spread")
    formula(11, "=B9-B10", pct=True)

    label(13, "Note")
    note = summary_ws.cell(row=13, column=1,
                            value="Formulas recalculate automatically when this file is opened in Excel or LibreOffice.")
    note.font = Font(name=FONT_NAME, italic=True, size=9)
    summary_ws.merge_cells(start_row=13, start_column=1, end_row=13, end_column=2)

    OUT_PATH.parent.mkdir(exist_ok=True)
    wb.save(OUT_PATH)
    print(f"Exported {n} row(s) to {OUT_PATH}")


if __name__ == "__main__":
    export()
