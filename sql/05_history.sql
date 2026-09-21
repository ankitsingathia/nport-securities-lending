-- Keep each quarter's results for the trend analysis (DECISIONS D-08).
--
-- Steps 01-04 rebuild their tables for whichever quarter is being run. This
-- step copies the outputs into history tables tagged with the quarter, and
-- replaces that quarter's rows if it is run again, so reruns never duplicate.
-- If a step's columns change, drop the history tables and rerun every quarter.

create table if not exists hist_exposure as
select '${QUARTER}'::varchar as quarter, * from exposure limit 0;
delete from hist_exposure where quarter = '${QUARTER}';
insert into hist_exposure select '${QUARTER}', * from exposure;

create table if not exists hist_fund as
select '${QUARTER}'::varchar as quarter, * from fund_collateral limit 0;
delete from hist_fund where quarter = '${QUARTER}';
insert into hist_fund select '${QUARTER}', * from fund_collateral;

create table if not exists hist_cash_reinvestment as
select '${QUARTER}'::varchar as quarter, c.*, f.series_id
from cash_collateral_holdings c join filing_latest f using (accession_number) limit 0;
delete from hist_cash_reinvestment where quarter = '${QUARTER}';
insert into hist_cash_reinvestment
select '${QUARTER}', c.*, f.series_id
from cash_collateral_holdings c join filing_latest f using (accession_number);
