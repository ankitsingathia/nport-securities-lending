-- Fund-level exposure on each fund's latest snapshot (DECISIONS D-06).
--
-- Counterparty risk is a group question: a fund lending to three JPMorgan
-- entities has one JPMorgan exposure. Borrowers that could not be resolved
-- are kept as their own group under their filed name, never dropped.

create or replace table fund_group_exposure as
select
    series_id,
    any_value(series_name) as series_name,
    any_value(report_date) as report_date,
    any_value(net_assets) as net_assets,
    coalesce(parent_lei, 'UNRESOLVED:' || filed_key) as group_id,
    any_value(coalesce(parent_name, filed_name)) as group_name,
    sum(value_on_loan) as value_on_loan
from exposure
group by series_id, coalesce(parent_lei, 'UNRESOLVED:' || filed_key);

-- Each filing reports lending twice: per borrower (Item B.4) and per holding
-- (Item C.12). The two should agree; a fund where they do not is flagged
-- rather than trusted.
create or replace table holding_loans as
select h.ACCESSION_NUMBER as accession_number,
       sum(try_cast(replace(sl.LOAN_VALUE, ',', '') as double)) as holdings_on_loan
from src."${QUARTER}".securities_lending sl
join src."${QUARTER}".fund_reported_holding h using (HOLDING_ID)
where sl.IS_LOAN_BY_FUND = 'Y'
group by 1;

create or replace table fund_lending as
with per_fund as (
    select
        series_id,
        any_value(series_name) as series_name,
        any_value(report_date) as report_date,
        any_value(net_assets) as net_assets,
        sum(value_on_loan) as borrower_total,
        count(*) as n_groups,
        max(value_on_loan) as top_group_value,
        arg_max(group_name, value_on_loan) as top_group
    from fund_group_exposure
    group by series_id
)
select
    p.*,
    hl.holdings_on_loan,
    p.borrower_total / nullif(p.net_assets, 0) as on_loan_pct_nav,
    p.top_group_value / nullif(p.net_assets, 0) as top_group_pct_nav,
    p.top_group_value / nullif(p.borrower_total, 0) as top_group_share_of_lending,
    case
        when p.net_assets is null or p.net_assets <= 0 then 'nav_missing'
        when hl.holdings_on_loan is null then 'no_holding_detail'
        when abs(p.borrower_total - hl.holdings_on_loan) <= greatest(0.01 * p.borrower_total, 1000) then 'reconciles'
        else 'does_not_reconcile'
    end as reconciliation
from per_fund p
join filing_latest f using (series_id)
left join holding_loans hl on hl.accession_number = f.accession_number;
