-- Resolve every filed borrower to a legal entity (LEI) and a parent group.
-- Needs the macros in 00_macros.sql, the raw quarter attached as `src`, and
-- data/gleif/entities.csv from scripts/fetch_gleif.py. ${QUARTER} and
-- ${MATCH} are filled in by scripts/resolve.py. Rules: DECISIONS D-03.
--
-- A string-similarity threshold alone cannot do this. Calibration on 2026q2:
-- branches and initials score low but are right ("CIBC NEW YORK" vs Canadian
-- Imperial Bank of Commerce, 0.59), while some wrong LEIs score similarly
-- ("JP MORGAN SECURITIES LLC" filed with UBS AG's LEI, 0.46). So a filed LEI is
-- kept, corrected or flagged on evidence, in this order:
--   1 lei_confirmed   filed name and registry name are near-identical
--   2 lei_accepted    the name shares a distinctive word, or the initials, with
--                     the registered firm or its parent (a branch or alias)
--   3 lei_corrected   the name does not support the filed LEI, but is confirmed
--                     elsewhere for one firm or one group
-- A filed LEI the name supports is never overridden. An earlier version
-- corrected first and moved $19.6bn of genuine J.P. Morgan Securities LLC
-- lending to J.P. Morgan Securities plc; rule order is the safeguard.
--   5 lei_name_conflict  none of the above: flagged, not assigned
-- Rows with no LEI are matched by a confirmed name, or left unresolved.

create or replace table gleif as
select lei, legal_name, registration_status, country, parent_lei, parent_name, parent_basis,
       name_key(legal_name) as gleif_key, name_key(parent_name) as parent_key
from read_csv('data/gleif/entities.csv', header = true, all_varchar = true);

create or replace table borrower_filed as
select
    ACCESSION_NUMBER as accession_number,
    BORROWER_ID as borrower_id,
    trim(NAME) as filed_name,
    name_key(NAME) as filed_key,
    case when upper(trim(coalesce(LEI, ''))) in ('', 'N/A', 'NA', 'NONE') then null
         else upper(trim(LEI)) end as filed_lei,
    try_cast(replace(AGGREGATE_VALUE, ',', '') as double) as value_on_loan
from src."${QUARTER}".borrower;

create or replace table borrower_scored as
select
    f.*,
    g.legal_name as filed_lei_registry_name,
    g.registration_status as filed_lei_status,
    g.parent_lei as filed_lei_parent,
    case when g.lei is null then null else jaro_winkler_similarity(f.filed_key, g.gleif_key) end
        as lei_name_similarity,
    g.lei is not null and (
        list_has_any(distinctive(string_split(f.filed_key, ' ')),
                     distinctive(string_split(g.gleif_key, ' ') || string_split(g.parent_key, ' ')))
        or (length(initials(string_split(g.gleif_key, ' '))) >= 2
            and list_contains(string_split(f.filed_key, ' '), initials(string_split(g.gleif_key, ' '))))
        or (length(initials(string_split(g.parent_key, ' '))) >= 2
            and list_contains(string_split(f.filed_key, ' '), initials(string_split(g.parent_key, ' '))))
    ) as name_supports_lei
from borrower_filed f
left join gleif g on g.lei = f.filed_lei;

-- Name keys tied to an LEI by near-identical matches only.
create or replace table key_candidates as
select s.filed_key,
       count(distinct s.filed_lei) as n_leis,
       min(s.filed_lei) as only_lei,
       count(distinct g.parent_lei) as n_parents,
       min(g.parent_lei) as only_parent
from borrower_scored s
join gleif g on g.lei = s.filed_lei
where s.lei_name_similarity >= ${MATCH}
group by s.filed_key;

create or replace table borrower_resolved as
select
    s.*,
    case
        when s.lei_name_similarity >= ${MATCH} then 'lei_confirmed'
        when s.name_supports_lei then 'lei_accepted'
        -- only a filed LEI the name does NOT support can be overridden
        when s.filed_lei_registry_name is not null and (k.n_leis = 1 or k.n_parents = 1) then 'lei_corrected'
        when s.filed_lei is not null and s.filed_lei_registry_name is null then 'lei_not_in_registry'
        when s.filed_lei is not null then 'lei_name_conflict'
        when k.n_leis = 1 then 'matched_by_name'
        when k.n_parents = 1 then 'parent_by_name'
        else 'unresolved'
    end as resolution,
    k.only_lei as key_lei,
    k.n_leis as key_n_leis,
    k.only_parent as key_parent
from borrower_scored s
left join key_candidates k on k.filed_key = s.filed_key;

create or replace table borrower_final as
select
    r.* exclude (key_lei, key_n_leis, key_parent),
    case
        when r.resolution in ('lei_confirmed', 'lei_accepted') then r.filed_lei
        when r.resolution in ('lei_corrected', 'matched_by_name') and r.key_n_leis = 1 then r.key_lei
    end as resolved_lei,
    case
        when r.resolution in ('lei_confirmed', 'lei_accepted') then r.filed_lei_parent
        when r.resolution in ('lei_corrected', 'matched_by_name', 'parent_by_name') then r.key_parent
    end as parent_lei
from borrower_resolved r;

create or replace table borrower_final as
select b.*, g.legal_name as resolved_name, coalesce(p.legal_name, pp.parent_name) as parent_name
from borrower_final b
left join gleif g on g.lei = b.resolved_lei
left join gleif p on p.lei = b.parent_lei
left join (select parent_lei, any_value(parent_name) as parent_name from gleif group by 1) pp
       on pp.parent_lei = b.parent_lei;
