-- One snapshot per fund (DECISIONS D-05).
--
-- A quarterly posting holds everything disseminated in that quarter, so one
-- fund can appear with two holdings months (a late filing for an earlier month
-- alongside the current one) and with amendments that replace an earlier
-- filing. Counting them all double-counts that fund's lending.
--
-- The rule, per fund series: the latest holdings date (REPORT_DATE, the as-of
-- date of the portfolio; REPORT_ENDING_PERIOD is the fiscal year end and can
-- lie in the future), then within that date the latest filing, so an amendment
-- supersedes the original.

create or replace table filing as
select
    s.ACCESSION_NUMBER as accession_number,
    i.SERIES_ID as series_id,
    i.SERIES_NAME as series_name,
    s.SUB_TYPE as sub_type,
    strptime(s.REPORT_DATE, '%d-%b-%Y')::date as report_date,
    strptime(s.FILING_DATE, '%d-%b-%Y')::date as filing_date,
    try_cast(replace(i.NET_ASSETS, ',', '') as double) as net_assets,
    try_cast(replace(i.TOTAL_ASSETS, ',', '') as double) as total_assets
from src."${QUARTER}".submission s
join src."${QUARTER}".fund_reported_info i using (ACCESSION_NUMBER);

create or replace table filing_latest as
select * exclude (rn)
from (
    select *, row_number() over (
        partition by series_id
        order by report_date desc, filing_date desc, accession_number desc) as rn
    from filing)
where rn = 1;

-- Borrower exposure on the latest snapshot only: one row per fund per borrower.
create or replace table exposure as
select f.series_id, f.series_name, f.report_date, f.net_assets, b.*
from borrower_final b
join filing_latest f using (accession_number);
