"""Build the cross-quarter trend tables and print the headline view.

    python scripts/trend.py

Run after scripts/resolve.py has been run for every quarter. Reads the history
tables in data/warehouse.duckdb and writes trend_market, trend_groups and
trend_fund_flags there.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "data" / "warehouse.duckdb"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(WAREHOUSE))
    con.execute((REPO / "sql" / "06_trend.sql").read_text())

    print("== Market, by SEC posting quarter ==")
    print(con.execute("""
        select quarter, strftime(holdings_from, '%b %Y') || ' - ' || strftime(holdings_to, '%b %Y') as holdings,
               lending_funds, round(on_loan_usd / 1e9, 1) as on_loan_bn, round(100 * coverage, 1) as coverage_pct,
               round(100 * top5_share, 1) as top5_pct, hhi
        from trend_market order by quarter""").df().to_string(index=False))

    quarters = [r[0] for r in con.execute("select quarter from trend_market order by quarter").fetchall()]
    first, last = quarters[0], quarters[-1]
    print(f"\n== Top borrower groups, share of fund lending ({first} to {last}) ==")
    print(con.execute(f"""
        with p as (pivot (select quarter, parent_name, share from trend_groups) on quarter using any_value(share))
        select parent_name, {", ".join(f'round(100 * "{q}", 1) as "{q}"' for q in quarters)},
               round(100 * ("{last}" - "{first}"), 1) as change_pts
        from p order by "{last}" desc nulls last limit 10""").df().to_string(index=False))

    print("\n== Funds with a problem in more than one quarter ==")
    print(con.execute(f"""
        select 'near the lending ceiling (33%+ of net assets)' as issue,
               count(*) filter (where quarters_near_ceiling >= 2) as funds_2plus,
               count(*) filter (where quarters_near_ceiling = {len(quarters)}) as funds_every_quarter
        from trend_fund_flags
        union all
        select 'collateral below 90%',
               count(*) filter (where quarters_below_90pct >= 2),
               count(*) filter (where quarters_below_90pct = {len(quarters)})
        from trend_fund_flags""").df().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
