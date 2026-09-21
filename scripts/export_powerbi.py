"""Export the warehouse as a small star schema for Power BI.

    python scripts/export_powerbi.py          # writes docs/powerbi/*.csv

One dimension, postings, that every fact table links to on `quarter`:

  posting.csv        one row per SEC posting, with its holdings window and a label
  market.csv         one row per posting: lending, cover, concentration
  borrower_groups.csv  one row per posting and borrower group
  funds.csv          one row per posting and lending fund (latest snapshot)
  fund_flags.csv     one row per fund: how many postings it spent near the limit
                     or short of collateral

Amounts are in US dollars and ratios are fractions (0.103 = 10.3%), so Power
BI's own formatting decides how they are shown.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "powerbi"

QUERIES = {
    "posting": """
        select quarter, holdings_from, holdings_to,
               strftime(holdings_from, '%b %Y') || ' to ' || strftime(holdings_to, '%b %Y') as holdings_label,
               row_number() over (order by quarter) as posting_order
        from trend_market order by quarter""",
    "market": """
        select quarter, lending_funds, funds_reconciling, on_loan_usd, coverage, top5_share, hhi, borrower_groups
        from trend_market order by quarter""",
    "borrower_groups": """
        select quarter, parent_lei, parent_name, funds, on_loan_usd, share, rank_in_quarter
        from trend_groups order by quarter, rank_in_quarter""",
    "funds": """
        select quarter, series_id, series_name, report_date, net_assets, borrower_total as on_loan_usd,
               n_groups as borrower_groups, top_group as largest_borrower, top_group_value as largest_borrower_usd,
               on_loan_pct_nav, top_group_pct_nav as largest_borrower_pct_nav,
               top_group_share_of_lending as largest_borrower_share, cash_collateral, noncash_collateral,
               cash_collateral + noncash_collateral as collateral_usd, coverage, reconciliation
        from hist_fund order by quarter, borrower_total desc""",
    "fund_flags": """
        select series_id, series_name, quarters_seen, quarters_near_ceiling, quarters_below_90pct,
               max_on_loan_pct_nav, min_coverage
        from trend_fund_flags order by quarters_near_ceiling desc, quarters_below_90pct desc""",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(REPO / "data" / "warehouse.duckdb"), read_only=True) as con:
        for name, sql in QUERIES.items():
            path = OUT / f"{name}.csv"
            con.execute(f"copy ({sql}) to '{path.as_posix()}' (header, delimiter ',')")
            rows = con.execute(f"select count(*) from ({sql})").fetchone()[0]
            print(f"{name + '.csv':<22}{rows:>7,} rows  {path.stat().st_size / 1024:>7,.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
