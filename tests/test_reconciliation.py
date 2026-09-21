"""A filing states its lending twice; a fund is only trusted when the two agree."""

import pytest

from tests.builder import Quarter, build, entity, lei

GS = lei("GOLDMANSACHSCOLLC0")
REGISTRY = [entity(GS, "GOLDMAN SACHS & CO. LLC")]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()

    close = q.filing("S000000001", "Close Enough Fund", 200e6)
    q.borrower(close, "GOLDMAN SACHS & CO. LLC", GS, 10_000_000)
    q.position_on_loan(close, 10_050_000)                       # 0.5% apart

    apart = q.filing("S000000002", "Far Apart Fund", 200e6)
    q.borrower(apart, "GOLDMAN SACHS & CO. LLC", GS, 10_000_000)
    q.position_on_loan(apart, 8_000_000)                        # 20% apart

    blank = q.filing("S000000003", "Every Position Says No Fund", 200e6)
    q.borrower(blank, "GOLDMAN SACHS & CO. LLC", GS, 5_000_000)
    for _ in range(3):                                          # the iShares 2025q4 pattern
        q.position_on_loan(blank, 1_700_000, flagged="N")

    no_nav = q.filing("S000000004", "No Net Assets Fund", 0)
    q.lend(no_nav, "GOLDMAN SACHS & CO. LLC", GS, 1_000_000)

    tiny = q.filing("S000000005", "Tiny Fund", 2e6)
    q.borrower(tiny, "GOLDMAN SACHS & CO. LLC", GS, 50_000)
    q.position_on_loan(tiny, 50_900)                            # 1.8% apart, but only $900
    return build(tmp_path, [q], REGISTRY)


def label(wh, series):
    return wh.execute("select reconciliation from fund_lending where series_id = ?", [series]).fetchone()[0]


@pytest.mark.parametrize("series, expected", [
    ("S000000001", "reconciles"),
    ("S000000002", "does_not_reconcile"),
    ("S000000003", "no_holding_detail"),
    ("S000000004", "nav_missing"),
    ("S000000005", "reconciles"),
])
def test_each_fund_gets_the_right_label(wh, series, expected):
    assert label(wh, series) == expected


def test_missing_net_assets_leaves_the_ratios_empty(wh):
    ratios = wh.execute("""select on_loan_pct_nav, top_group_pct_nav from fund_lending
                           where series_id = 'S000000004'""").fetchone()
    assert ratios == (None, None)


def test_borrower_totals_are_kept_whatever_the_label(wh):
    # Market totals come from the borrower section, so flagging a fund must not drop its lending.
    assert wh.execute("select sum(borrower_total) from fund_lending").fetchone()[0] == pytest.approx(26_050_000)
