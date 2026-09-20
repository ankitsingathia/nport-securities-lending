"""Unpack a quarter's N-PORT zip and load every table into DuckDB as-is.

    python scripts/ingest.py 2026q2

Nothing here assumes what the tables are called or what columns they hold: the
SEC's layout is discovered from the zip, loaded with every column as text, and
reported. Typing and cleaning happen later, in the warehouse, where the rules
are visible. Loading text first means a surprise value cannot be silently
coerced or dropped on the way in.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
EXTRACTED = REPO / "data" / "extracted"
DB = REPO / "data" / "nport.duckdb"


def unpack(quarter: str) -> Path:
    src = RAW / f"{quarter}_nport.zip"
    if not src.exists():
        raise SystemExit(f"{src} not found. Run: python scripts/download.py {quarter}")
    out = EXTRACTED / quarter
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src) as z:
        members = [m for m in z.namelist() if not m.endswith("/")]
        if all((out / Path(m).name).exists() for m in members):
            print(f"{quarter}: already unpacked ({len(members)} files)", flush=True)
            return out
        for m in members:
            target = out / Path(m).name
            with z.open(m) as fin, target.open("wb") as fout:
                while chunk := fin.read(1 << 20):
                    fout.write(chunk)
            print(f"  unpacked {target.name} ({target.stat().st_size / 1e6:,.1f} MB)", flush=True)
    return out


def load(quarter: str, folder: Path) -> None:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".tsv", ".txt", ".csv"))
    if not files:
        raise SystemExit(f"no data files in {folder}")
    con = duckdb.connect(str(DB))
    con.execute(f'create schema if not exists "{quarter}"')
    print(f"\n{'table':<34}{'rows':>12}{'cols':>7}")
    for f in files:
        table = f.stem.lower()
        con.execute(f'''
            create or replace table "{quarter}"."{table}" as
            select * from read_csv('{f.as_posix()}', delim='\t', header=true,
                                   all_varchar=true, quote='"', escape='"',
                                   ignore_errors=false, null_padding=true)
        ''')
        rows, cols = con.execute(f'select count(*) from "{quarter}"."{table}"').fetchone()[0], \
            len(con.execute(f'describe "{quarter}"."{table}"').fetchall())
        print(f"{table:<34}{rows:>12,}{cols:>7}")
    con.close()
    print(f"\nloaded into {DB}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarter", help="e.g. 2026q2")
    args = ap.parse_args(argv)
    load(args.quarter, unpack(args.quarter))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
