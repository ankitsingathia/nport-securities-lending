"""Collateral is added up from both places a filing reports it, and gaps stay visible."""

import pytest

from tests.builder import Quarter, build, entity, lei

MS = lei("MORGANSTANLEYCOLLC")
REGISTRY = [entity(MS, "MORGAN STANLEY & CO. LLC")]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    cash = q.filing("S000000001", "Cash Only Fund", 300e6)
    q.lend(cash, "MORGAN STANLEY & CO. LLC", MS, 10_000_000, cover=1.03)

    mixed = q.filing("S000000002", "Mixed Collateral Fund", 300e6, noncash_flag="Y")
    q.lend(mixed, "MORGAN STANLEY & CO. LLC", MS, 10_000_000, cover=0)
    q.cash_collateral(mixed, 5_000_000, vehicle="BlackRock Cash Funds: Institutional")
    q.noncash_collateral(mixed, 5_300_000, category="UST")

    treasuries = q.filing("S000000003", "Treasuries Only Fund", 300e6, noncash_flag="Y")
    q.lend(treasuries, "MORGAN STANLEY & CO. LLC", MS, 10_000_000, cover=0)
    q.noncash_collateral(treasuries, 10_400_000, category="UST")

    short = q.filing("S000000004", "Slightly Short Fund", 300e6)
    q.lend(short, "MORGAN STANLEY & CO. LLC", MS, 10_000_000, cover=0.995)

    none_ = q.filing("S000000005", "Nothing Recorded Fund", 300e6)
    q.lend(none_, "MORGAN STANLEY & CO. LLC", MS, 10_000_000, cover=0)
    return build(tmp_path, [q], REGISTRY)


def coverage(wh, series):
    return wh.execute("select coverage from fund_collateral where series_id = ?", [series]).fetchone()[0]


@pytest.mark.parametrize("series, expected", [
    ("S000000001", 1.03),    # cash reinvested
    ("S000000002", 1.03),    # half cash, half Treasuries
    ("S000000003", 1.04),    # non-cash only
    ("S000000004", 0.995),   # just under full cover: reported as it is
    ("S000000005", 0.0),     # nothing recorded: kept, not dropped
])
def test_coverage_adds_both_kinds_of_collateral(wh, series, expected):
    assert coverage(wh, series) == pytest.approx(expected)


def test_cash_and_noncash_are_kept_apart_for_reporting(wh):
    split = wh.execute("""select cash_collateral, noncash_collateral from fund_collateral
                          where series_id = 'S000000002'""").fetchone()
    assert split == (pytest.approx(5_000_000), pytest.approx(5_300_000))


def test_the_reinvestment_vehicle_is_recorded(wh):
    vehicles = wh.execute("""select issuer_name, sum(cash_reinvested) from cash_collateral_holdings
                             group by 1 order by 1""").fetchall()
    assert ("BlackRock Cash Funds: Institutional", pytest.approx(5_000_000)) in vehicles


def test_a_fund_with_no_collateral_is_still_counted(wh):
    assert wh.execute("select count(*) from fund_collateral").fetchone()[0] == 5
