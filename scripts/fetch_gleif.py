"""Look up every borrower LEI in GLEIF: registered legal name and ultimate parent.

    python scripts/fetch_gleif.py 2026q2

GLEIF is the official global LEI registry (api.gleif.org, free, no key). Each
LEI costs two requests, the record and its ultimate parent, paced at about one
per second to stay inside GLEIF's published limit. Answers are cached as JSON
under data/gleif/, so reruns only fetch LEIs not seen before.

Writes data/gleif/entities.csv: one row per LEI with its registered name, the
entity it rolls up through, and its ultimate parent. A duplicate or retired LEI
is followed to its successor and a branch to its head office before the parent
is looked up; `parent_basis` records the path. An entity with no reported
parent is the top of its own group.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "nport.duckdb"
CACHE = REPO / "data" / "gleif"
API = "https://api.gleif.org/api/v1/lei-records/{lei}{suffix}"
PAUSE = 1.1


def get(lei: str, suffix: str = "") -> dict | None:
    path = CACHE / f"{lei}{suffix.replace('/', '_')}.json"
    if path.exists():
        return json.loads(path.read_text())
    req = urllib.request.Request(API.format(lei=lei, suffix=suffix), headers={"Accept": "application/vnd.api+json"})
    for attempt in range(1, 5):
        time.sleep(PAUSE if attempt == 1 else 10 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            body = {"data": None, "http_status": e.code}  # 404 = no such parent relationship
            break
        except (urllib.error.URLError, TimeoutError) as e:
            # A dropped connection is not an answer. Retry, and never cache it.
            print(f"  {lei}{suffix}: {e}, retrying", flush=True)
    else:
        raise SystemExit(f"{lei}{suffix}: no response after 4 attempts; rerun to resume")
    path.write_text(json.dumps(body))
    return body


def name_of(record: dict | None) -> str:
    try:
        return record["data"]["attributes"]["entity"]["legalName"]["name"]
    except (TypeError, KeyError):
        return ""


def successor_of(rec: dict) -> str | None:
    entity = rec["data"]["attributes"]["entity"]
    lei = (entity.get("successorEntity") or {}).get("lei")
    if not lei and entity.get("successorEntities"):
        lei = entity["successorEntities"][0].get("lei")
    return lei


def roll_up(lei: str) -> tuple[str, str, str, str]:
    """Follow an LEI to the entity that counts, then to its ultimate parent.

    A duplicate or retired LEI points at its successor; a branch LEI points at
    its head office. Only then is the ultimate parent looked up. Returns
    (effective LEI, parent LEI, parent name, path taken).
    """
    path, current = [], lei
    for _ in range(5):  # chains are short; the cap stops a loop in bad data
        rec = get(current)
        if not rec or not rec.get("data"):
            break
        attrs = rec["data"]["attributes"]
        if attrs["registration"]["status"] in ("DUPLICATE", "RETIRED", "ANNULLED", "MERGED") and successor_of(rec):
            current = successor_of(rec)
            path.append("successor")
            continue
        if attrs["entity"].get("category") == "BRANCH":
            head = get(current, "/head-office")
            if head and head.get("data"):
                current = head["data"]["id"]
                path.append("head_office")
                continue
        break
    up = get(current, "/ultimate-parent")
    if up and up.get("data"):
        return current, up["data"]["id"], name_of(up), "+".join(path + ["ultimate_parent"])
    return current, current, name_of(get(current)), "+".join(path + ["top_of_group"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarter")
    args = ap.parse_args(argv)
    CACHE.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(DB), read_only=True) as con:
        leis = [r[0] for r in con.execute(f'''
            select distinct upper(trim(LEI)) from "{args.quarter}".borrower
            where coalesce(trim(LEI), '') not in ('', 'N/A', 'NONE') order by 1''').fetchall()]
    print(f"{len(leis)} distinct borrower LEIs", flush=True)

    rows = []
    for i, lei in enumerate(leis, 1):
        rec = get(lei)
        attrs = (rec or {}).get("data", {}).get("attributes", {}) if rec and rec.get("data") else {}
        effective, parent_lei, parent_name, basis = roll_up(lei)
        rows.append({
            "lei": lei,
            "legal_name": name_of(rec),
            "category": attrs.get("entity", {}).get("category", ""),
            "registration_status": attrs.get("registration", {}).get("status", ""),
            "country": attrs.get("entity", {}).get("legalAddress", {}).get("country", ""),
            "effective_lei": effective,
            "parent_lei": parent_lei,
            "parent_name": parent_name,
            "parent_basis": basis,
        })
        if i % 20 == 0 or i == len(leis):
            print(f"  {i}/{len(leis)}", flush=True)

    out = CACHE / "entities.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    missing = sum(1 for r in rows if not r["legal_name"])
    print(f"\nwrote {out} ({len(rows)} LEIs, {missing} not found in GLEIF)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
