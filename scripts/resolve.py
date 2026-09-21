"""Resolve filed borrowers to legal entities and parent groups.

    python scripts/resolve.py 2026q2                 # one quarter
    python scripts/resolve.py 2025q3 2025q4 2026q1 2026q2   # history for the trend
    python scripts/resolve.py 2026q2 --match 0.90
    python scripts/resolve.py 2026q2 --calibrate     # show the score distribution first

Runs sql/00_macros.sql, then 01_resolve_borrowers, 02_latest_filing,
03_fund_exposure and 04_collateral in
data/warehouse.duckdb,
with the raw filings attached read-only, so nothing here can alter them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
RAW_DB = REPO / "data" / "nport.duckdb"
WAREHOUSE = REPO / "data" / "warehouse.duckdb"
SQL = REPO / "sql"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(WAREHOUSE))
    con.execute(f"attach '{RAW_DB.as_posix()}' as src (read_only)")
    con.execute((SQL / "00_macros.sql").read_text())
    return con


def run(con, quarter: str, match: float) -> None:
    sql = chr(10).join((SQL / f).read_text() for f in ("01_resolve_borrowers.sql", "02_latest_filing.sql", "03_fund_exposure.sql", "04_collateral.sql", "05_history.sql"))
    sql = sql.replace("${QUARTER}", quarter).replace("${MATCH}", str(match))
    import os
    cwd = os.getcwd()
    os.chdir(REPO)  # the SQL reads data/gleif/entities.csv relative to the repo
    try:
        con.execute(sql)
    finally:
        os.chdir(cwd)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarters", nargs="+", help="one or more quarters, e.g. 2025q3 2026q2")
    ap.add_argument("--match", type=float, default=0.90, help="min name similarity to trust a filed LEI")
    ap.add_argument("--calibrate", action="store_true")
    args = ap.parse_args(argv)

    con = connect()
    for quarter in args.quarters:
        run(con, quarter, args.match)
        if len(args.quarters) > 1:
            print(f"{quarter}: done", flush=True)

    if args.calibrate:
        print("Similarity between filed name and registry name for the filed LEI (rows):")
        print(con.execute("""
            select case when lei_name_similarity is null then 'no LEI / not in registry'
                        else printf('%.2f-%.2f', floor(lei_name_similarity * 20) / 20,
                                    floor(lei_name_similarity * 20) / 20 + 0.05) end as band,
                   count(*) as borrower_rows, round(sum(value_on_loan) / 1e9, 1) as on_loan_bn
            from borrower_scored group by 1 order by 1""").df().to_string(index=False))
        print("\nLowest-scoring distinct pairs (filed name vs registry name):")
        print(con.execute("""
            select round(lei_name_similarity, 3) as sim, filed_name, filed_lei_registry_name as registry_name,
                   count(*) as rows_
            from borrower_scored where lei_name_similarity is not null
            group by 1, 2, 3 order by sim limit 25""").df().to_string(index=False, max_colwidth=48))
        return 0

    print(con.execute("""
        select resolution, count(*) as borrower_rows, round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_rows,
               round(sum(value_on_loan) / 1e9, 1) as on_loan_bn
        from borrower_final group by 1 order by borrower_rows desc""").df().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
