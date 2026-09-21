"""History keeps one copy of each quarter, and the trend reads it correctly."""

from pathlib import Path

import pytest

from scripts import resolve
from tests.builder import Quarter, build, entity, lei

REPO = Path(__file__).resolve().parents[1]
CITI = lei("CITIGROUPGLOBALMKT")
REGISTRY = [entity(CITI, "CITIGROUP GLOBAL MARKETS INC.")]


def quarter(name, report_date, big_cover):
    q = Quarter(name)
    heavy = q.filing("S000000001", "Near The Ceiling Fund", 100e6, report_date=report_date)
    q.lend(heavy, "CITIGROUP GLOBAL MARKETS INC.", CITI, 40_000_000, cover=big_cover)   # 40% of net assets
    small = q.filing("S000000002", "Small Short Fund", 10e6, report_date=report_date)
    q.lend(small, "CITIGROUP GLOBAL MARKETS INC.", CITI, 1_000_000, cover=0.5)
    return q


@pytest.fixture
def wh(tmp_path):
    con = build(tmp_path, [quarter("2026q1", "30-NOV-2025", 1.10), quarter("2026q2", "28-FEB-2026", 1.10)],
                REGISTRY)
    resolve.run(con, "2026q2", gleif_csv=tmp_path / "entities.csv")   # a rerun must not duplicate
    con.execute((REPO / "sql" / "06_trend.sql").read_text())
    return con


def test_a_rerun_leaves_one_copy_of_each_quarter(wh):
    rows = wh.execute("select quarter, count(*) from hist_fund group by 1 order by 1").fetchall()
    assert rows == [("2026q1", 2), ("2026q2", 2)]


def test_market_coverage_is_weighted_by_value(wh):
    # (44m + 0.5m) / 41m, not the 0.80 a simple average of the two funds would give.
    cover = wh.execute("select coverage from trend_market where quarter = '2026q2'").fetchone()[0]
    assert cover == pytest.approx(44_500_000 / 41_000_000)


def test_a_fund_near_the_ceiling_every_quarter_is_flagged_as_persistent(wh):
    flags = wh.execute("""select quarters_seen, quarters_near_ceiling, quarters_below_90pct
                          from trend_fund_flags where series_id = 'S000000001'""").fetchone()
    assert flags == (2, 2, 0)


def test_a_fund_short_of_collateral_every_quarter_is_flagged(wh):
    flags = wh.execute("""select quarters_below_90pct from trend_fund_flags
                          where series_id = 'S000000002'""").fetchone()
    assert flags == (2,)


def test_each_posting_records_its_holdings_window(wh):
    windows = wh.execute("""select quarter, holdings_from::varchar, holdings_to::varchar
                            from trend_market order by quarter""").fetchall()
    assert windows == [("2026q1", "2025-11-30", "2025-11-30"), ("2026q2", "2026-02-28", "2026-02-28")]


def test_borrower_share_and_rank_are_per_quarter(wh):
    rows = wh.execute("select quarter, share, rank_in_quarter from trend_groups order by quarter").fetchall()
    assert rows == [("2026q1", pytest.approx(1.0), 1), ("2026q2", pytest.approx(1.0), 1)]
