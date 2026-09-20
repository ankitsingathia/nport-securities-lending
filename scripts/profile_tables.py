"""Report what is actually in a loaded quarter: sizes, emptiness, keys, links.

    python scripts/profile_tables.py 2026q2

Run this before designing anything. It assumes no table or column names: it
reads whatever ingest loaded and answers the questions that decide the design.

  * how big is each table, and which ones are worth building on
  * which columns are entirely empty, so a field that looks promising in the
    documentation but is never filed is caught now rather than later
  * which columns are unique (candidate keys) and which are shared between
    tables (candidate joins)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "nport.duckdb"
FILL_SAMPLE = 200_000  # rows sampled for fill rates on very large tables


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarter", help="e.g. 2026q2")
    ap.add_argument("--empty-only", action="store_true", help="only list columns that are never filled")
    args = ap.parse_args(argv)

    if not DB.exists():
        raise SystemExit(f"{DB} not found. Run: python scripts/ingest.py {args.quarter}")
    con = duckdb.connect(str(DB), read_only=True)
    q = args.quarter
    tables = [r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema = ? order by table_name", [q]).fetchall()]
    if not tables:
        raise SystemExit(f"no tables in schema {q}")

    print(f"{'table':<36}{'rows':>12}{'cols':>6}")
    sizes = {}
    for t in tables:
        rows = con.execute(f'select count(*) from "{q}"."{t}"').fetchone()[0]
        cols = [r[0] for r in con.execute(f'describe "{q}"."{t}"').fetchall()]
        sizes[t] = (rows, cols)
        print(f"{t:<36}{rows:>12,}{len(cols):>6}")

    print("\nColumns never filled (all NULL or blank):")
    found = False
    for t, (rows, cols) in sizes.items():
        if not rows:
            print(f"  {t}: table is empty")
            found = True
            continue
        n = min(rows, FILL_SAMPLE)
        exprs = ", ".join(f'''count(case when "{c}" is not null and "{c}" <> '' then 1 end)''' for c in cols)
        filled = con.execute(f'select {exprs} from (select * from "{q}"."{t}" limit {n})').fetchone()
        empty = [c for c, f in zip(cols, filled) if f == 0]
        if empty:
            found = True
            print(f"  {t}: {', '.join(empty)}")
    if not found:
        print("  none")
    if args.empty_only:
        return 0

    print("\nCandidate keys (unique across the table):")
    for t, (rows, cols) in sizes.items():
        if not rows:
            continue
        keys = []
        for c in cols:
            if con.execute(f'select count(distinct "{c}") from "{q}"."{t}"').fetchone()[0] == rows:
                keys.append(c)
        print(f"  {t}: {', '.join(keys) if keys else 'no single-column key'}")

    print("\nColumns shared between tables (candidate joins):")
    seen: dict[str, list[str]] = {}
    for t, (_, cols) in sizes.items():
        for c in cols:
            seen.setdefault(c, []).append(t)
    for c, ts in sorted(seen.items()):
        if len(ts) > 1:
            print(f"  {c:<28}{', '.join(ts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
