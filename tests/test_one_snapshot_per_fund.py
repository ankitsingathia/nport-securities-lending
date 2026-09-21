"""A fund that files more than once in a posting must be counted exactly once."""

import pytest

from tests.builder import Quarter, build, entity, lei

BARC = lei("BARCLAYSBANKPLC000")
REGISTRY = [entity(BARC, "BARCLAYS BANK PLC")]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    # Two holdings months in one posting. The older one carries the LATER fiscal
    # year end, so ordering by REPORT_ENDING_PERIOD instead of REPORT_DATE would
    # pick the wrong filing.
    old = q.filing("S000000001", "Two Months Fund", 100e6, report_date="30-NOV-2025",
                   filing_date="20-JAN-2026", fiscal_year_end="31-AUG-2026")
    q.lend(old, "BARCLAYS BANK PLC", BARC, 9_000_000)
    new = q.filing("S000000001", "Two Months Fund", 100e6, report_date="28-FEB-2026",
                   filing_date="20-APR-2026", fiscal_year_end="31-MAR-2026")
    q.lend(new, "BARCLAYS BANK PLC", BARC, 4_000_000)

    # An amendment replacing the same month: its figures must win.
    orig = q.filing("S000000002", "Amended Fund", 50e6, report_date="28-FEB-2026", filing_date="20-APR-2026")
    q.lend(orig, "BARCLAYS BANK PLC", BARC, 3_000_000)
    amend = q.filing("S000000002", "Amended Fund", 50e6, report_date="28-FEB-2026", filing_date="15-MAY-2026",
                     sub_type="NPORT-P/A")
    q.lend(amend, "BARCLAYS BANK PLC", BARC, 2_500_000)

    # A late amendment of an older month, filed after the current filing: the
    # holdings date still decides.
    cur = q.filing("S000000003", "Late Amendment Fund", 80e6, report_date="28-FEB-2026", filing_date="20-APR-2026")
    q.lend(cur, "BARCLAYS BANK PLC", BARC, 1_000_000)
    late = q.filing("S000000003", "Late Amendment Fund", 80e6, report_date="30-NOV-2025",
                    filing_date="25-MAY-2026", sub_type="NPORT-P/A")
    q.lend(late, "BARCLAYS BANK PLC", BARC, 7_000_000)
    return build(tmp_path, [q], REGISTRY)


def kept(wh, series):
    return wh.execute("""select report_date::varchar, sub_type, sum(value_on_loan)
                         from exposure join filing_latest using (series_id, report_date)
                         where series_id = ? group by 1, 2""", [series]).fetchall()


def test_each_fund_appears_once(wh):
    assert wh.execute("select count(*), count(distinct series_id) from filing_latest").fetchone() == (3, 3)


def test_the_latest_holdings_date_wins_not_the_fiscal_year_end(wh):
    assert kept(wh, "S000000001") == [("2026-02-28", "NPORT-P", pytest.approx(4_000_000))]


def test_an_amendment_replaces_the_original(wh):
    assert kept(wh, "S000000002") == [("2026-02-28", "NPORT-P/A", pytest.approx(2_500_000))]


def test_a_late_amendment_of_an_older_month_does_not_win(wh):
    assert kept(wh, "S000000003") == [("2026-02-28", "NPORT-P", pytest.approx(1_000_000))]


def test_summing_every_filing_would_have_double_counted(wh):
    naive = wh.execute("select sum(value_on_loan) from borrower_final").fetchone()[0]
    counted = wh.execute("select sum(value_on_loan) from exposure").fetchone()[0]
    assert naive == pytest.approx(26_500_000)
    assert counted == pytest.approx(7_500_000)
