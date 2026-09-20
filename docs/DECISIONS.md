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
