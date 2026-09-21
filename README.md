# Securities Lending Exposure in US Funds

An analysis of who borrows securities from US mutual funds and ETFs, how
concentrated that borrowing is, and whether it is adequately collateralised.
Built on the SEC's Form N-PORT data sets, which disclose every registered fund's
portfolio, its securities lending, and each borrower by name and Legal Entity
Identifier (LEI). Four quarterly postings are covered, with portfolios dated
May 2025 to April 2026.

[Decision log](docs/DECISIONS.md)

| Funds filing | Lending funds | On loan | Borrower groups | Top five borrowers | Collateral cover |
|---:|---:|---:|---:|---:|---:|
| 12,944 | 4,109 | $339.0bn | 58 | 58.4% | 103.1% |

*Latest posting (2026 Q2, portfolios dated February to April 2026).*

## Key findings

1. **Five banks borrow most of what US funds lend.** Barclays (14.6%),
   JPMorgan (12.6%), Morgan Stanley (11.9%), Goldman Sachs (11.0%) and
   Citigroup (8.3%) take 58.4% of all lending. The overall market is not
   dominated by one firm (HHI 864, below the 1,000 mark regulators treat as
   unconcentrated), but more than half of every dollar lent goes to five
   groups.
2. **A simple sum of the filings overstates the market by $44.6bn.** 677
   funds file more than once in a posting, with a second holdings month or an
   amendment. Counting each fund once brings the 2026 Q2 total from $383.6bn
   to $339.0bn, 11.6% lower.
3. **Lending grew 23% over the year, and the growth was broad.** It rose from
   $275.7bn (portfolios dated May to July 2025) to $339.0bn. In the last
   posting, funds already lending added $46.1bn and 495 new lenders added
   $14.6bn. The largest single contribution was $3.4bn, from a fund lending
   for the first time (Invesco S&P 500 Equal Weight ETF).
   JPMorgan gained the most share over the year (+1.9 points), while Bank of
   America and State Street each lost about 1.5 points.
4. **Most funds lend little, but a few lend right up to the limit.** The
   median lending fund has 1.7% of its net assets on loan and the 99th
   percentile 27.8%. SEC guidance caps lending at about half of net assets
   once collateral is counted. Four funds sit between 43% and 47% in every one
   of the four postings: three iShares hedged bond ETFs and AlphaCentric
   Robotics and Automation.
5. **Half of lending funds rely on a single borrower for most of their
   lending.** The median fund places 51% of its lending with one bank group.
   The largest single exposures reach 49% of a fund's net assets, in
   AdvisorShares Dorsey Wright FSM, lent entirely to Barclays.
6. **Collateral cover is healthy overall, and the real gaps are small.** Funds
   hold $270bn of reinvested cash and $79bn of non-cash collateral, mostly US
   Treasuries: 103.1% of what is on loan. Read literally, 572 funds with
   $39.5bn on loan are below 100%, but loans are re-marked daily and three
   quarters of that value is within three points of full cover. The actual
   shortfall is $1.6bn, concentrated in 49 funds below 90%.
7. **Cash collateral is pooled into a handful of vehicles.** BlackRock's
   vehicles hold about 28% of all reinvested cash collateral, Fidelity 12.6%
   and Vanguard 12.2%. A problem in one vehicle would reach hundreds of funds
   at once.

## Recommendations

| Priority | Action | Basis |
|---|---|---|
| 1 | Monitor the four funds that lend 43-47% of net assets in every posting | They sit persistently just under the roughly 50% ceiling |
| 2 | Review the 49 funds below 90% collateral cover, and request collateral detail from GMO | $1.6bn actual shortfall; GMO's filings do not show where collateral for about $0.5bn of loans is held |
| 3 | Measure counterparty exposure at parent-group level, resolved through the GLEIF registry | Grouping by LEI alone splits JPMorgan across a London entity and a Paris branch |
| 4 | Add a consistency check to filing review that compares borrower totals with position-level flags | iShares filings for 2025 Q4 report $25.3bn lent while marking every position as not on loan |
| 5 | Track concentration in cash-collateral reinvestment vehicles | About 28% of reinvested cash sits in BlackRock vehicles |

## Data problems found and handled

N-PORT is filed by the funds themselves and published as filed. Every problem
below was measured on the real data before any figure was quoted:

| Issue | Evidence | Handling |
|---|---|---|
| One firm, many spellings | 307 borrower names but 112 LEIs in 2026 Q2; Morgan Stanley alone is filed 11 ways | Names are normalised only to group candidates; the LEI, checked against the GLEIF registry, decides the entity |
| A valid LEI belonging to another firm | "JP MORGAN SECURITIES LLC" filed with UBS AG's LEI; 22 rows ($0.1bn) in 2026 Q2 have no supporting evidence | Corrected when the name is confirmed elsewhere for another group, otherwise flagged and kept, never silently reassigned |
| Branch and replaced LEIs | JPMorgan Securities plc is also filed under its Paris branch LEI; duplicate and retired LEIs are still in use | Followed through GLEIF to the head office or successor before the ultimate parent is found |
| Funds filing more than once | 677 funds in 2026 Q2, with a second holdings month or an amendment | One snapshot per fund: the latest holdings date, then the latest filing; removes $44.6bn of double counting |
| Two dates that look alike | `REPORT_ENDING_PERIOD` is the fiscal year end and can lie in the future | `REPORT_DATE`, the portfolio's as-of date, is used throughout |
| A filing contradicting itself | In 2025 Q4, 63 funds (almost all iShares ETFs) report $25.3bn lent while marking every position as not on loan | Market totals use the borrower section; those funds' fund-level ratios are excluded for that quarter |
| Placeholder identifiers | `0000000000` filed as an LEI against five different banks | Anything not shaped like an LEI is treated as blank and matched by name |
| Collateral not visible | GMO funds' filings do not show collateral for about $0.5bn of loans | Reported as not visible, not as unsecured; confirming it needs the funds' annual reports |

Each rule, and the alternatives rejected, is recorded in
[docs/DECISIONS.md](docs/DECISIONS.md). Five of the entries describe errors in
earlier versions of this analysis and how they were caught.

## Limitations

- **Filings are not audited.** Figures are as reported by each fund.
- **A posting is not a calendar quarter.** Each posting holds funds' latest
  month-end portfolios, so the 2026 Q2 posting covers February to April 2026.
  Every trend figure is labelled with its holdings window.
- **Cash collateral is measured at its reinvested value.** Cover below 100%
  can mean too little was taken or that a reinvestment lost value; the filing
  cannot tell the two apart.
- **Exposure is to a borrower group, before netting.** Offsetting positions
  between a fund and the same bank elsewhere are not visible in N-PORT.

## Method

| Stage | Implementation |
|---|---|
| Download | Quarterly zips from the SEC, 400-470 MB each. The SEC refuses scripted clients (curl and Python return 403 on every network tried), so files are fetched in a browser or by the `fetch-nport.yml` GitHub Actions workflow |
| Ingest | `scripts/ingest.py` loads all 32 tables into DuckDB with every column as text, so no value is coerced on the way in |
| Registry | `scripts/fetch_gleif.py` looks up each borrower LEI in GLEIF and follows successors and head offices to the ultimate parent |
| Resolution | `sql/01_resolve_borrowers.sql` assigns each borrower row an entity on evidence and labels the path it took |
| One snapshot per fund | `sql/02_latest_filing.sql`, a `ROW_NUMBER()` over holdings date and filing date |
| Exposure | `sql/03_fund_exposure.sql` measures exposure per borrower group and reconciles the two lending reports in each filing (99.7% of value agrees) |
| Collateral | `sql/04_collateral.sql` adds reinvested cash and non-cash collateral against loans |
| History and trend | `sql/05_history.sql`, `sql/06_trend.sql` and `scripts/trend.py` compare the four postings |
| Tests | 55 tests run the real SQL on small built quarters with planted problems, with no network access |

**Stack:** DuckDB SQL, Python, the GLEIF API, pytest, GitHub Actions.

## Reproducing the analysis

```bash
pip install -r requirements.txt
python -m pytest                  # 55 tests, no data or network needed
```

For the real data, download the quarterly zips from
[sec.gov](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)
into `data/raw/`, then:

```bash
python scripts/ingest.py 2026q2          # repeat for each quarter
python scripts/fetch_gleif.py 2026q2 2026q1 2025q4 2025q3
python scripts/resolve.py 2025q3 2025q4 2026q1 2026q2
python scripts/trend.py
```

## Repository structure

```
scripts/     download, ingest, registry lookups, pipeline runner, trend report
sql/         the warehouse steps, 00 to 06, each documented at the top
tests/       the test builder and one file per data problem
docs/        decision log
.github/     the SEC download workflow
```
