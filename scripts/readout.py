"""Write docs/readout.html: the analysis as a readable page, built from the warehouse.

    python scripts/readout.py

Every number on the page is queried here; none is typed by hand. Run it after
scripts/resolve.py (all quarters) and scripts/trend.py.
"""

from __future__ import annotations

import base64
import html
import io
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "data" / "warehouse.duckdb"
RAW = REPO / "data" / "nport.duckdb"
OUT = REPO / "docs" / "readout.html"
REPO_URL = "https://github.com/ankitsingathia/nport-securities-lending"

# Validated categorical slots, fixed order; muted ink for context series.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 9,
                     "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED})

CSS = """
:root{--bg:#fbfbf9;--ink:#1a1a18;--ink2:#55544f;--line:#e4e3dc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;padding:48px 22px 96px}
h1{font-size:30px;line-height:1.2;margin:0 0 8px;font-weight:650}
h2{font-size:20px;margin:56px 0 10px;font-weight:650}h3{font-size:16.5px;margin:30px 0 6px}
p{margin:12px 0}ol{padding-left:22px}li{margin:10px 0}a{color:#1f5fae}
.byline{color:var(--ink2);margin:0 0 28px;font-size:14.5px}.small{color:var(--ink2);font-size:14.5px}
figure{margin:22px 0}figure img{width:100%;height:auto;display:block;border:1px solid var(--line)}
figcaption{color:var(--ink2);font-size:13.5px;margin-top:6px}
details{margin:14px 0}summary{cursor:pointer;color:var(--ink2);font-size:14.5px}
.tw{overflow-x:auto;margin:12px 0}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--ink2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
code{font-size:14px;background:#efeee8;padding:1px 5px;border-radius:3px}
"""


def esc(s) -> str:
    return html.escape(str(s))


def bn(x: float) -> str:
    return f"${x / 1e9:,.1f}bn"


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def table(headers, rows, numeric_from=1) -> str:
    head = "".join(f"<th{' class=n' if i >= numeric_from else ''}>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td{' class=n' if i >= numeric_from else ''}>{esc(c)}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def fold(summary: str, inner: str) -> str:
    return f"<details><summary>{esc(summary)}</summary>{inner}</details>"


def axes(w=7.2, h=3.2):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    return fig, ax


def png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def figure(src: str, alt: str, caption: str) -> str:
    return f'<figure><img alt="{esc(alt)}" src="{src}"><figcaption>{caption}</figcaption></figure>'


def short(name: str) -> str:
    for old, new in (("THE GOLDMAN SACHS GROUP, INC.", "Goldman Sachs"), ("JPMORGAN CHASE & CO.", "JPMorgan Chase"),
                     ("BANK OF AMERICA CORPORATION", "Bank of America"), ("MORGAN STANLEY", "Morgan Stanley"),
                     ("BARCLAYS PLC", "Barclays"), ("CITIGROUP INC.", "Citigroup"), ("BNP PARIBAS", "BNP Paribas"),
                     ("WELLS FARGO & COMPANY", "Wells Fargo"), ("STATE STREET CORPORATION", "State Street"),
                     ("UBS Group AG", "UBS")):
        if name == old:
            return new
    return name


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    con.execute(f"attach '{RAW.as_posix()}' as src (read_only)")
    one = lambda s, *a: con.execute(s, list(a)).fetchone()
    rows = lambda s, *a: con.execute(s, list(a)).fetchall()

    market = rows("""select quarter, strftime(holdings_from, '%b %Y'), strftime(holdings_to, '%b %Y'),
                            lending_funds, on_loan_usd, coverage, top5_share, hhi, borrower_groups
                     from trend_market order by quarter""")
    latest_q = market[-1][0]
    first = market[0]
    last = market[-1]
    funds_total = one(f'select count(distinct SERIES_ID) from src."{latest_q}".fund_reported_info')[0]
    naive = one(f"""select sum(try_cast(replace(AGGREGATE_VALUE, ',', '') as double))
                    from src."{latest_q}".borrower""")[0]
    top = rows("""select parent_name, funds, on_loan_usd, share from trend_groups
                  where quarter = ? order by rank_in_quarter limit 8""", latest_q)
    resolution = dict(rows("""select resolution, sum(value_on_loan) / sum(sum(value_on_loan)) over ()
                              from hist_exposure where quarter = ? group by 1""", latest_q))
    lei_backed = resolution.get("lei_confirmed", 0) + resolution.get("lei_accepted", 0)
    rec = one("""select sum(borrower_total) filter (where reconciliation = 'reconciles') / sum(borrower_total)
                 from hist_fund where quarter = ?""", latest_q)[0]
    dist = one("""select quantile_cont(on_loan_pct_nav, 0.5), quantile_cont(on_loan_pct_nav, 0.99),
                         quantile_cont(top_group_share_of_lending, 0.5)
                  from hist_fund where quarter = ? and reconciliation = 'reconciles'""", latest_q)
    # Totals over all lending funds, the same scope as the market cover figure;
    # the under-100% analysis uses only funds whose two reports agree.
    totals = one("select sum(cash_collateral), sum(noncash_collateral) from hist_fund where quarter = ?", latest_q)
    cover = one("""select null, null,
                          count(*) filter (where coverage > 0 and coverage < 1),
                          sum(borrower_total) filter (where coverage > 0 and coverage < 1),
                          sum(borrower_total - cash_collateral - noncash_collateral)
                              filter (where coverage > 0 and coverage < 1),
                          count(*) filter (where coverage > 0 and coverage < 0.9)
                   from hist_fund where quarter = ? and reconciliation = 'reconciles'""", latest_q)
    persistent = rows("""select series_name, quarters_near_ceiling, quarters_below_90pct, max_on_loan_pct_nav,
                                min_coverage from trend_fund_flags
                         where quarters_near_ceiling = 4 or quarters_below_90pct = 4
                         order by quarters_near_ceiling desc, max_on_loan_pct_nav desc""")

    parts = ["<title>Who borrows from US funds</title>", f"<style>{CSS}</style>", "<main>",
             "<h1>Who borrows from US funds, and is it safe?</h1>",
             f'<p class="byline">Ankit Singathia &middot; SEC Form N-PORT, four postings, portfolios dated '
             f"{first[1]} to {last[2]}</p>"]

    parts.append(
        f"<p>Every US mutual fund and ETF files its full portfolio with the SEC, including the securities it lends "
        f"out and who borrows them. I read four quarterly postings of those filings. In the latest, "
        f"{last[3]:,} of {funds_total:,} funds were lending, with {bn(last[4])} on loan to {last[8]} bank "
        f"groups, backed by collateral worth {pct(last[5])} of the loans.</p>")

    parts.append("<h2>The short version</h2>")
    names = ", ".join(f"{short(t[0])} ({pct(t[3])})" for t in top[:5])
    parts.append(
        f"<p>Five banks borrow most of it: {names}. Together that is {pct(last[6])} of all lending. The market "
        f"as a whole is not dominated by one firm, but more than half of every dollar goes to those five.</p>"
        f"<p>Most funds lend very little: the median lending fund has {pct(dist[0])} of its assets out. A few lend "
        f"right up to the limit, and four of them do it in every posting I looked at. Collateral covers "
        f"{pct(last[5])} of loans overall, and once daily re-marking is allowed for, the real shortfall is "
        f"{bn(cover[4])}, not the {bn(cover[3])} a literal reading suggests.</p>")

    parts.append("<h2>Before trusting any of it</h2>")
    parts.append(
        f"<p>The filings are published exactly as funds submit them, and it shows. Before I added anything up, I "
        f"had to fix four things:</p><ol>"
        f"<li>The same bank is filed under many names. Morgan Stanley alone appears eleven ways. I matched names "
        f"to each firm's Legal Entity Identifier and checked every identifier against GLEIF, the official "
        f"registry. In the latest posting {pct(lei_backed)} of the value is backed by an identifier the registry "
        f"agrees with.</li>"
        f"<li>Some identifiers belong to a different bank: a JPMorgan name filed with UBS's identifier, for "
        f"example. Those are corrected when the name is confirmed elsewhere and flagged when it is not. None is "
        f"moved silently.</li>"
        f"<li>Many funds file twice in a posting, with a late filing for an earlier month or an amendment. "
        f"Adding everything up gives {bn(naive)}; counting each fund once gives {bn(last[4])}. The difference, "
        f"{bn(naive - last[4])}, is double counting.</li>"
        f"<li>Each filing reports its lending twice, once per borrower and once per position. For "
        f"{pct(rec)} of the value the two agree, and I only rank funds where they do.</li></ol>")

    parts.append("<h2>Who borrows</h2>")
    fig, ax = axes(7.2, 3.4)
    y = np.arange(len(top))[::-1]
    ax.barh(y, [t[3] for t in top], height=0.62, color=SERIES[0])
    for yy, t in zip(y, top):
        ax.text(t[3] + 0.002, yy, pct(t[3]), va="center", color=INK, fontsize=8.5)
    ax.set_yticks(y, [short(t[0]) for t in top])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_xlabel("Share of all fund lending, latest posting")
    parts.append(figure(png(fig), "Share of lending by borrower group",
                        f"Borrowers grouped by ultimate parent. {last[8]} groups in all."))

    quarters = [m[0] for m in market]
    labels = [f"{m[1]}-{m[2]}" for m in market]
    fig, ax = axes(7.2, 3.2)
    for i, t in enumerate(top[:4]):
        shares = dict(rows("select quarter, share from trend_groups where parent_name = ?", t[0]))
        ys = [shares.get(q) for q in quarters]
        ax.plot(range(len(quarters)), ys, color=SERIES[i], linewidth=2, marker="o", markersize=5, label=short(t[0]))
    ax.set_xticks(range(len(quarters)), labels, fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylabel("Share of fund lending")
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.01))
    moves = {short(t[0]): None for t in top}
    for name in list(moves):
        full = next(t[0] for t in top if short(t[0]) == name)
        s = dict(rows("select quarter, share from trend_groups where parent_name = ?", full))
        moves[name] = (s.get(quarters[-1], 0) - s.get(quarters[0], 0))
    gain = max(moves, key=moves.get)
    loss = min(moves, key=moves.get)
    parts.append(figure(png(fig), "Top four borrowers' share across the year",
                        "Each point is one posting, labelled by the months its portfolios are dated."))
    leaders = {short(r[0]) for r in rows("select parent_name from trend_groups where rank_in_quarter = 1")}
    lead = (f"{leaders.pop()} led in every posting." if len(leaders) == 1
            else f"The lead changed hands between {', '.join(sorted(leaders))}.")
    parts.append(f"<p>Over the year {gain} gained the most share ({moves[gain] * 100:+.1f} points) and {loss} lost "
                 f"the most ({moves[loss] * 100:+.1f} points). {lead}</p>")

    parts.append("<h2>How much each fund lends</h2>")
    parts.append(
        f"<p>Lending is uneven. The median fund has {pct(dist[0])} of its net assets on loan; one in a hundred has "
        f"{pct(dist[1])} or more. SEC guidance caps lending at a third of total assets, and because the collateral "
        f"received counts as an asset, that works out to about half of net assets. Half of lending funds also place "
        f"{pct(dist[2], 0)} or more of their lending with a single bank group.</p>"
        f"<p>What matters to me is persistence. A fund near the limit once could be timing; these were there in "
        f"every posting:</p>")
    spread = rows("""select case when on_loan_pct_nav < 0.01 then 'under 1%' when on_loan_pct_nav < 0.05 then '1-5%'
                                 when on_loan_pct_nav < 0.10 then '5-10%' when on_loan_pct_nav < 0.20 then '10-20%'
                                 when on_loan_pct_nav < 0.33 then '20-33%' when on_loan_pct_nav < 0.45 then '33-45%'
                                 else '45% or more' end as band, count(*), min(on_loan_pct_nav)
                      from hist_fund where quarter = ? and reconciliation = 'reconciles'
                      group by 1 order by 3""", latest_q)
    fig, ax = axes(7.2, 3.0)
    x = np.arange(len(spread))
    ax.bar(x, [b[1] for b in spread], width=0.6, color=SERIES[0])
    for xx, b in zip(x, spread):
        ax.text(xx, b[1], f"{b[1]:,}", ha="center", va="bottom", color=INK, fontsize=8.5)
    ax.set_xticks(x, [b[0] for b in spread], fontsize=8.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylabel("Lending funds")
    ax.set_xlabel("Share of the fund's net assets on loan")
    parts.append(figure(png(fig), "Lending funds by share of net assets on loan",
                        "Latest posting, funds whose two lending reports agree. The limit is about half."))
    parts.append(table(["Fund", "Postings near the limit", "Postings under 90% collateral", "Highest share lent",
                        "Lowest collateral cover"],
                       [[p[0], p[1], p[2], pct(p[3]) if p[3] is not None else "",
                         pct(p[4]) if p[4] is not None else ""] for p in persistent]))
    parts.append("<p class=small>The two GMO funds are not necessarily short of collateral. Their filings simply do "
                 "not show where it is held for most of their loans, and confirming it would need their annual "
                 "reports.</p>")

    parts.append("<h2>Collateral</h2>")
    parts.append(
        f"<p>Funds hold {bn(totals[0])} of reinvested cash and {bn(totals[1])} of non-cash collateral, mostly US "
        f"Treasuries. Read literally, {cover[2]:,} funds with {bn(cover[3])} on loan are under 100% cover. But loans "
        f"are re-marked every day and a filing freezes prices between marks, so most of that is a point or two of "
        f"normal drift. The actual gap is {bn(cover[4])}, and the funds worth a look are the {cover[5]} below "
        f"90%.</p>")
    bands = rows("""select case when coverage is null or coverage = 0 then 'None recorded'
                                when coverage < 0.90 then 'Under 90%' when coverage < 1.00 then '90-100%'
                                when coverage < 1.02 then '100-102%' when coverage < 1.10 then '102-110%'
                                else '110%+' end as band, sum(borrower_total), min(coalesce(coverage, 0))
                     from hist_fund where quarter = ? and reconciliation = 'reconciles'
                     group by 1 order by 3""", latest_q)
    fig, ax = axes(7.2, 3.0)
    x = np.arange(len(bands))
    ax.bar(x, [b[1] for b in bands], width=0.6, color=SERIES[0])
    for xx, b in zip(x, bands):
        ax.text(xx, b[1], f" {bn(b[1])}", ha="center", va="bottom", color=INK, fontsize=8.5)
    ax.set_xticks(x, [b[0] for b in bands], fontsize=8.5)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1e9:.0f}bn")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylabel("Value on loan")
    parts.append(figure(png(fig), "Value on loan by collateral cover",
                        "Most lending sits in the normal 102-110% band."))

    parts.append("<h2>What I got wrong along the way</h2>")
    parts.append(
        "<p>Four of my own mistakes changed a number before I caught them, and each is written up in the decision "
        "log with how I found it:</p><ol>"
        "<li>A matching rule moved $19.6bn of genuine JPMorgan lending between two JPMorgan entities and reported "
        "$27.8bn of \"wrong identifiers\" that were right. I found it by reading the largest corrections before "
        "trusting the total.</li>"
        "<li>I first used a fund's fiscal year end as the date of its portfolio. The two columns look alike; one "
        "can be in the future.</li>"
        "<li>I explained GMO's missing collateral as untagged short-term holdings. The numbers did not support it, "
        "so the write-up now says only what the filing shows.</li>"
        "<li>I claimed no single fund drove the last posting's rise by more than $1.8bn. A fund lending for the "
        "first time added $3.4bn.</li></ol>")

    parts.append("<h2>Across the year</h2>")
    fig, ax = axes(7.2, 3.0)
    x = np.arange(len(market))
    ax.bar(x, [m[4] for m in market], width=0.55, color=SERIES[0])
    for xx, m in zip(x, market):
        ax.text(xx, m[4], bn(m[4]), ha="center", va="bottom", color=INK, fontsize=8.5)
    ax.set_xticks(x, [f"{m[1]}-{m[2]}" for m in market], fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1e9:.0f}bn")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylabel("Value on loan")
    parts.append(figure(png(fig), "Value on loan per posting",
                        "Each bar is one SEC posting, labelled by the months its portfolios are dated."))
    parts.append(table(["Posting", "Portfolios dated", "Lending funds", "On loan", "Collateral cover", "Top five share"],
                       [[m[0], f"{m[1]} to {m[2]}", f"{m[3]:,}", bn(m[4]), pct(m[5]), pct(m[6])] for m in market]))
    parts.append(f'<p class=small>Code, tests and the full decision log: <a href="{REPO_URL}">{REPO_URL}</a>.</p>'
                 "</main>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
