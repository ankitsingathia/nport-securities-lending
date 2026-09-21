"""A valid LEI that belongs to a different firm is corrected or flagged, never trusted blindly."""

import pytest

from tests.builder import Quarter, build, entity, lei

JPM_LLC, JPM_PLC, JPMC = lei("JPMSECURITIESLLC00"), lei("JPMSECURITIESPLC00"), lei("JPMORGANCHASECO000")
UBS, UBS_GROUP = lei("UBSAG0000000000000"), lei("UBSGROUPAG00000000")
SGAS, SOCGEN = lei("SGAMERICASSECLLC00"), lei("SOCIETEGENERALE000")
BNPS, BNP = lei("BNPPARIBASSECCORP0"), lei("BNPPARIBAS00000000")
REGISTRY = [
    entity(JPM_LLC, "J.P. MORGAN SECURITIES LLC", JPMC, "JPMORGAN CHASE & CO."),
    entity(JPM_PLC, "J.P. MORGAN SECURITIES PLC", JPMC, "JPMORGAN CHASE & CO."),
    entity(JPMC, "JPMORGAN CHASE & CO."),
    entity(UBS, "UBS AG", UBS_GROUP, "UBS Group AG"),
    entity(UBS_GROUP, "UBS Group AG"),
    entity(SGAS, "SG AMERICAS SECURITIES, LLC", SOCGEN, "SOCIETE GENERALE"),
    entity(SOCGEN, "SOCIETE GENERALE"),
    entity(BNPS, "BNP PARIBAS SECURITIES CORP.", BNP, "BNP PARIBAS"),
    entity(BNP, "BNP PARIBAS"),
]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    ok = q.filing("S000000001", "Clean Filer Fund", net_assets=900_000_000)
    q.lend(ok, "J.P. MORGAN SECURITIES LLC", JPM_LLC, 10_000_000)
    q.lend(ok, "J.P. MORGAN SECURITIES PLC", JPM_PLC, 5_000_000)
    q.lend(ok, "BNP PARIBAS SECURITIES CORP.", BNPS, 3_000_000)

    bad = q.filing("S000000002", "Careless Filer Fund", net_assets=400_000_000)
    q.lend(bad, "JP MORGAN SECURITIES LLC", UBS, 2_000_000)                 # UBS's LEI on a JPMorgan name
    q.lend(bad, "Jeffries LLC", JPM_LLC, 700_000)                           # JPMorgan's LEI on an unknown name
    q.lend(bad, "BNP PARIBAS SECURITIES CORPORATION", SGAS, 1_500_000)     # shares only "SECURITIES"
    return build(tmp_path, [q], REGISTRY)


def row(wh, fund, filed):
    return wh.execute("""select resolution, resolved_lei, parent_lei from borrower_final b
                         join filing using (accession_number)
                         where series_name = ? and filed_name = ?""", [fund, filed]).fetchone()


def test_genuine_lending_is_never_moved_between_entities(wh):
    # The $19.6bn bug: LLC and PLC share a name key once "LLC"/"PLC" are stripped.
    assert row(wh, "Clean Filer Fund", "J.P. MORGAN SECURITIES LLC") == ("lei_confirmed", JPM_LLC, JPMC)
    assert row(wh, "Clean Filer Fund", "J.P. MORGAN SECURITIES PLC") == ("lei_confirmed", JPM_PLC, JPMC)


def test_a_confirmed_name_overrides_another_firms_lei(wh):
    resolution, _, parent = row(wh, "Careless Filer Fund", "JP MORGAN SECURITIES LLC")
    assert resolution == "lei_corrected"
    assert parent == JPMC  # JPMorgan, not UBS Group


def test_an_unsupported_name_is_flagged_not_assigned(wh):
    assert row(wh, "Careless Filer Fund", "Jeffries LLC") == ("lei_name_conflict", None, None)


def test_a_shared_generic_word_is_not_evidence(wh):
    resolution, _, parent = row(wh, "Careless Filer Fund", "BNP PARIBAS SECURITIES CORPORATION")
    assert resolution == "lei_corrected"
    assert parent == BNP  # "SECURITIES" alone must not tie it to SG Americas


def test_flagged_value_stays_in_the_totals(wh):
    total = wh.execute("select sum(value_on_loan) from exposure").fetchone()[0]
    assert total == pytest.approx(22_200_000)
    kept = wh.execute("""select group_name, value_on_loan from fund_group_exposure
                         where group_id like 'UNRESOLVED:%'""").fetchall()
    assert kept == [("Jeffries LLC", pytest.approx(700_000))]
