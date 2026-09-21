-- Collateral against each fund's loans, on its latest snapshot (DECISIONS D-07).
--
-- Cash collateral is not reported as a number received; it shows up as the
-- holdings the cash was reinvested in (Item C.12, IS_CASH_COLLATERAL). Non-cash
-- collateral is held off balance sheet and reported in aggregate by type
-- (Item B.4.b, the BORROW_AGGREGATE table). Coverage is their sum over the
-- value on loan. Because cash is measured at its reinvested value, coverage
-- below 100% can mean a reinvestment has lost value, not only that too little
-- was taken; the report says which it cannot tell apart.

create or replace table cash_collateral_holdings as
select
    h.ACCESSION_NUMBER as accession_number,
    h.ISSUER_NAME as issuer_name,
    nullif(upper(trim(h.ISSUER_LEI)), 'N/A') as issuer_lei,
    h.ASSET_CAT as asset_cat,
    try_cast(replace(sl.CASH_COLLATERAL_AMOUNT, ',', '') as double) as cash_reinvested
from src."${QUARTER}".securities_lending sl
join src."${QUARTER}".fund_reported_holding h using (HOLDING_ID)
where sl.IS_CASH_COLLATERAL = 'Y';

create or replace table fund_collateral as
with cash as (
    select accession_number, sum(cash_reinvested) as cash_collateral
    from cash_collateral_holdings group by 1
), noncash as (
    select ACCESSION_NUMBER as accession_number,
           sum(try_cast(replace(COLLATERAL, ',', '') as double)) as noncash_collateral
    from src."${QUARTER}".borrow_aggregate group by 1
)
select
    f.*,
    coalesce(c.cash_collateral, 0) as cash_collateral,
    coalesce(n.noncash_collateral, 0) as noncash_collateral,
    (coalesce(c.cash_collateral, 0) + coalesce(n.noncash_collateral, 0)) / nullif(f.borrower_total, 0) as coverage
from fund_lending f
join filing_latest fl using (series_id)
left join cash c on c.accession_number = fl.accession_number
left join noncash n on n.accession_number = fl.accession_number;
