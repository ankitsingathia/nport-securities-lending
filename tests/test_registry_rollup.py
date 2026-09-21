"""Branches and replaced LEIs must roll up to the right parent before exposure is grouped.

Runs scripts/fetch_gleif.roll_up against a fake GLEIF cache in the API's own
response shape. The network is blocked, so a missing fixture fails loudly
instead of quietly calling the real registry.
"""

import json
import urllib.request

import pytest

from scripts import fetch_gleif
from tests.builder import lei

PARIS_BRANCH, LONDON_HQ, JPMC = lei("JPMPARISBRANCH0000"), lei("JPMSECURITIESPLC00"), lei("JPMORGANCHASECO000")
BNP_DUP, BNP_SEC, BNP = lei("BNPDUPLICATE000000"), lei("BNPPARIBASSECCORP0"), lei("BNPPARIBAS00000000")
TOP = lei("MORGANSTANLEY00000")
LAPSED = lei("JANNEYMONTGOMERY00")
LOOP_A, LOOP_B = lei("LOOPA0000000000000"), lei("LOOPB0000000000000")


def record(code, name, status="ISSUED", category="GENERAL", successor=None):
    entity = {"legalName": {"name": name}, "category": category, "legalAddress": {"country": "US"}}
    if successor:
        entity["successorEntity"] = {"lei": successor}
    return {"data": {"id": code, "attributes": {"registration": {"status": status}, "entity": entity}}}


def points_to(code, name):
    return {"data": {"id": code, "attributes": {"entity": {"legalName": {"name": name}}}}}


NO_PARENT = {"data": None, "http_status": 404}

CACHE = {
    PARIS_BRANCH: record(PARIS_BRANCH, "JP MORGAN SECURITIES PLC", category="BRANCH"),
    f"{PARIS_BRANCH}_head-office": points_to(LONDON_HQ, "J.P. MORGAN SECURITIES PLC"),
    LONDON_HQ: record(LONDON_HQ, "J.P. MORGAN SECURITIES PLC"),
    f"{LONDON_HQ}_ultimate-parent": points_to(JPMC, "JPMORGAN CHASE & CO."),
    BNP_DUP: record(BNP_DUP, "BNP PARIBAS SECURITIES CORP.", status="DUPLICATE", successor=BNP_SEC),
    BNP_SEC: record(BNP_SEC, "BNP PARIBAS SECURITIES CORP."),
    f"{BNP_SEC}_ultimate-parent": points_to(BNP, "BNP PARIBAS"),
    TOP: record(TOP, "MORGAN STANLEY"),
    f"{TOP}_ultimate-parent": NO_PARENT,
    LAPSED: record(LAPSED, "JANNEY MONTGOMERY SCOTT LLC", status="LAPSED"),
    f"{LAPSED}_ultimate-parent": NO_PARENT,
    LOOP_A: record(LOOP_A, "LOOP A", status="RETIRED", successor=LOOP_B),
    LOOP_B: record(LOOP_B, "LOOP B", status="RETIRED", successor=LOOP_A),
    f"{LOOP_A}_ultimate-parent": NO_PARENT,
    f"{LOOP_B}_ultimate-parent": NO_PARENT,
}


@pytest.fixture(autouse=True)
def fake_registry(tmp_path, monkeypatch):
    for key, body in CACHE.items():
        (tmp_path / f"{key}.json").write_text(json.dumps(body))
    monkeypatch.setattr(fetch_gleif, "CACHE", tmp_path)
    monkeypatch.setattr(fetch_gleif, "PAUSE", 0)

    def no_network(*args, **kwargs):
        raise AssertionError("test tried to call the real GLEIF API")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)


def test_a_branch_rolls_up_through_its_head_office():
    assert fetch_gleif.roll_up(PARIS_BRANCH) == (LONDON_HQ, JPMC, "JPMORGAN CHASE & CO.", "head_office+ultimate_parent")


def test_a_duplicate_lei_follows_its_successor():
    assert fetch_gleif.roll_up(BNP_DUP) == (BNP_SEC, BNP, "BNP PARIBAS", "successor+ultimate_parent")


def test_the_top_of_a_group_is_its_own_parent():
    assert fetch_gleif.roll_up(TOP) == (TOP, TOP, "MORGAN STANLEY", "top_of_group")


def test_a_lapsed_lei_is_kept_as_it_is():
    # Lapsed means not renewed; the firm still exists, so it is not replaced.
    assert fetch_gleif.roll_up(LAPSED)[:2] == (LAPSED, LAPSED)


def test_a_successor_loop_stops_instead_of_hanging():
    effective, parent, _, basis = fetch_gleif.roll_up(LOOP_A)
    assert effective in (LOOP_A, LOOP_B)
    assert basis.count("successor") == 5
