"""Junk in the LEI field is treated as blank; a real LEI is recognised whatever its case."""

import pytest

from tests.builder import Quarter, build, entity, lei

BARC = lei("BARCLAYSBANKPLC000")
REGISTRY = [entity(BARC, "BARCLAYS BANK PLC")]


@pytest.fixture
def wh(tmp_path):
    q = Quarter()
    f = q.filing("S000000001", "Placeholder Fund", 400e6)
    q.lend(f, "BARCLAYS BANK PLC", BARC, 5_000_000)             # confirms the name
    q.lend(f, "Barclays Bank PLC", "0000000000", 1_000_000)     # seen in the real 2025 filings
    q.lend(f, "BARCLAYS BANK PLC.", "N/A", 1_000_000)
    q.lend(f, "Barclays Bank", "NONE", 1_000_000)
    q.lend(f, "barclays bank plc", BARC.lower(), 1_000_000)     # a real LEI, typed in lower case
    q.lend(f, "Mystery Lender Ltd", "0000000000", 500_000)      # junk LEI and an unknown name
    return build(tmp_path, [q], REGISTRY)


def test_junk_is_never_kept_as_an_lei(wh):
    kept = wh.execute("""select distinct filed_lei from borrower_final where filed_lei is not null""").fetchall()
    assert kept == [(BARC,)]


@pytest.mark.parametrize("filed", ["Barclays Bank PLC", "BARCLAYS BANK PLC.", "Barclays Bank"])
def test_a_blank_lei_is_matched_by_a_confirmed_name(wh, filed):
    resolution, resolved = wh.execute("""select resolution, resolved_lei from borrower_final
                                         where filed_name = ?""", [filed]).fetchone()
    assert (resolution, resolved) == ("matched_by_name", BARC)


def test_a_lower_case_lei_is_recognised(wh):
    resolved = wh.execute("select resolved_lei from borrower_final where filed_name = 'barclays bank plc'").fetchone()
    assert resolved == (BARC,)


def test_junk_with_an_unknown_name_stays_unresolved_but_counted(wh):
    row = wh.execute("""select resolution, parent_lei, value_on_loan from borrower_final
                        where filed_name = 'Mystery Lender Ltd'""").fetchone()
    assert row == ("unresolved", None, pytest.approx(500_000))
