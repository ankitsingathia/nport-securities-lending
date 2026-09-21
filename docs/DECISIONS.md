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

## D-06 · Fund exposure is measured per borrower group, and only on funds whose two reports agree

`sql/03_fund_exposure.sql` measures each fund on its latest snapshot:
lending as a share of net assets, and its largest single borrower group as a
share of net assets and of its own lending.

- **Group, not entity:** a fund lending to three JPMorgan entities has one
  JPMorgan exposure. Unresolved borrowers stay as their own group under their
  filed name; they are never dropped.
- **Two reports must agree:** a filing states its lending twice, per borrower
  (Item B.4) and per holding (Item C.12). A fund counts only if the two agree
  within 1% (or $1,000). On 2026q2, 4,038 of 4,109 lending funds reconcile,
  covering $337.9bn of $339.0bn. 39 funds ($1.1bn) do not and are flagged, not
  ranked; 32 report borrowers but no holding-level detail.
- **Reading the ceiling:** SEC staff guidance limits a fund's lending to one
  third of total assets, and total assets include the collateral received,
  which puts the practical ceiling at about half of net assets. The largest
  lender on 2026q2 sits at 50.9% of net assets. That is noted as being at the
  ceiling, not as a breach: holdings and net assets are valued at slightly
  different moments, and the filing is not an audit.
- **Result on 2026q2:** the median lending fund has 1.7% of net assets on loan;
  the 99th percentile has 27.8%. Half of lending funds place at least half of
  their lending with one group. The largest single-borrower exposures reach
  49% of net assets (AdvisorShares Dorsey Wright FSM, to Barclays).

## D-07 · Collateral coverage is read with its timing and tagging limits stated

`sql/04_collateral.sql` puts each fund's collateral against its loans. Cash
collateral appears as the holdings it was reinvested in (Item C.12); non-cash
collateral is off balance sheet and reported in aggregate by type (Item B.4.b).

- **Internal consistency:** the 1,725 funds with non-cash collateral rows are
  exactly the 1,725 whose own flag says non-cash collateral was received.
- **Market level, 2026q2:** $270.1bn of cash (reinvested) and $79.3bn of
  non-cash collateral, mostly US Treasuries, against $339.0bn on loan: 103.3%
  coverage. The median fund is at 102.4%, inside the usual 102-105% range.
- **"Under 100%" is not read literally.** 572 funds with $39.5bn on loan are
  below 100%, but loans are re-marked daily and the filing freezes prices
  between marks. Three quarters of that value is within 3 points of full cover.
  The actual shortfall is $1.6bn, about 0.5% of lending, and the meaningful
  gaps sit in 49 funds below 90%.
- **Cash is measured at its reinvested value,** so coverage below 100% can also
  mean a reinvestment lost value. The filing cannot separate the two, and the
  write-up says so.
- **"No collateral recorded" is reported as not visible, not as unsecured.**
  A first version called it a tagging gap, on the grounds that such funds hold
  short-term investment vehicles that were not tagged as collateral. Measured,
  that does not hold for the largest case: GMO Alternative Allocation has
  $216m on loan, no tagged collateral, and only $23m in short-term vehicles;
  GMO Implementation has $217m on loan, $38m tagged and $22m in such vehicles.
  The filings do not show where the rest of the collateral sits. It may be held
  outside the fund's reported holdings, but confirming that needs the funds'
  annual reports, so the write-up states only what the filing shows.

## D-08 · Trends are read by posting quarter, with each posting's holdings window stated

`scripts/resolve.py` runs every quarter through steps 1-5 and
`sql/05_history.sql` stores the results tagged by quarter; `sql/06_trend.sql`
builds the trend tables from them.

- **A posting quarter is not a calendar quarter.** The 2026q2 posting holds
  portfolios dated February to April 2026; 2025q3 holds May to July 2025.
  `trend_market` records the window (5th to 95th percentile of holdings dates)
  for every posting, and charts label postings by that window.
- **The 2026q2 rise is broad, not one fund.** Lending rose from $280.8bn to
  $339.0bn. Funds lending in both postings added $46.1bn, 495 new lenders
  added $14.6bn and 287 that stopped removed $2.5bn. The largest single
  increase was $1.8bn (Vanguard Total International Stock Index).
- **A filer contradicting itself in one quarter.** In 2025q4, 63 funds, almost
  all iShares ETFs, report $25.3bn lent to borrowers while marking every
  position as not on loan (iShares Russell 2000 ETF: 1,981 of 1,981 holdings
  flagged "N" against $11bn lent; 1,011 flagged "Y" the next quarter). Market
  totals come from the borrower section and are unaffected; those funds'
  2025q4 fund-level ratios are excluded as `no_holding_detail`.
- **Placeholder LEIs.** Older quarters include `0000000000`, filed against five
  different banks. Anything not shaped like an LEI is now treated as blank.
- **Persistence is the signal.** A fund near the lending ceiling or short of
  collateral once may be timing; in every one of four postings it is a
  pattern. Three iShares hedged bond ETFs and AlphaCentric Robotics lend 43-47%
  of net assets in all four postings while staying collateralised; two GMO
  funds show about 17% visible collateral in all four.
