"""The same firm filed under different spellings must end up as one exposure."""

import pytest

from tests.builder import Quarter, build, entity, lei

BOFA = lei("BOFASECURITIESINC0")
JPM = lei("JPMSECURITIESLLC00")
HSBC = lei("HSBCBANKPLC0000000")
BMO = lei("BANKOFMONTREAL0000")
CIBC = lei("CIBCHEADOFFICE0000")
REGISTRY = [
    entity(BOFA, "BOFA SECURITIES, INC."),
    entity(JPM, "J.P. MORGAN SECURITIES LLC"),
    entity(HSBC, "HSBC BANK PLC"),
    entity(BMO, "Bank of Montréal"),
    entity(CIBC, "Canadian Imperial Bank of Commerce"),
]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    f = q.filing("S000000001", "Gamma Index Fund", net_assets=500_000_000)
    for spelling in ("BOFA SECURITIES, INC.", "BofA Securities Inc", "BOFA SECURITIES  INC."):
        q.lend(f, spelling, BOFA, 1_000_000)
    q.lend(f, "JP MORGAN SECURITIES LLC", JPM, 1_000_000)
    q.lend(f, "H.S.B.C. BANK PLC", HSBC, 1_000_000)
    q.lend(f, "Banque de Montreal", BMO, 1_000_000)
    q.lend(f, "CIBC NEW YORK", CIBC, 1_000_000)
    return build(tmp_path, [q], REGISTRY)


def test_every_spelling_resolves_to_its_registered_firm(wh):
    unresolved = wh.execute("select filed_name, resolution from borrower_final where resolved_lei is null").fetchall()
    assert unresolved == []


def test_three_bofa_spellings_become_one_exposure(wh):
    rows = wh.execute("""select resolved_lei, count(*), sum(value_on_loan) from exposure
                         where filed_name ilike '%bofa%' group by 1""").fetchall()
    assert rows == [(BOFA, 3, pytest.approx(3_000_000))]


@pytest.mark.parametrize("filed, expected", [
    ("JP MORGAN SECURITIES LLC", JPM),   # "J.P." and "JP" normalise to the same key
    ("H.S.B.C. BANK PLC", HSBC),         # dotted initials collapse to "HSBC"
    ("Banque de Montreal", BMO),         # accent and language differ, "MONTREAL" does not
    ("CIBC NEW YORK", CIBC),             # filed under the firm's initials
])
def test_hard_spellings_are_matched_on_evidence(wh, filed, expected):
    resolved, resolution = wh.execute(
        "select resolved_lei, resolution from borrower_final where filed_name = ?", [filed]).fetchone()
    assert resolved == expected
    assert resolution in ("lei_confirmed", "lei_accepted")


def test_the_fund_sees_five_groups_not_seven_names(wh):
    assert wh.execute("select n_groups from fund_lending").fetchone()[0] == 5
