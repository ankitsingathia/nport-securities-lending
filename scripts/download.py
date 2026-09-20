"""Download SEC Form N-PORT quarterly data sets.

    python scripts/download.py 2026q2 2026q1        # named quarters
    python scripts/download.py --from 2025q1        # that quarter to the latest

The SEC rate-limits hard and answers with a 1.9 KB HTML page titled "Request
Rate Threshold Exceeded" instead of an error code you would notice, so this
waits between files, backs off when it is blocked, and refuses to keep any file
that is not a real zip. Downloads resume: a quarter already on disk is skipped.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
URL = "https://www.sec.gov/files/dera/data/form-n-port-data-sets/{q}_nport.zip"
# The SEC asks automated traffic to identify itself with a contact address.
UA = "ankit-singathia-portfolio-research ankitsingathia@users.noreply.github.com"
PAUSE = 3.0          # seconds between files, well under the published limit
BACKOFF = (60, 180, 420, 900)  # 403 means blocked for a while, not forever


def quarters_from(start: str, end: str = "2026q2") -> list[str]:
    def parts(q: str) -> tuple[int, int]:
        return int(q[:4]), int(q[-1])

    y, n = parts(start)
    ey, en = parts(end)
    out = []
    while (y, n) <= (ey, en):
        out.append(f"{y}q{n}")
        y, n = (y + 1, 1) if n == 4 else (y, n + 1)
    return out


def is_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return z.namelist() != []
    except (zipfile.BadZipFile, OSError):
        return False


def fetch(quarter: str) -> bool:
    out = RAW / f"{quarter}_nport.zip"
    if out.exists() and is_zip(out):
        print(f"{quarter}: already downloaded ({out.stat().st_size / 1e6:.0f} MB)", flush=True)
        return True

    req = urllib.request.Request(URL.format(q=quarter), headers={"User-Agent": UA})
    for attempt, wait in enumerate((0, *BACKOFF), start=1):
        if wait:
            print(f"{quarter}: blocked, waiting {wait}s before attempt {attempt}", flush=True)
            time.sleep(wait)
        try:
            tmp = out.with_suffix(".part")
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=600) as r, tmp.open("wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            if not is_zip(tmp):
                tmp.unlink(missing_ok=True)
                continue  # rate-limit page dressed as a download
            tmp.replace(out)
            mb, secs = out.stat().st_size / 1e6, time.perf_counter() - t0
            print(f"{quarter}: {mb:,.0f} MB in {secs:.0f}s", flush=True)
            return True
        except urllib.error.HTTPError as e:
            if e.code != 403:
                print(f"{quarter}: HTTP {e.code}", file=sys.stderr, flush=True)
                return False
        except urllib.error.URLError as e:
            print(f"{quarter}: {e.reason}", file=sys.stderr, flush=True)
    print(f"{quarter}: gave up after {len(BACKOFF) + 1} attempts", file=sys.stderr, flush=True)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarters", nargs="*", help="e.g. 2026q2 2026q1")
    ap.add_argument("--from", dest="start", help="download this quarter through the latest")
    args = ap.parse_args(argv)

    wanted = args.quarters or (quarters_from(args.start) if args.start else [])
    if not wanted:
        ap.error("name at least one quarter, or use --from")
    RAW.mkdir(parents=True, exist_ok=True)

    ok = 0
    for i, q in enumerate(wanted):
        if i:
            time.sleep(PAUSE)
        ok += fetch(q)
    print(f"\n{ok} of {len(wanted)} quarters on disk in {RAW}")
    return 0 if ok == len(wanted) else 1


if __name__ == "__main__":
    raise SystemExit(main())
