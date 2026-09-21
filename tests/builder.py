"""Build small N-PORT quarters for tests, in the SEC's own table layout.

Every column is text, exactly as scripts/ingest.py loads the real files, and
LEIs carry correct ISO 17442 check digits. A test describes funds, borrowers
and collateral in a few lines, plants one problem, and runs the real pipeline
SQL against it. Nothing here touches the network or data/.
"""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from scripts import resolve

TABLES = {
    "submission": ["ACCESSION_NUMBER", "FILING_DATE", "FILE_NUM", "SUB_TYPE", "REPORT_ENDING_PERIOD",
                   "REPORT_DATE", "IS_LAST_FILING"],
    "fund_reported_info": ["ACCESSION_NUMBER", "SERIES_NAME", "SERIES_ID", "SERIES_LEI", "TOTAL_ASSETS",
                           "TOTAL_LIABILITIES", "NET_ASSETS", "IS_NON_CASH_COLLATERAL"],
    "borrower": ["ACCESSION_NUMBER", "BORROWER_ID", "NAME", "LEI", "AGGREGATE_VALUE"],
    "borrow_aggregate": ["ACCESSION_NUMBER", "BORROW_AGGREGATE_ID", "AMOUNT", "COLLATERAL", "INVESTMENT_CAT",
                         "OTHER_DESC"],
    "fund_reported_holding": ["ACCESSION_NUMBER", "HOLDING_ID", "ISSUER_NAME", "ISSUER_LEI", "ISSUER_TITLE",
                              "ISSUER_CUSIP", "BALANCE", "UNIT", "CURRENCY_CODE", "CURRENCY_VALUE", "ASSET_CAT"],
    "securities_lending": ["HOLDING_ID", "IS_CASH_COLLATERAL", "CASH_COLLATERAL_AMOUNT", "IS_NON_CASH_COLLATERAL",
                           "NON_CASH_COLLATERAL_VALUE", "IS_LOAN_BY_FUND", "LOAN_VALUE"],
}
ENTITY_COLUMNS = ["lei", "legal_name", "category", "registration_status", "country", "effective_lei",
                  "parent_lei", "parent_name", "parent_basis"]


def lei(body: str) -> str:
    """A format-valid LEI: an 18-character body plus ISO 17442 check digits."""
    body = body.upper().ljust(18, "0")[:18]
    n = int("".join(str(int(c, 36)) for c in body + "00"))
    return body + f"{98 - n % 97:02d}"


class Quarter:
    """One quarterly posting: filings, borrowers, holdings and collateral."""

    def __init__(self, name: str = "2026q2"):
        self.name = name
        self.rows: dict[str, list[dict]] = {t: [] for t in TABLES}
        self._ids = 0

    def _next(self) -> int:
        self._ids += 1
        return self._ids

    def filing(self, series_id: str, series_name: str, net_assets: float, report_date: str = "28-FEB-2026",
               filing_date: str = "20-APR-2026", sub_type: str = "NPORT-P", noncash_flag: str = "N") -> str:
        acc = f"0000000000-26-{self._next():06d}"
        self.rows["submission"].append({"ACCESSION_NUMBER": acc, "FILING_DATE": filing_date, "SUB_TYPE": sub_type,
                                        "REPORT_ENDING_PERIOD": "31-DEC-2026", "REPORT_DATE": report_date})
        self.rows["fund_reported_info"].append({"ACCESSION_NUMBER": acc, "SERIES_ID": series_id,
                                                "SERIES_NAME": series_name, "NET_ASSETS": str(net_assets),
                                                "TOTAL_ASSETS": str(net_assets),
                                                "IS_NON_CASH_COLLATERAL": noncash_flag})
        return acc

    def borrower(self, acc: str, name: str, lei_: str | None, value: float) -> None:
        self.rows["borrower"].append({"ACCESSION_NUMBER": acc, "BORROWER_ID": str(self._next()), "NAME": name,
                                      "LEI": lei_ or "", "AGGREGATE_VALUE": str(value)})

    def position_on_loan(self, acc: str, value: float) -> None:
        hid = str(self._next())
        self.rows["fund_reported_holding"].append({"ACCESSION_NUMBER": acc, "HOLDING_ID": hid,
                                                   "ISSUER_NAME": "Some Issuer", "ASSET_CAT": "EC",
                                                   "CURRENCY_VALUE": str(value)})
        self.rows["securities_lending"].append({"HOLDING_ID": hid, "IS_CASH_COLLATERAL": "N",
                                                "IS_NON_CASH_COLLATERAL": "N", "IS_LOAN_BY_FUND": "Y",
                                                "LOAN_VALUE": str(value)})

    def cash_collateral(self, acc: str, amount: float, vehicle: str = "Collateral Pool") -> None:
        hid = str(self._next())
        self.rows["fund_reported_holding"].append({"ACCESSION_NUMBER": acc, "HOLDING_ID": hid,
                                                   "ISSUER_NAME": vehicle, "ASSET_CAT": "STIV",
                                                   "CURRENCY_VALUE": str(amount)})
        self.rows["securities_lending"].append({"HOLDING_ID": hid, "IS_CASH_COLLATERAL": "Y",
                                                "CASH_COLLATERAL_AMOUNT": str(amount),
                                                "IS_NON_CASH_COLLATERAL": "N", "IS_LOAN_BY_FUND": "N"})

    def noncash_collateral(self, acc: str, value: float, category: str = "UST") -> None:
        self.rows["borrow_aggregate"].append({"ACCESSION_NUMBER": acc, "BORROW_AGGREGATE_ID": str(self._next()),
                                              "AMOUNT": str(value), "COLLATERAL": str(value),
                                              "INVESTMENT_CAT": category})

    def lend(self, acc: str, name: str, lei_: str | None, value: float, cover: float = 1.03) -> None:
        """The common case: one borrower, the matching position, cash collateral at `cover`."""
        self.borrower(acc, name, lei_, value)
        self.position_on_loan(acc, value)
        if cover:
            self.cash_collateral(acc, round(value * cover, 2))


def entity(lei_: str, name: str, parent_lei: str | None = None, parent_name: str | None = None,
           category: str = "GENERAL", status: str = "ISSUED", basis: str = "ultimate_parent") -> dict:
    """One registry row, as scripts/fetch_gleif.py writes it after roll-up."""
    return {"lei": lei_, "legal_name": name, "category": category, "registration_status": status,
            "country": "US", "effective_lei": lei_, "parent_lei": parent_lei or lei_,
            "parent_name": parent_name or name, "parent_basis": basis if parent_lei else "top_of_group"}


def build(tmp_path: Path, quarters: list[Quarter], entities: list[dict]):
    """Write the raw database and registry file, run the pipeline, return the warehouse."""
    raw = tmp_path / "raw.duckdb"
    with duckdb.connect(str(raw)) as con:
        for q in quarters:
            con.execute(f'create schema "{q.name}"')
            for table, cols in TABLES.items():
                con.execute(f'create table "{q.name}".{table} ({", ".join(f"{c} varchar" for c in cols)})')
                rows = [tuple(r.get(c) for c in cols) for r in q.rows[table]]
                if rows:
                    marks = ", ".join("?" for _ in cols)
                    con.executemany(f'insert into "{q.name}".{table} values ({marks})', rows)
    gleif = tmp_path / "entities.csv"
    with gleif.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ENTITY_COLUMNS)
        w.writeheader()
        w.writerows(entities)
    wh = resolve.connect(raw, tmp_path / "warehouse.duckdb")
    for q in quarters:
        resolve.run(wh, q.name, gleif_csv=gleif)
    return wh
