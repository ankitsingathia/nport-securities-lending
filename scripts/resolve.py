"""Run the warehouse steps for one or more quarters.

    python scripts/resolve.py 2026q2                         # one quarter
    python scripts/resolve.py 2025q3 2025q4 2026q1 2026q2    # history for the trend
    python scripts/resolve.py 2026q2 --calibrate             # name-match scores first

Runs sql/00_macros.sql, then 01_resolve_borrowers, 02_latest_filing,
03_fund_exposure, 04_collateral and 05_history in data/warehouse.duckdb, with
the raw filings attached read-only, so nothing here can alter them. The tests
call connect() and run() directly with their own paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
RAW_DB = REPO / "data" / "nport.duckdb"
WAREHOUSE = REPO / "data" / "warehouse.duckdb"
GLEIF_CSV = REPO / "data" / "gleif" / "entities.csv"
SQL = REPO / "sql"
STEPS = ("01_resolve_borrowers.sql", "02_latest_filing.sql", "03_fund_exposure.sql",
         "04_collateral.sql", "05_history.sql")


def connect(raw_db: Path = RAW_DB, warehouse: Path = WAREHOUSE) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(warehouse))
    con.execute(f"attach '{Path(raw_db).as_posix()}' as src (read_only)")
    con.execute((SQL / "00_macros.sql").read_text())
    return con


def run(con: duckdb.DuckDBPyConnection, quarter: str, match: float = 0.95, gleif_csv: Path = GLEIF_CSV) -> None:
    sql = chr(10).join((SQL / f).read_text() for f in STEPS)
    sql = (sql.replace("${QUARTER}", quarter)
              .replace("${MATCH}", str(match))
              .replace("${GLEIF_CSV}", Path(gleif_csv).as_posix()))
    con.execute(sql)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarters", nargs="+", help="one or more quarters, e.g. 2025q3 2026q2")
    ap.add_argument("--match", type=float, default=0.95, help="min name similarity to trust a filed LEI")
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
        return 0

    print(con.execute("""
        select resolution, count(*) as borrower_rows, round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_rows,
               round(sum(value_on_loan) / 1e9, 1) as on_loan_bn
        from borrower_final group by 1 order by borrower_rows desc""").df().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
