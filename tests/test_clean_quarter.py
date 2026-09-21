"""A quarter with no problems must pass through untouched."""

import pytest

from tests.builder import Quarter, build, entity, lei

JPM, JPM_PARENT = lei("JPMSECURITIESLLC00"), lei("JPMORGANCHASECO000")
BARC = lei("BARCLAYSBANKPLC000")
REGISTRY = [
    entity(JPM, "J.P. MORGAN SECURITIES LLC", JPM_PARENT, "JPMORGAN CHASE & CO."),
    entity(JPM_PARENT, "JPMORGAN CHASE & CO."),
    entity(BARC, "BARCLAYS BANK PLC"),
]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    a = q.filing("S000000001", "Alpha Equity Fund", net_assets=100_000_000)
    q.lend(a, "J.P. MORGAN SECURITIES LLC", JPM, 6_000_000)
    q.lend(a, "BARCLAYS BANK PLC", BARC, 4_000_000)
    b = q.filing("S000000002", "Beta Bond Fund", net_assets=50_000_000)
    q.lend(b, "J.P. MORGAN SECURITIES LLC", JPM, 2_500_000)
    return build(tmp_path, [q], REGISTRY)


def test_the_generated_leis_are_valid():
    for code in (JPM, JPM_PARENT, BARC):
        assert len(code) == 20
        assert int("".join(str(int(c, 36)) for c in code)) % 97 == 1


def test_every_borrower_is_confirmed_by_its_lei(wh):
    assert wh.execute("select distinct resolution from borrower_final").fetchall() == [("lei_confirmed",)]


def test_no_value_is_lost_or_invented(wh):
    assert wh.execute("select sum(value_on_loan) from exposure").fetchone()[0] == pytest.approx(12_500_000)


def test_entities_roll_up_to_their_parent_group(wh):
    rows = dict(wh.execute("select parent_name, sum(value_on_loan) from exposure group by 1").fetchall())
    assert rows == {"JPMORGAN CHASE & CO.": pytest.approx(8_500_000), "BARCLAYS BANK PLC": pytest.approx(4_000_000)}


def test_both_reports_reconcile_and_collateral_is_measured(wh):
    rows = wh.execute("select series_id, reconciliation, round(coverage, 4) from fund_collateral order by 1").fetchall()
    assert rows == [("S000000001", "reconciles", 1.03), ("S000000002", "reconciles", 1.03)]


def test_exposure_is_measured_against_fund_size(wh):
    top = wh.execute("""select top_group, round(top_group_pct_nav, 4), round(on_loan_pct_nav, 4)
                        from fund_lending where series_id = 'S000000001'""").fetchone()
    assert top == ("JPMORGAN CHASE & CO.", 0.06, 0.10)
