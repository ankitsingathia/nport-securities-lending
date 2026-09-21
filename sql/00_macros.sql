-- Name normaliser used everywhere a counterparty name is compared.
--
-- Filers type the same firm many ways: "BOFA SECURITIES, INC.",
-- "BOFA SECURITIES INC", "Morgan Stanley & Co. LLC (US Equity Sec Lending)".
-- The key keeps only what identifies the firm:
--   1. upper case
--   2. drop anything in brackets (desk or branch notes)
--   3. accents go, dots vanish ("J.P." becomes "JP", "H.S.B.C." becomes "HSBC"),
--      and other punctuation becomes a space
--   4. drop legal-form words and filler (INC, LLC, PLC, CO, THE, AND ...)
--   5. squeeze the spaces
-- It is deliberately blunt. It only ever groups names; the LEI and the GLEIF
-- registry decide which firm a group is (DECISIONS D-03).
create or replace macro name_key(s) as
    trim(regexp_replace(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(strip_accents(upper(coalesce(s, ''))), '\([^)]*\)', ' ', 'g'),
                    '\.', '', 'g'),
                '[^A-Z0-9 ]', ' ', 'g'),
            '\b(INC|INCORPORATED|LLC|L L C|LTD|LIMITED|PLC|CO|CORP|CORPORATION|N A|NA|LP|L P|SA|S A|AG|THE|AND)\b', ' ', 'g'),
        '\s+', ' ', 'g'));

-- Words that identify a firm. Generic banking words are removed, so sharing
-- "SECURITIES" or "LONDON" is not evidence that two names are the same firm.
create or replace macro distinctive(words) as
    list_filter(words, w -> length(w) > 1 and not list_contains([
        'SECURITIES', 'SECURITY', 'BANK', 'BANKING', 'CAPITAL', 'MARKETS', 'MARKET', 'FINANCIAL',
        'FINANCE', 'GLOBAL', 'INTERNATIONAL', 'BRANCH', 'LONDON', 'NEW', 'YORK', 'NY', 'USA', 'US',
        'AMERICAS', 'TRUST', 'GROUP', 'HOLDINGS', 'HOLDING', 'SERVICES', 'PRIME', 'BROKERAGE', 'OF',
        'DE', 'ET', 'CIE', 'LENDING', 'EQUITY', 'SEC', 'REPO', 'GOV', 'GC', 'ENHANCED'], w));

-- "CANADIAN IMPERIAL BANK OF COMMERCE" -> "CIBC", "ROYAL BANK OF CANADA" -> "RBC".
-- Firms are often filed under their initials, which no string distance catches.
create or replace macro initials(words) as
    array_to_string(list_transform(
        list_filter(words, w -> not list_contains(['OF', 'DE', 'THE', 'AND', 'ET'], w)),
        w -> w[1]), '');
