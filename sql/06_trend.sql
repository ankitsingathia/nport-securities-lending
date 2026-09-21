-- Trend across quarters, built from the history tables (DECISIONS D-08).
--
-- "Quarter" here is the SEC posting quarter. Each posting holds funds'
-- portfolios as of a spread of recent month-ends, so trend_market records the
-- holdings window (5th to 95th percentile of report dates) for every posting,
-- and no chart should call a posting quarter a calendar quarter.

create or replace table trend_market as
with g as (
    select quarter, parent_lei, sum(value_on_loan) as v
    from hist_exposure where parent_lei is not null group by 1, 2
), s as (
    select quarter, v / sum(v) over (partition by quarter) as sh,
           row_number() over (partition by quarter order by v desc) as r
    from g
), conc as (
    select quarter, round(sum(sh * sh) * 10000) as hhi,
           sum(sh) filter (where r <= 5) as top5_share,
           count(*) as borrower_groups
    from s group by 1
), funds as (
    select quarter,
           count(*) as lending_funds,
           sum(borrower_total) as on_loan_usd,
           sum(cash_collateral + noncash_collateral) / sum(borrower_total) as coverage,
           count(*) filter (where reconciliation = 'reconciles') as funds_reconciling,
           quantile_disc(report_date, 0.05) as holdings_from,
           quantile_disc(report_date, 0.95) as holdings_to
    from hist_fund group by 1
)
select f.*, c.hhi, c.top5_share, c.borrower_groups
from funds f join conc c using (quarter)
order by quarter;

create or replace table trend_groups as
with g as (
    select quarter, parent_lei, any_value(parent_name) as parent_name,
           count(distinct series_id) as funds, sum(value_on_loan) as v
    from hist_exposure where parent_lei is not null group by 1, 2
)
select quarter, parent_lei, parent_name, funds, v as on_loan_usd,
       v / sum(v) over (partition by quarter) as share,
       rank() over (partition by quarter order by v desc) as rank_in_quarter
from g;

create or replace table trend_fund_flags as
select
    series_id,
    any_value(series_name) as series_name,
    count(*) as quarters_seen,
    count(*) filter (where reconciliation = 'reconciles' and on_loan_pct_nav >= 0.33) as quarters_near_ceiling,
    count(*) filter (where reconciliation = 'reconciles' and coverage > 0 and coverage < 0.90) as quarters_below_90pct,
    max(on_loan_pct_nav) filter (where reconciliation = 'reconciles') as max_on_loan_pct_nav,
    min(coverage) filter (where reconciliation = 'reconciles' and coverage > 0) as min_coverage
from hist_fund
group by series_id;
