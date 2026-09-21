# Decisions

Every rule a number in this project depends on, why it was chosen, and what was
rejected. If a figure is questioned, the answer starts here.

## D-01 · Downloads identify themselves, back off, and verify what they got

`scripts/download.py` sends a contact address in the User-Agent, pauses between
files, and backs off for 1, 3, 7 and 15 minutes when the SEC returns 403.

- **Why:** the SEC rate-limits automated traffic and answers with a 1.9 KB HTML
  page titled "Request Rate Threshold Exceeded", served under the name of the
  file you asked for. A downloader that trusts the filename saves that page as
  `2026q2_nport.zip` and the failure only surfaces much later, somewhere
  confusing. Every download is opened as a zip before it is kept.
- **Measured on 2026-09-16:** a burst of exploratory requests had this machine
  blocked site-wide for over 26 minutes, on plain HTML pages as well as files.
  Retrying harder extends the block; the only fix is to stop asking.

## D-02 · Load every column as text, clean later in the warehouse

`scripts/ingest.py` discovers whatever files are in the quarterly zip and loads
each one with all columns as `VARCHAR`.

- **Why:** type inference silently rewrites data. A column of identifiers with
  one odd value becomes a float, leading zeros vanish, and a date in an
  unexpected format turns into NULL without anything failing. Loading as text
  keeps the filing exactly as filed, and every cast then happens in SQL where it
  is visible, tested and reversible.
- **Rejected:** letting DuckDB sniff types on the way in. It is faster to write
  and impossible to audit afterwards.

## D-03 · A filed LEI is trusted on evidence, and corrected only when the name rejects it

Borrowers are resolved in `sql/01_resolve_borrowers.sql`. Each row is labelled
with the path it took, so nothing is reassigned silently.

1. **`lei_confirmed`**: the filed name and the GLEIF registry name for the filed
   LEI are near-identical (Jaro-Winkler at least 0.95 on normalised names).
2. **`lei_accepted`**: the filed name shares a distinctive word, or the
   initials, with the registered firm or its parent. This covers branches and
   aliases such as "CIBC NEW YORK" for Canadian Imperial Bank of Commerce.
   Generic words (SECURITIES, BANK, LONDON ...) do not count.
3. **`lei_corrected`**: the name does not support the filed LEI, but is
   confirmed elsewhere for one firm or one group.
4. **`lei_name_conflict`**: none of the above. Flagged, not assigned.

Rows with no LEI are matched by a confirmed name, or left `unresolved`.

- **Why not a similarity threshold:** calibration on 2026q2 showed correct
  branches scoring as low as wrong LEIs. "CIBC NEW YORK" against its own
  registry name scores 0.59; "JP MORGAN SECURITIES LLC" filed with UBS AG's LEI
  scores 0.46. No single cut-off separates them.
- **Why the order matters:** a first version applied corrections before checking
  whether the name supported the filed LEI. It moved $19.6bn of genuine
  J.P. Morgan Securities LLC lending to J.P. Morgan Securities plc, because
  stripping "LLC" and "PLC" made the two share a name key, and it reported
  $27.8bn of "wrong LEIs" that were in fact right. Found by reading the
  largest corrections before quoting the total. A filed LEI the name supports
  is now never overridden.
- **Result on 2026q2:** 94.1% of borrower rows confirmed and 5.0% accepted as
  branches or aliases; 22 rows ($0.1bn) flagged as conflicts; 0.2% unresolved.
- **Normalising names:** accents are removed and dots deleted before other
  punctuation becomes a space, so "J.P." and "JP" match, and so do "H.S.B.C."
  and "HSBC". The normaliser only groups candidates; the LEI decides the entity.

## D-04 · Roll up through successors and head offices before finding the parent

`scripts/fetch_gleif.py` follows each LEI to the entity that counts before
asking GLEIF for its ultimate parent:

- a **duplicate or retired** LEI goes to its registered successor (BNP Paribas
  Securities Corp.'s duplicate LEI reaches BNP Paribas this way);
- a **branch** LEI goes to its head office. Funds report J.P. Morgan Securities
  plc under its Paris branch LEI as well as its London one, and without this
  step JPMorgan's exposure would split across two groups.

**Lapsed** LEIs (not renewed) are kept as they are: the firm still exists. They
are flagged in the audit. On 2026q2, Janney Montgomery Scott ($0.6bn) and TD
Prime Services ($0.2bn) are filed under lapsed LEIs.

## D-05 · One snapshot per fund: latest holdings date, then latest filing

A quarterly posting holds everything disseminated in the quarter. On 2026q2,
12,945 funds made 14,416 filings: 677 funds appear more than once, 393 with two
holdings months, 70 with an amendment replacing the same month, and 213 with
both. `sql/02_latest_filing.sql` keeps, per fund series, the latest holdings
date and within it the latest filing, so an amendment supersedes the original.

- **The date that matters is `REPORT_DATE`**, the as-of date of the portfolio.
  `REPORT_ENDING_PERIOD` is the fund's fiscal year end and can lie in the future
  (31 August 2026 on a February 2026 portfolio). The first version of this check
  used it by mistake.
- **Effect:** total lending falls from $383.6bn to $339.0bn. Summing the posting
  as-is overstates the market by $44.6bn, or 11.6%.
- **Comparability:** 99.9% of funds' latest holdings fall between February and
  April 2026, so one snapshot per fund is a consistent cross-section.
