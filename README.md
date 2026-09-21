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
