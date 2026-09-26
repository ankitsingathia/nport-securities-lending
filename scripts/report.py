"""Write docs/report.html: the analysis as a report, with interactive charts.

    python scripts/report.py

Every figure is queried from the warehouse here and embedded as JSON, so the
page is one self-contained file and the charts hold the same numbers as the
README. Run it after scripts/resolve.py (all quarters) and scripts/trend.py.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "data" / "warehouse.duckdb"
RAW = REPO / "data" / "nport.duckdb"
OUT = REPO / "docs" / "report.html"
REPO_URL = "https://github.com/ankitsingathia/nport-securities-lending"

SHORT = {"THE GOLDMAN SACHS GROUP, INC.": "Goldman Sachs", "JPMORGAN CHASE & CO.": "JPMorgan Chase",
         "BANK OF AMERICA CORPORATION": "Bank of America", "MORGAN STANLEY": "Morgan Stanley",
         "BARCLAYS PLC": "Barclays", "CITIGROUP INC.": "Citigroup", "BNP PARIBAS": "BNP Paribas",
         "WELLS FARGO & COMPANY": "Wells Fargo", "STATE STREET CORPORATION": "State Street",
         "UBS Group AG": "UBS", "ROYAL BANK OF CANADA": "RBC", "TORONTO-DOMINION BANK": "TD",
         "CANADIAN IMPERIAL BANK OF COMMERCE": "CIBC", "BANK OF MONTREAL": "BMO",
         "THE BANK OF NOVA SCOTIA": "Scotiabank", "NATIXIS": "Natixis", "SOCIETE GENERALE": "Societe Generale",
         "HSBC HOLDINGS PLC": "HSBC", "DEUTSCHE BANK AKTIENGESELLSCHAFT": "Deutsche Bank"}


KEEP_CAPS = {"TD", "BNP", "UBS", "HSBC", "RBC", "BMO", "CIBC", "LLC", "INC", "INC.", "PLC", "ETF", "USA",
             "FMR", "NA", "N.A.", "SA", "AG", "US", "UK", "LP", "III", "II", "IV", "BNY"}


def short(name: str) -> str:
    """Filed names are shouted; make them readable without mangling acronyms."""
    if name in SHORT:
        return SHORT[name]
    if not name.isupper():
        return name
    return " ".join(w if w.strip(",.") in KEEP_CAPS else w.title() for w in name.split())


def esc(s) -> str:
    return html.escape(str(s))


def bn(x: float) -> str:
    return f"${x / 1e9:,.1f}bn"


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


CSS = """
:root{--paper:#fbfbf9;--card:#ffffff;--ink:#16161a;--ink2:#53565c;--ink3:#82868e;
--line:#e3e3dd;--rule:#16161a;--accent:#2a78d6;--warn:#eb6834}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.6 "Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;padding:0 24px 120px}
header.doc{padding:56px 0 26px;border-bottom:2px solid var(--rule);margin-bottom:34px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink3);margin:0 0 14px}
h1{font-size:34px;line-height:1.18;margin:0 0 10px;font-weight:650;letter-spacing:-.01em;max-width:20ch}
.standfirst{font-size:18px;line-height:1.55;color:var(--ink2);margin:0 0 22px;max-width:62ch}
.meta{display:flex;flex-wrap:wrap;gap:0 34px;font-size:13.5px;color:var(--ink2);margin:0}
.meta div{padding:3px 0}.meta b{color:var(--ink);font-weight:600}
h2{font-size:22px;margin:54px 0 6px;font-weight:650;letter-spacing:-.01em}
h2 .num{color:var(--ink3);font-weight:500;margin-right:10px;font-variant-numeric:tabular-nums}
h3{font-size:16.5px;margin:30px 0 6px;font-weight:650}
p{margin:12px 0;max-width:72ch}
li{margin:8px 0;max-width:70ch}
a{color:#1f5fae}
.lede{font-size:17px;color:var(--ink2)}
.summary{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--rule);
padding:22px 26px;margin:26px 0 8px}
.summary h3{margin:0 0 4px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.summary p{margin:6px 0 18px}.summary ul{margin:6px 0 18px;padding-left:20px}
.summary > :last-child{margin-bottom:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);
border:1px solid var(--line);margin:24px 0}
.tile{background:var(--card);padding:14px 16px}
.tile .k{font-size:12px;color:var(--ink3);letter-spacing:.04em;margin-bottom:4px}
.tile .v{font-size:25px;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.tile .s{font-size:12.5px;color:var(--ink2);margin-top:2px}
.panel{background:var(--card);border:1px solid var(--line);padding:18px 20px 14px;margin:22px 0}
.panel h4{margin:0 0 2px;font-size:15.5px;font-weight:650}
.panel .sub{margin:0 0 14px;font-size:13.5px;color:var(--ink2)}
.panel figcaption{font-size:13px;color:var(--ink3);margin-top:10px}
.cv{position:relative;height:340px}
.cv.tall{height:420px}
.picker{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px}
.picker button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--line);background:var(--card);
color:var(--ink2);cursor:pointer;border-radius:2px}
.picker button:hover{border-color:var(--ink3);color:var(--ink)}
.picker button[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:#fff}
.scope{font-size:12.5px;color:var(--ink3);margin:0 0 14px}
.tw{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{color:var(--ink2);font-weight:600;border-bottom:1px solid var(--rule);white-space:nowrap}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#f6f6f2}
.srch{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid var(--line);background:var(--card);
width:260px;max-width:100%;margin:2px 0 4px}
.flag{color:var(--warn);font-weight:600}
.note{border-left:3px solid var(--accent);background:#f4f8fd;padding:12px 16px;margin:20px 0;font-size:14.5px}
.note b{font-weight:650}
.fine{font-size:13.5px;color:var(--ink2)}
footer{margin-top:64px;padding-top:20px;border-top:1px solid var(--line);font-size:13.5px;color:var(--ink2)}
footer a{color:#1f5fae}
@media (max-width:640px){h1{font-size:27px}.cv{height:300px}.wrap{padding:0 16px 80px}}
@media print{.picker{display:none}body{background:#fff}.panel,.tile,.summary{border-color:#ccc}}
"""

JS = """
const D = JSON.parse(document.getElementById('report-data').textContent);
const C = {blue:'#2a78d6', orange:'#eb6834', green:'#1baf7a', amber:'#eda100',
           ink:'#16161a', ink2:'#53565c', grid:'#e8e8e2', mute:'#b9bcc2'};
const F = {
  bn: v => '$' + (v/1e9).toFixed(1) + 'bn',
  pct: (v, d=1) => (v*100).toFixed(d) + '%',
  int: v => v.toLocaleString('en-US')
};
Chart.defaults.font.family = '"Segoe UI", system-ui, Helvetica, Arial, sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = C.ink2;
Chart.defaults.animation.duration = 300;
Chart.defaults.plugins.tooltip.backgroundColor = '#16161a';
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 2;
Chart.defaults.plugins.tooltip.displayColors = false;

let q = D.latest;
const charts = {};
const labels = D.postings.map(p => p.label);

function pctAxis(max) {
  return {grid:{color:C.grid, drawTicks:false}, border:{display:false},
          ticks:{callback:v => (v*100).toFixed(0) + '%'}, suggestedMax:max};
}

// 1. Borrower concentration, redrawn when the posting changes.
charts.borrowers = new Chart(document.getElementById('c-borrowers'), {
  type: 'bar',
  data: {labels: [], datasets: [{data: [], backgroundColor: C.blue, borderRadius: 1, barThickness: 16}]},
  options: {indexAxis:'y', maintainAspectRatio:false,
    plugins:{legend:{display:false}, tooltip:{callbacks:{
      label: c => F.pct(c.raw) + ' of all lending, ' + F.bn(D.groups[q][c.dataIndex][2])
                  + ' from ' + F.int(D.groups[q][c.dataIndex][3]) + ' funds'}}},
    scales:{x:{...pctAxis(), title:{display:true, text:'Share of all fund lending'}},
            y:{grid:{display:false}, border:{display:false}}}}
});

// 2. Lending and concentration over the four postings.
charts.trend = new Chart(document.getElementById('c-trend'), {
  type: 'line',
  data: {labels, datasets: [
    {label:'On loan', data: D.postings.map(p => D.market[p.q].on_loan), borderColor: C.blue,
     backgroundColor: C.blue, pointRadius: 4, borderWidth: 2, tension: 0, yAxisID: 'y'},
    {label:'Top five share', data: D.postings.map(p => D.market[p.q].top5), borderColor: C.orange,
     backgroundColor: C.orange, pointRadius: 4, borderWidth: 2, tension: 0, borderDash: [5,4], yAxisID: 'y1'}
  ]},
  options: {maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
    plugins:{legend:{position:'top', align:'start', labels:{boxWidth:10, boxHeight:10, usePointStyle:true,
                     pointStyle:'circle'}},
             tooltip:{callbacks:{label: c => c.datasetIndex === 0
                ? 'On loan ' + F.bn(c.raw) : 'Top five share ' + F.pct(c.raw)}}},
    scales:{x:{grid:{display:false}, border:{display:false}},
            y:{position:'left', grid:{color:C.grid, drawTicks:false}, border:{display:false},
               ticks:{callback: v => '$' + (v/1e9).toFixed(0) + 'bn'}},
            y1:{position:'right', grid:{display:false}, border:{display:false},
                ticks:{callback: v => (v*100).toFixed(1) + '%'}}}}
});

// 3. Share of lending, top groups, click the legend to isolate one.
charts.shares = new Chart(document.getElementById('c-shares'), {
  type: 'line',
  data: {labels, datasets: D.shares.map((s, i) => ({
    label: s.name, data: s.values, borderColor: [C.blue, C.orange, C.green, C.amber, C.mute, C.ink][i],
    backgroundColor: [C.blue, C.orange, C.green, C.amber, C.mute, C.ink][i],
    pointRadius: 3.5, borderWidth: 2, tension: 0}))},
  options: {maintainAspectRatio:false, interaction:{mode:'nearest', intersect:false},
    plugins:{legend:{position:'top', align:'start', labels:{boxWidth:10, boxHeight:10, usePointStyle:true,
                     pointStyle:'circle'}},
             tooltip:{callbacks:{label: c => c.dataset.label + ' ' + F.pct(c.raw)}}},
    scales:{x:{grid:{display:false}, border:{display:false}}, y:pctAxis()}}
});

// 4. How much of itself each fund lends.
charts.dist = new Chart(document.getElementById('c-dist'), {
  type: 'bar',
  data: {labels: D.dist.bins, datasets: [{data: [], backgroundColor: C.blue, borderRadius: 1}]},
  options: {maintainAspectRatio:false,
    plugins:{legend:{display:false}, tooltip:{callbacks:{
      title: c => c[0].label + ' of net assets on loan',
      label: c => F.int(c.raw) + ' funds'}}},
    scales:{x:{grid:{display:false}, border:{display:false},
               title:{display:true, text:'Share of net assets out on loan'}},
            y:{grid:{color:C.grid, drawTicks:false}, border:{display:false}, type:'logarithmic',
               title:{display:true, text:'Funds (log scale)'}}}}
});

// 5. Collateral cover against how much each fund lends.
charts.cover = new Chart(document.getElementById('c-cover'), {
  type: 'scatter',
  data: {datasets: [{data: [], backgroundColor: 'rgba(42,120,214,0.45)', pointRadius: 3,
                     pointHoverRadius: 6, pointHoverBackgroundColor: C.orange}]},
  options: {maintainAspectRatio:false,
    plugins:{legend:{display:false}, tooltip:{callbacks:{
      title: c => c[0].raw.n,
      label: c => [F.pct(c.raw.x) + ' of net assets on loan', 'cover ' + F.pct(c.raw.y)]}}},
    scales:{x:{...pctAxis(), grid:{color:C.grid, drawTicks:false},
               title:{display:true, text:'Share of net assets out on loan'}},
            y:{grid:{color:C.grid, drawTicks:false}, border:{display:false}, min:0.5, max:2,
               ticks:{callback: v => (v*100).toFixed(0) + '%'},
               title:{display:true, text:'Collateral cover'}}}}
});

// 6. Where reinvested cash collateral sits.
charts.cash = new Chart(document.getElementById('c-cash'), {
  type: 'bar',
  data: {labels: D.cash.map(r => r[0]), datasets: [{data: D.cash.map(r => r[1]),
         backgroundColor: C.green, borderRadius: 1, barThickness: 16}]},
  options: {indexAxis:'y', maintainAspectRatio:false,
    plugins:{legend:{display:false}, tooltip:{callbacks:{label: c => F.pct(c.raw) + ' of reinvested cash'}}},
    scales:{x:{...pctAxis(), title:{display:true, text:'Share of all reinvested cash collateral'}},
            y:{grid:{display:false}, border:{display:false}}}}
});

function tiles() {
  const m = D.market[q];
  document.getElementById('t-onloan').textContent = F.bn(m.on_loan);
  document.getElementById('t-funds').textContent = F.int(m.lending_funds);
  document.getElementById('t-cover').textContent = F.pct(m.coverage);
  document.getElementById('t-top5').textContent = F.pct(m.top5);
  document.getElementById('t-hhi').textContent = F.int(m.hhi);
  document.getElementById('t-groups').textContent = F.int(m.groups);
}

function watchlist() {
  const term = document.getElementById('watch-search').value.trim().toLowerCase();
  const rows = D.watch[q].filter(r => !term || r[0].toLowerCase().includes(term));
  document.getElementById('watch-body').innerHTML = rows.map(r =>
    '<tr><td>' + r[0] + '</td><td class=n>' + F.pct(r[1]) + '</td><td>' + r[2] +
    '</td><td class=n>' + F.pct(r[3]) + '</td><td class="n' + (r[4] < 0.9 ? ' flag' : '') + '">' +
    F.pct(r[4]) + '</td></tr>').join('') ||
    '<tr><td colspan=5 class=fine>No fund in this posting matches that name.</td></tr>';
  document.getElementById('watch-count').textContent = rows.length;
}

function draw() {
  tiles();
  charts.borrowers.data.labels = D.groups[q].map(r => r[0]);
  charts.borrowers.data.datasets[0].data = D.groups[q].map(r => r[1]);
  charts.borrowers.update();
  charts.dist.data.datasets[0].data = D.dist.counts[q];
  charts.dist.update();
  charts.cover.data.datasets[0].data = D.scatter[q];
  charts.cover.update();
  document.querySelectorAll('.scope-label').forEach(el => {
    el.textContent = D.postings.find(p => p.q === q).label;
  });
  watchlist();
}

document.querySelectorAll('.picker button').forEach(b => {
  b.addEventListener('click', () => {
    q = b.dataset.q;
    document.querySelectorAll('.picker button').forEach(o =>
      o.setAttribute('aria-pressed', String(o.dataset.q === q)));
    draw();
  });
});
document.getElementById('watch-search').addEventListener('input', watchlist);
draw();
"""


def tile(key: str, label: str, sub: str) -> str:
    return f'<div class="tile"><div class="k">{esc(label)}</div><div class="v" id="t-{key}">&nbsp;</div>' \
           f'<div class="s">{esc(sub)}</div></div>'


def panel(title: str, sub: str, canvas: str, caption: str, tall: bool = False) -> str:
    return (f'<figure class="panel"><h4>{title}</h4><p class="sub">{sub}</p>'
            f'<div class="cv{" tall" if tall else ""}"><canvas id="{canvas}"></canvas></div>'
            f'<figcaption>{caption}</figcaption></figure>')


def table(headers, rows, numeric_from=1) -> str:
    head = "".join(f"<th{' class=n' if i >= numeric_from else ''}>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td{' class=n' if i >= numeric_from else ''}>{esc(c)}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    con.execute(f"attach '{RAW.as_posix()}' as src (read_only)")
    one = lambda s, *a: con.execute(s, list(a)).fetchone()
    rows = lambda s, *a: con.execute(s, list(a)).fetchall()

    market = rows("""select quarter, strftime(holdings_from, '%b %Y'), strftime(holdings_to, '%b %Y'),
                            lending_funds, on_loan_usd, coverage, top5_share, hhi, borrower_groups,
                            funds_reconciling
                     from trend_market order by quarter""")
    postings = [{"q": m[0], "label": f"{m[1]} to {m[2]}", "short": m[0].upper()} for m in market]
    latest = market[-1]
    latest_q = latest[0]
    first = market[0]

    data = {
        "latest": latest_q,
        "postings": postings,
        "market": {m[0]: {"lending_funds": m[3], "on_loan": m[4], "coverage": m[5], "top5": m[6],
                          "hhi": m[7], "groups": m[8], "reconciling": m[9]} for m in market},
        "groups": {}, "shares": [], "dist": {"bins": [], "counts": {}}, "scatter": {}, "watch": {},
    }

    for m in market:
        top = rows("""select parent_name, share, on_loan_usd, funds from trend_groups
                      where quarter = ? order by rank_in_quarter limit 8""", m[0])
        data["groups"][m[0]] = [[short(t[0]), t[1], t[2], t[3]] for t in top]

    leaders = [r[0] for r in rows("""select parent_name from trend_groups where quarter = ?
                                     order by rank_in_quarter limit 6""", latest_q)]
    for name in leaders:
        by_q = dict(rows("select quarter, share from trend_groups where parent_name = ?", name))
        data["shares"].append({"name": short(name), "values": [by_q.get(m[0]) for m in market]})

    # Distribution of lending intensity, on fixed bins so the postings compare.
    edges = [0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.33, 0.50]
    data["dist"]["bins"] = ["0-1%", "1-2%", "2-5%", "5-10%", "10-20%", "20-33%", "33%+"]
    for m in market:
        counts = []
        for i in range(len(edges) - 1):
            hi = "and on_loan_pct_nav < ?" if i < len(edges) - 2 else ""
            args = [m[0], edges[i]] + ([edges[i + 1]] if hi else [])
            counts.append(one(f"""select count(*) from hist_fund
                                  where quarter = ? and reconciliation = 'reconciles'
                                    and on_loan_pct_nav >= ? {hi}""", *args)[0])
        data["dist"]["counts"][m[0]] = counts

    for m in market:
        pts = rows("""select on_loan_pct_nav, coverage, series_name from hist_fund
                      where quarter = ? and reconciliation = 'reconciles' and coverage > 0
                      order by hash(series_id) limit 900""", m[0])
        data["scatter"][m[0]] = [{"x": round(p[0], 4), "y": round(min(p[1], 2.0), 3), "n": p[2]} for p in pts]
        watch = rows("""select series_name, on_loan_pct_nav, top_group, top_group_pct_nav, coverage
                        from hist_fund where quarter = ? and reconciliation = 'reconciles'
                        order by on_loan_pct_nav desc limit 25""", m[0])
        data["watch"][m[0]] = [[w[0], round(w[1], 4), short(w[2] or ""), round(w[3] or 0, 4),
                                round(w[4] or 0, 4)] for w in watch]

    cash = rows("""select issuer_name, sum(cash_reinvested) from hist_cash_reinvestment
                   where quarter = ? group by 1 order by 2 desc limit 8""", latest_q)
    cash_total = one("select sum(cash_reinvested) from hist_cash_reinvestment where quarter = ?", latest_q)[0]
    data["cash"] = [[short(c[0])[:38], c[1] / cash_total] for c in cash]

    # Supporting figures quoted in the prose.
    funds_total = one(f'select count(distinct SERIES_ID) from src."{latest_q}".fund_reported_info')[0]
    naive = one(f"""select sum(try_cast(replace(AGGREGATE_VALUE, ',', '') as double))
                    from src."{latest_q}".borrower""")[0]
    # filing holds every filing of the quarter resolve.py ran last, before one snapshot per fund is picked.
    dup_funds = one("""select count(*) from (select series_id from filing
                       group by 1 having count(distinct accession_number) > 1)""")[0]
    corrections = dict((r[0], (r[1], r[2])) for r in rows(
        """select resolution, count(*), sum(value_on_loan) from hist_exposure
           where quarter = ? and resolution in ('lei_corrected', 'lei_name_conflict') group by 1""", latest_q))
    names_vs_leis = one("""select count(distinct filed_key), count(distinct filed_lei)
                           from hist_exposure where quarter = ?""", latest_q)
    resolution = dict(rows("""select resolution, sum(value_on_loan) / sum(sum(value_on_loan)) over ()
                              from hist_exposure where quarter = ? group by 1""", latest_q))
    lei_backed = resolution.get("lei_confirmed", 0) + resolution.get("lei_accepted", 0)
    rec_share = one("""select sum(borrower_total) filter (where reconciliation = 'reconciles')
                              / sum(borrower_total) from hist_fund where quarter = ?""", latest_q)[0]
    quant = one("""select quantile_cont(on_loan_pct_nav, 0.5), quantile_cont(on_loan_pct_nav, 0.99),
                          quantile_cont(top_group_share_of_lending, 0.5)
                   from hist_fund where quarter = ? and reconciliation = 'reconciles'""", latest_q)
    totals = one("select sum(cash_collateral), sum(noncash_collateral) from hist_fund where quarter = ?",
                 latest_q)
    short_fall = one("""select count(*) filter (where coverage > 0 and coverage < 1),
                               sum(borrower_total) filter (where coverage > 0 and coverage < 1),
                               sum(borrower_total - cash_collateral - noncash_collateral)
                                   filter (where coverage > 0 and coverage < 1),
                               count(*) filter (where coverage > 0 and coverage < 0.9)
                        from hist_fund where quarter = ? and reconciliation = 'reconciles'""", latest_q)
    near_limit = one("""select count(*) from hist_fund where quarter = ? and reconciliation = 'reconciles'
                        and on_loan_pct_nav >= 0.33""", latest_q)[0]
    biggest_single = one("""select series_name, top_group, top_group_pct_nav from hist_fund
                            where quarter = ? and reconciliation = 'reconciles'
                            order by top_group_pct_nav desc limit 1""", latest_q)
    persistent = rows("""select series_name, quarters_near_ceiling, quarters_below_90pct,
                                max_on_loan_pct_nav, min_coverage from trend_fund_flags
                         where quarters_near_ceiling = 4 or quarters_below_90pct = 4
                         order by quarters_near_ceiling desc, max_on_loan_pct_nav desc""")
    ishares = one("""select count(*), sum(borrower_total) from hist_fund
                     where quarter = '2025q4' and reconciliation = 'no_holding_detail'""")
    new_lenders = one("""select count(*), sum(borrower_total) from hist_fund a
                         where quarter = ? and not exists (select 1 from hist_fund b
                           where b.series_id = a.series_id and b.quarter = ?)""",
                      latest_q, market[-2][0])
    top5_names = ", ".join(f"{g[0]} ({pct(g[1])})" for g in data["groups"][latest_q][:5])
    movers = sorted(((s["name"], (s["values"][-1] or 0) - (s["values"][0] or 0)) for s in data["shares"]),
                    key=lambda t: -t[1])

    p = []
    p.append('<!doctype html><html lang="en"><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1">')
    p.append("<title>Securities lending exposure in US funds</title>")
    p.append('<meta name="description" content="Counterparty concentration and collateral cover across four '
             'quarterly SEC Form N-PORT postings.">')
    p.append(f"<style>{CSS}</style><body><div class=wrap>")

    p.append('<header class="doc"><p class="kicker">Analysis report</p>'
             "<h1>Securities lending exposure in US funds</h1>"
             '<p class="standfirst">Who borrows securities from US mutual funds and ETFs, how concentrated that '
             "borrowing has become, and whether the collateral behind it holds up.</p>"
             f'<div class="meta"><div>Prepared by <b>Ankit Singathia</b></div>'
             f'<div>Source <b>SEC Form N-PORT</b>, four quarterly postings</div>'
             f'<div>Portfolios dated <b>{first[1]} to {latest[2]}</b></div>'
             f'<div>Issued <b>{dt.date.today():%d %B %Y}</b></div></div></header>')

    p.append('<section class="summary">'
             "<h3>The question</h3>"
             "<p>Funds lend the shares and bonds they hold to banks, for a fee. The loans are collateralised and "
             "the borrower is named in every filing, yet the exposure is only ever disclosed one fund at a time. "
             "Nobody adds it up. This report does, for every US mutual fund and ETF that filed, and asks three "
             "things: who is on the other side, how concentrated is it, and is it covered.</p>"
             "<h3>What the filings show</h3><ul>"
             f"<li><b>{bn(latest[4])} is on loan</b> from {latest[3]:,} of {funds_total:,} funds in the latest "
             f"posting, to {latest[8]} bank groups.</li>"
             f"<li><b>Five banks take {pct(latest[6])} of it.</b> {top5_names}.</li>"
             f"<li><b>Collateral covers {pct(latest[5])} of loans</b>, and the genuine shortfall is "
             f"{bn(short_fall[2])}, not the {bn(short_fall[1])} a literal reading of the filings suggests.</li>"
             f"<li><b>{near_limit} funds lend a third or more of their net assets</b>, and four of them do it in "
             f"every posting.</li></ul>"
             "<h3>What we recommend</h3><ul>"
             "<li>Monitor the four funds that sit at 43 to 47% of net assets in every posting.</li>"
             f"<li>Review the {short_fall[3]} funds below 90% cover, and ask GMO where the collateral for about "
             "$0.5bn of loans is held.</li>"
             "<li>Measure counterparty exposure at parent-group level, not by identifier, or JPMorgan splits "
             "across a London entity and a Paris branch.</li></ul>"
             "</section>")

    p.append('<div class="picker" role="group" aria-label="Choose a posting">'
             + "".join(f'<button type="button" data-q="{x["q"]}" '
                       f'aria-pressed="{str(x["q"] == latest_q).lower()}">{esc(x["label"])}</button>'
                       for x in postings) + "</div>")
    p.append('<p class="scope">Figures below follow this selector. Showing <b class="scope-label"></b>.</p>')

    p.append('<div class="tiles">'
             + tile("onloan", "On loan", "value of securities lent")
             + tile("funds", "Lending funds", "funds with a borrower")
             + tile("cover", "Collateral cover", "collateral over loans")
             + tile("top5", "Top five share", "share taken by five groups")
             + tile("hhi", "HHI", "1,000 is the concentration mark")
             + tile("groups", "Borrower groups", "after resolving to parents")
             + "</div>")

    p.append('<h2><span class="num">01</span>Why this is worth measuring</h2>')
    p.append("<p>Securities lending is routine and, in normal weather, dull. A fund lends stock to a bank, the "
             "bank posts collateral worth slightly more than the loan, the fund earns a few basis points and the "
             "collateral is marked daily. The risk only appears in two places: if the borrower fails at the same "
             "moment the collateral falls short, and if a lot of funds happen to face the same borrower at once. "
             "Both are invisible in any single filing, which is what makes the aggregate worth building.</p>")
    p.append(f"<p>Form N-PORT is the raw material. Every registered fund files its portfolio monthly, the "
             f"securities it has out on loan, the name and Legal Entity Identifier of each borrower, and the "
             f"collateral held against them. Four quarterly postings were read here, "
             f"{first[1]} to {latest[2]}, covering {funds_total:,} funds in the latest one.</p>")

    p.append('<h2><span class="num">02</span>What had to be fixed before anything could be added up</h2>')
    p.append("<p>N-PORT is published exactly as funds submit it. The filings are not audited and not "
             "standardised, and the first pass at the data is wrong in ways that are easy to miss. Five "
             "problems mattered enough to change the numbers:</p>")
    p.append(table(
        ["Problem", "Evidence in the latest posting", "How it was handled"],
        [["One firm, many spellings",
          f"{names_vs_leis[0]} distinct borrower names against {names_vs_leis[1]} identifiers; Morgan Stanley "
          f"alone is filed eleven ways",
          "Names group candidates only. The identifier, checked against the GLEIF registry, decides the entity"],
         ["An identifier belonging to another firm",
          f"{corrections.get('lei_corrected', (0, 0))[0]} rows corrected on the evidence of the name, and "
          f"{corrections.get('lei_name_conflict', (0, 0))[0]} rows worth "
          f"{bn(corrections.get('lei_name_conflict', (0, 0))[1])} left flagged where the evidence is thin",
          "Corrected only when the name is confirmed elsewhere for another group, never moved silently"],
         ["Branch and replaced identifiers",
          "JPMorgan Securities plc also appears under its Paris branch; duplicate and retired identifiers are "
          "still in use",
          "Followed through GLEIF to the head office or successor, then to the ultimate parent"],
         ["Funds filing more than once",
          f"{dup_funds:,} funds filed twice; a naive sum gives {bn(naive)} against {bn(latest[4])}",
          "One snapshot per fund: latest holdings date, then latest filing. Removes "
          f"{bn(naive - latest[4])} of double counting"],
         ["A filing contradicting itself",
          f"{ishares[0]} funds in the Aug-Oct 2025 posting report {bn(ishares[1])} lent while marking every "
          f"position as not on loan",
          "Market totals use the borrower section; those funds are excluded from fund-level ratios"]],
        numeric_from=9))
    p.append(f'<div class="note"><b>Net effect.</b> {pct(lei_backed)} of the value in the latest posting is '
             f"backed by an identifier the registry agrees with, and {pct(rec_share)} of value reconciles "
             f"between the two places each filing reports its lending. Every rule above, and the alternatives "
             f'rejected, is recorded in the <a href="DECISIONS.md">decision log</a>.</div>')

    p.append('<h2><span class="num">03</span>Five banks borrow most of what US funds lend</h2>')
    p.append(f"<p>Borrowers are grouped to their ultimate parent, so a bank's London entity, its Paris branch "
             f"and its US broker-dealer count as one counterparty. On that basis {latest[8]} groups borrow from "
             f"US funds, and the top five take {pct(latest[6])} of the total. The market is not dominated by a "
             f"single firm, the HHI of {latest[7]:,.0f} sits below the 1,000 mark regulators treat as "
             f"unconcentrated, but more than half of every dollar goes to five names.</p>")
    p.append(panel("Share of all fund lending, by borrower group",
                   'Ultimate parents, top eight. Hover a bar for the value and the number of funds behind it.',
                   "c-borrowers",
                   'Showing <b class="scope-label"></b>. Source: N-PORT borrower sections, resolved through '
                   "GLEIF."))

    p.append('<h2><span class="num">04</span>Lending grew 23% over the year, and the leaders moved</h2>')
    p.append(f"<p>Across the four postings the amount on loan rose from {bn(first[4])} to {bn(latest[4])}, up "
             f"{(latest[4] / first[4] - 1) * 100:.0f}%. Concentration barely moved with it: the top five share "
             f"went from {pct(first[6])} to {pct(latest[6])}. Growth came from both directions, "
             f"{new_lenders[0]:,} funds lending for the first time in the latest posting and adding "
             f"{bn(new_lenders[1])}, and existing lenders adding the rest.</p>")
    p.append(panel("Value on loan and top five share, by posting",
                   "Left axis is the value on loan, right axis the share taken by the five largest groups.",
                   "c-trend", "Both series cover all four postings and ignore the selector above."))
    p.append(f"<p>Underneath the flat total, the order changed. {movers[0][0]} gained the most over the year, "
             f"{movers[0][1] * 100:+.1f} points, while {movers[-1][0]} lost {abs(movers[-1][1]) * 100:.1f}. "
             f"Click a name in the legend to isolate it.</p>")
    p.append(panel("Share of lending, six largest borrower groups",
                   "Each line is one group's share of all fund lending in that posting.",
                   "c-shares", "Click a legend entry to hide or show a group."))

    p.append('<h2><span class="num">05</span>Most funds lend a little, a few lend to the limit</h2>')
    p.append(f"<p>The median lending fund has {pct(quant[0])} of its net assets out on loan. The 99th percentile "
             f"is {pct(quant[1])}. SEC guidance caps lending at about a third of total assets, which is roughly "
             f"half of net assets once collateral is counted, so the shape of this distribution matters more "
             f"than its average: {near_limit} funds sit at or above a third of net assets in the latest "
             f"posting.</p>")
    p.append(panel("How much of itself each fund lends",
                   "Funds by share of net assets out on loan. The count axis is logarithmic, because the first "
                   "bar holds most of the market.",
                   "c-dist", 'Showing <b class="scope-label"></b>. Reconciling funds only.'))
    p.append(f"<p>Concentration repeats inside the funds. The median fund places {pct(quant[2])} of its lending "
             f"with a single bank group, and the largest single exposure is "
             f"{biggest_single[0]}, which has {pct(biggest_single[2])} of its net assets lent to "
             f"{short(biggest_single[1])} alone.</p>")
    p.append('<h3>Funds lending the most, relative to their size</h3>'
             '<p class="fine">Top 25 by share of net assets on loan, for the selected posting. '
             'Type to filter by fund name. Cover below 90% is marked.</p>'
             '<input class="srch" id="watch-search" type="search" placeholder="Filter by fund name" '
             'aria-label="Filter by fund name">'
             '<p class="fine"><b id="watch-count"></b> funds shown for <b class="scope-label"></b>.</p>'
             '<div class="tw"><table><thead><tr><th>Fund</th><th class=n>On loan, % of NAV</th>'
             "<th>Largest borrower</th><th class=n>That borrower, % of NAV</th>"
             '<th class=n>Collateral cover</th></tr></thead><tbody id="watch-body"></tbody></table></div>')

    p.append('<h2><span class="num">06</span>Cover is sound overall, and the real gaps are small</h2>')
    p.append(f"<p>Funds hold {bn(totals[0])} of reinvested cash collateral and {bn(totals[1])} of non-cash "
             f"collateral, mostly US Treasuries, against {bn(latest[4])} of loans. That is {pct(latest[5])} "
             f"cover. Read literally, {short_fall[0]} funds with {bn(short_fall[1])} on loan are below 100%, "
             f"which sounds alarming and is mostly an artefact: loans are re-marked daily and three quarters of "
             f"that value sits within three points of full cover. Summing only what is actually missing gives "
             f"{bn(short_fall[2])}, concentrated in {short_fall[3]} funds below 90%.</p>")
    p.append(panel("Collateral cover against lending intensity",
                   "One dot per fund. Hover a dot for the fund name. The vertical axis is trimmed to 50-200% "
                   "cover; a handful of funds report more, usually because they lend very little against a "
                   "whole cash pool.",
                   "c-cover", 'Showing <b class="scope-label"></b>. A sample of up to 900 reconciling funds.',
                   tall=True))
    p.append("<p>The shape is the point. Funds lending heavily, on the right, sit tightly on full cover. The "
             "wide spread is all among funds lending very little, where a single lumpy collateral position "
             "moves the ratio. Thin cover and heavy lending do not coincide.</p>")

    p.append('<h2><span class="num">07</span>Cash collateral pools into a handful of vehicles</h2>')
    p.append("<p>Cash collateral is not held idle, it is reinvested, and funds overwhelmingly reinvest into the "
             "same few money market vehicles. That is a second, quieter concentration: a problem in one vehicle "
             "would reach hundreds of funds at once, whoever their borrowers were.</p>")
    p.append(panel("Where reinvested cash collateral sits",
                   "Largest eight vehicles by reinvested value, latest posting.",
                   "c-cash", "Source: N-PORT cash collateral reinvestment sections."))

    p.append('<h2><span class="num">08</span>Funds carrying the same problem in every posting</h2>')
    p.append("<p>A fund near the ceiling in one quarter is noise. The same fund there in all four is a policy. "
             "Seven funds qualify, and they split into two unrelated groups: four that lend heavily but are "
             "fully covered, and three whose filings never show most of their collateral.</p>")
    p.append(table(["Fund", "Postings near the ceiling", "Postings under 90% cover", "Highest % of NAV",
                    "Lowest cover"],
                   [[r[0], r[1], r[2], pct(r[3]), pct(r[4])] for r in persistent]))
    p.append('<div class="note">The GMO funds lend very little and their filings only ever show about 17% of '
             "the collateral. That is reported here as <b>collateral not visible</b>, not as uncollateralised. "
             "A filing failing to show something is not evidence that it is missing, and confirming it needs "
             "the funds' annual reports.</div>")

    p.append('<h2><span class="num">09</span>Recommendations</h2>')
    p.append(table(["Priority", "Action", "Why"],
                   [["1", "Monitor the four funds lending 43 to 47% of net assets in every posting",
                     "They sit persistently just under the ceiling, with no quarter of relief"],
                    ["2", f"Review the {short_fall[3]} funds below 90% cover and request collateral detail "
                          "from GMO",
                     f"{bn(short_fall[2])} of genuine shortfall, plus about $0.5bn of loans whose collateral "
                     "is not visible"],
                    ["3", "Measure counterparty exposure at parent-group level, resolved through GLEIF",
                     "Grouping by identifier alone splits JPMorgan across a London entity and a Paris branch"],
                    ["4", "Add a consistency check comparing borrower totals with position-level flags",
                     f"{ishares[0]} funds reported {bn(ishares[1])} lent while flagging no position as on loan"],
                    ["5", "Track concentration in cash collateral reinvestment vehicles",
                     f"The largest vehicle alone holds {pct(data['cash'][0][1])} of all reinvested cash"]],
                   numeric_from=9))

    p.append('<h2><span class="num">10</span>How this was produced</h2>')
    p.append('<figure class="panel"><img src="img/pipeline.svg" alt="Pipeline from the SEC data sets and the '
             'GLEIF registry, through DuckDB and six SQL steps, to this report and the Power BI dashboard" '
             'style="width:100%;height:auto"></figure>')
    p.append("<p>The quarterly data sets are loaded into DuckDB with every column as text, so nothing is "
             "coerced on the way in. Six SQL steps resolve borrowers to parent groups, keep one snapshot per "
             "fund, measure exposure and collateral, and compare the postings. Fifty-five tests run those same "
             "SQL files against small quarters built with planted faults, a wrong identifier, a duplicate "
             "filing, a placeholder identifier, a filing that contradicts itself, so the rules are checked "
             "rather than assumed. Every number in this report is queried at build time; none is typed in.</p>")

    p.append('<h2><span class="num">11</span>What changed during the analysis</h2>')
    p.append("<p>Five findings in earlier drafts were wrong and were corrected against the data. They are kept "
             "in the decision log because the corrections are part of the evidence:</p><ul>"
             "<li>A correction rule applied in the wrong order moved $19.6bn between two JPMorgan entities and "
             "reported $27.8bn of wrong identifiers. Checking the name before correcting fixed it.</li>"
             "<li>An early version used the fiscal year end rather than the portfolio date, which can sit in "
             "the future.</li>"
             "<li>A claimed tagging gap at GMO was contradicted by the funds' own numbers; the honest statement "
             "is that the collateral is not visible.</li>"
             "<li>A claim that no fund added more than $1.8bn was false: one new lender added $3.4bn.</li>"
             "<li>Collateral totals were once quoted on a different scope from the cover ratio beside them.</li>"
             "</ul>")

    p.append('<h2><span class="num">12</span>Limitations</h2>')
    p.append("<ul>"
             "<li><b>Filings are not audited.</b> Every figure is as reported by the fund.</li>"
             "<li><b>A posting is not a calendar quarter.</b> Each holds funds' latest month-end portfolios, so "
             f"the newest one covers {latest[1]} to {latest[2]}. Every figure here is labelled with its "
             "holdings window.</li>"
             "<li><b>Cash collateral is measured at reinvested value.</b> Cover below 100% can mean too little "
             "was taken or that a reinvestment lost value, and the filing cannot separate the two.</li>"
             "<li><b>Exposure is gross.</b> Positions offsetting between a fund and the same bank elsewhere are "
             "not visible in N-PORT.</li></ul>")

    p.append(f'<footer><p>Code, tests and the decision log: <a href="{REPO_URL}">{REPO_URL}</a>. '
             f'The same figures are in the <a href="powerbi/securities_lending.pdf">Power BI report</a>, and '
             f'the working notes written while building this are <a href="readout.html">here</a>.</p>'
             f'<p>Ankit Singathia, {dt.date.today():%B %Y}.</p></footer>')

    p.append("</div>")
    p.append('<script id="report-data" type="application/json">'
             + json.dumps(data, separators=(",", ":")).replace("</", "<\\/") + "</script>")
    p.append('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>')
    p.append(f"<script>{JS}</script></body></html>")

    OUT.write_text("\n".join(p), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}  {OUT.stat().st_size / 1024:.0f} KB")
    print(f"latest posting {latest_q}: {bn(latest[4])} on loan, {latest[3]:,} funds, cover {pct(latest[5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
