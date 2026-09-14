"""
export_to_excel.py

Exports data/scan_log.csv into data/predictions.xlsx with four sheets:

  - "Active Signals": only rows with no outcome yet (the game hasn't been
    backfilled as finished) -- this is the "what's live right now" view, so
    settled/old games don't clutter it every time this is regenerated.
  - "Settled History": every row that DOES have an outcome -- the full
    track record, kept for backtesting rather than deleted.
  - "Paper Trading": simulated buy-in and profit for each settled signal
    (from data/paper_trade_results.csv, written by paper_trade.py), ending
    in a bolded TOTAL row for overall profit/loss. Omitted if that file
    doesn't exist yet -- run paper_trade.py first.
  - "Summary": live Excel formulas (not hardcoded numbers) computing signal
    counts, win rate on settled signals, and how much raw edge collapses to
    net edge after fees/spread -- so the sheet recalculates automatically as
    new rows get appended by future scans. Formulas read from BOTH sheets
    combined, so the win rate always reflects every settled signal ever
    logged, not just the ones still shown in "Active Signals".

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
PAPER_TRADE_PATH = Path(__file__).parent / "data" / "paper_trade_results.csv"
OUT_PATH = Path(__file__).parent / "data" / "predictions.xlsx"

FONT_NAME = "Arial"
PCT_COLS = {"book_fair_prob", "kalshi_price", "entry_price", "raw_edge", "fee_cost", "spread_cost", "net_edge"}
PAPER_PCT_COLS = {"entry_price", "net_edge"}
PAPER_DOLLAR_COLS = {"buy_in", "profit", "cumulative_profit"}


def _write_sheet(ws, fields, rows):
    for col_idx, field in enumerate(fields, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field)
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
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = Font(name=FONT_NAME)
            if field in PCT_COLS:
                cell.number_format = "0.00%"

    for col_idx, field in enumerate(fields, start=1):
        letter = get_column_letter(col_idx)
        ws.column_dimensions[letter].width = max(14, len(field) + 4)


def _write_paper_trade_sheet(ws, fields, rows):
    """Same layout as _write_sheet, but with dollar formatting on buy-in/profit
    columns and the TOTAL row (written by paper_trade.py as the last row,
    identified by game_label == 'TOTAL') bolded so it stands out."""
    for col_idx, field in enumerate(fields, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.font = Font(name=FONT_NAME, bold=True)

    for row_idx, row in enumerate(rows, start=2):
        is_total = row.get("game_label") == "TOTAL"
        for col_idx, field in enumerate(fields, start=1):
            raw_value = row.get(field, "")
            value = raw_value
            if field == "contracts" and raw_value not in ("", None):
                try:
                    value = int(raw_value)
                except ValueError:
                    value = raw_value
            elif field in (PAPER_PCT_COLS | PAPER_DOLLAR_COLS) and raw_value not in ("", None):
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = Font(name=FONT_NAME, bold=is_total)
            if field in PAPER_PCT_COLS:
                cell.number_format = "0.00%"
            elif field in PAPER_DOLLAR_COLS:
                cell.number_format = "$#,##0.00"

    for col_idx, field in enumerate(fields, start=1):
        letter = get_column_letter(col_idx)
        ws.column_dimensions[letter].width = max(14, len(field) + 4)


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
    active_rows = [r for r in rows if not r.get("outcome")]
    settled_rows = [r for r in rows if r.get("outcome")]

    wb = Workbook()

    # ---------- Active Signals sheet (default view — no settled games) ----------
    active_ws = wb.active
    active_ws.title = "Active Signals"
    _write_sheet(active_ws, fields, active_rows)

    # ---------- Settled History sheet (full track record) ----------
    history_ws = wb.create_sheet("Settled History")
    _write_sheet(history_ws, fields, settled_rows)

    # ---------- Paper Trading sheet (simulated buy-in/profit per position) ----------
    # Reads whatever paper_trade.py last wrote -- run that script first (the
    # export_excel.yml workflow already does: backfill -> paper_trade -> export)
    # so this reflects the latest settled outcomes.
    if PAPER_TRADE_PATH.exists():
        with open(PAPER_TRADE_PATH, newline="") as f:
            paper_rows = list(csv.DictReader(f))
        if paper_rows:
            paper_fields = list(paper_rows[0].keys())
            paper_ws = wb.create_sheet("Paper Trading")
            _write_paper_trade_sheet(paper_ws, paper_fields, paper_rows)

    # Summary formulas read across BOTH sheets, so win rate/edge stats always
    # reflect every row ever logged, not just what's currently "Active".
    col = {field: get_column_letter(i + 1) for i, field in enumerate(fields)}

    def rng(sheet_title, field, n):
        return f"'{sheet_title}'!{col[field]}2:{col[field]}{n + 1}" if n > 0 else None

    def combined(field):
        parts = [p for p in (rng("Active Signals", field, len(active_rows)),
                              rng("Settled History", field, len(settled_rows))) if p]
        return parts

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

    def sum_across(func, *field_sets):
        """Builds e.g. SUMPRODUCT(...) + SUMPRODUCT(...) across both sheets,
        since a single SUMPRODUCT can't span two separate sheet ranges."""
        terms = []
        n_sheets = max(len(fs) for fs in field_sets)
        for i in range(n_sheets):
            args = [fs[i] for fs in field_sets]
            terms.append(f"{func}({','.join(args)})")
        return "+".join(terms) if terms else "0"

    fair_rngs = combined("book_fair_prob")
    kalshi_rngs = combined("kalshi_price")
    net_edge_rngs = combined("net_edge")
    raw_edge_rngs = combined("raw_edge")
    outcome_rngs = combined("outcome")
    scan_ts_rngs = combined("scan_timestamp")

    # An "underpriced favorite" is a real favorite (fair prob > 50%) priced by
    # Kalshi as an underdog (price < 50%) — this always implies side="buy_yes".
    # We're only trading this pattern for now, not the mirror "buy_no" case.
    fav_conds = [f"({f}>0.5)*({k}<0.5)" for f, k in zip(fair_rngs, kalshi_rngs)]

    summary_ws.cell(row=1, column=1, value="Kalshi Edge Finder — Summary").font = Font(name=FONT_NAME, bold=True, size=14)

    label(3, "Total games logged")
    formula(3, "=" + "+".join(f"COUNTA({r})" for r in scan_ts_rngs) if scan_ts_rngs else 0)

    fav_edge_terms = [f"({fav})*({ne}>=0.01)" for fav, ne in zip(fav_conds, net_edge_rngs)]

    label(4, "Underpriced-favorite signals ≥1% net edge")
    formula(4, "=" + "+".join(f"SUMPRODUCT({t})" for t in fav_edge_terms) if fav_edge_terms else 0)

    label(5, "...of those, settled (outcome known)")
    formula(5, "=" + "+".join(f'SUMPRODUCT({t}*({o}<>""))' for t, o in zip(fav_edge_terms, outcome_rngs)) if fav_edge_terms else 0)

    label(6, "...of those, wins (favorite actually won)")
    formula(6, "=" + "+".join(f'SUMPRODUCT({t}*({o}="yes"))' for t, o in zip(fav_edge_terms, outcome_rngs)) if fav_edge_terms else 0)

    wins_expr = "+".join(f'SUMPRODUCT({t}*({o}="yes"))' for t, o in zip(fav_edge_terms, outcome_rngs)) if fav_edge_terms else "0"
    settled_expr = "+".join(f'SUMPRODUCT({t}*({o}<>""))' for t, o in zip(fav_edge_terms, outcome_rngs)) if fav_edge_terms else "0"

    label(7, "Win rate on settled underpriced-favorite signals")
    formula(7, f'=IFERROR(({wins_expr})/({settled_expr}),"n/a — no settled signals yet")', pct=True)

    label(9, "Average raw edge (before fees)")
    formula(9, "=IFERROR(AVERAGE(" + ",".join(raw_edge_rngs) + "),0)" if raw_edge_rngs else 0, pct=True)

    label(10, "Average net edge (after fees & spread)")
    formula(10, "=IFERROR(AVERAGE(" + ",".join(net_edge_rngs) + "),0)" if net_edge_rngs else 0, pct=True)

    label(11, "Average edge lost to fees/spread")
    formula(11, "=B9-B10", pct=True)

    label(13, "Note")
    note = summary_ws.cell(row=13, column=1,
                            value="Formulas recalculate automatically when this file is opened in Excel or LibreOffice. "
                                  "'Active Signals' hides settled games — see 'Settled History' for the full track record.")
    note.font = Font(name=FONT_NAME, italic=True, size=9)
    summary_ws.merge_cells(start_row=13, start_column=1, end_row=13, end_column=2)

    OUT_PATH.parent.mkdir(exist_ok=True)
    wb.save(OUT_PATH)
    print(f"Exported {len(active_rows)} active + {len(settled_rows)} settled row(s) to {OUT_PATH}")


if __name__ == "__main__":
    export()

