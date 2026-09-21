"""HTML rendering for parsed estimates."""
from html import escape

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#66707d;--line:#e2e6eb;--accent:#1f5fbf;--ok:#1a7f4b;--bad:#b3261e;
--part:#e8f0fe;--body:#fdeedd;--paint:#f3e8fd;--mech:#e3f5ee;--other:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d222a;--ink:#e8ecf1;--mute:#98a2b0;--line:#2c333d;--accent:#7fb0ff;--ok:#5fd394;--bad:#ff8a80;
--part:#1d2b45;--body:#43301c;--paint:#35244a;--mech:#1b3a2f;--other:#2a3038}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:26px 0 8px}
.sub{color:var(--mute);margin:0 0 16px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 22px}.grid div span{display:block;color:var(--mute);font-size:12px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);font-size:14px}
th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--bg);font-size:12px;color:var(--mute)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.wrap{overflow-x:auto}
.chip{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;white-space:nowrap}
.Part{background:var(--part)}.Body{background:var(--body)}.Paint{background:var(--paint)}.Mechanical{background:var(--mech)}.Other{background:var(--other)}
.filters{margin:0 0 8px;display:flex;gap:6px;flex-wrap:wrap}.filters button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:99px;padding:3px 12px;cursor:pointer}
.filters button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.ok{color:var(--ok)}.bad{color:var(--bad)}.sec{color:var(--mute);font-size:12px}
form.up{display:flex;gap:10px;align-items:center;flex-wrap:wrap}input[type=file]{flex:1;min-width:220px}
button.go{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 18px;font-size:15px;cursor:pointer}
.err{background:var(--card);border:1px solid var(--bad);color:var(--bad);border-radius:10px;padding:12px 14px;margin:14px 0}
"""

JS = """
document.querySelectorAll('.filters button').forEach(function(b){b.onclick=function(){
 document.querySelectorAll('.filters button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
 var f=b.dataset.f;document.querySelectorAll('#charges tbody tr').forEach(function(r){r.style.display=(f==='all'||r.dataset.c===f)?'':'none'});};});
"""


def _kind(cat):
    first = cat.split()[0]
    return first if first in ("Body", "Paint", "Mechanical") else "Part" if cat == "Part" else "Other"


def _n(v, d=2, prefix=""):
    return "" if v is None else f"{prefix}{v:,.{d}f}"


def page(body, title="Estimate Parser"):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main><script>{JS}</script></body></html>")


def upload_form(error=""):
    err = f"<div class='err'>{escape(error)}</div>" if error else ""
    return page(
        "<h1>Estimate Parser</h1><p class='sub'>Upload a CCC ONE or Mitchell estimate PDF to extract customer, vehicle, "
        "itemized parts, labor (body / paint / mechanical), other charges and totals.</p>"
        f"{err}<div class='card'><form class='up' method='post' action='/' enctype='multipart/form-data'>"
        "<input type='file' name='pdf' accept='application/pdf,.pdf' required>"
        "<button class='go' type='submit'>Parse estimate</button></form></div>")


def results(r):
    h, v = r["header"], r["header"]["vehicle"]
    fields = [
        ("Customer", h.get("customer")), ("Phone", h.get("phone")), ("RO / Estimate #", h.get("ro_number")),
        ("Document", h.get("document")), ("Vehicle", f"{v['year']} {v['make']} {v['model']}".strip()),
        ("VIN", v.get("vin")), ("Mileage", v.get("mileage")), ("Insurance", h.get("insurance")),
        ("Claim #", h.get("claim")), ("Adjuster", h.get("adjuster")), ("Estimator", h.get("estimator")),
        ("Deductible", h.get("deductible")), ("Loss date", h.get("loss_date")),
    ]
    info = "".join(f"<div><span>{escape(k)}</span>{escape(str(val or '—'))}</div>" for k, val in fields)

    checks = "".join(
        f"<tr><td>{escape(c['name'])}</td><td class='n'>{c['parsed']:,.2f}</td><td class='n'>{c['expected']:,.2f}</td>"
        f"<td class='{'ok' if c['ok'] else 'bad'}'>{'✓ matches' if c['ok'] else '✗ mismatch'}</td></tr>"
        for c in r["checks"])
    checks_html = (
        "<h2>Validation against the estimate's own totals</h2><div class='wrap'><table><thead><tr><th>Check</th>"
        "<th class='n'>Extracted</th><th class='n'>Estimate says</th><th></th></tr></thead>"
        f"<tbody>{checks}</tbody></table></div>") if checks else ""

    cats = sorted({c["category"] for c in r["charges"]})
    filters = "<button class='on' data-f='all'>All</button>" + "".join(
        f"<button data-f='{escape(c)}'>{escape(c)}</button>" for c in cats)
    rows = []
    for c in r["charges"]:
        desc = " ".join(x for x in (c["op"], c["desc"]) if x)
        rows.append(
            f"<tr data-c='{escape(c['category'])}'><td class='n'>{c['line']}</td>"
            f"<td><span class='chip {_kind(c['category'])}'>{escape(c['category'])}</span></td>"
            f"<td>{escape(desc)}<div class='sec'>{escape(c['section'])}</div></td>"
            f"<td>{escape(c['part_no'])}</td><td>{escape(c.get('part_type', ''))}</td>"
            f"<td class='n'>{_n(c.get('qty'), 0)}</td><td class='n'>{_n(c.get('hours'), 1)}</td>"
            f"<td class='n'>{_n(c.get('rate'), 2, '$')}</td><td class='n'>{_n(c.get('amount'), 2, '$')}</td></tr>")
    charges = (
        f"<h2>Itemized charges ({len(r['charges'])})</h2><div class='filters'>{filters}</div>"
        "<div class='wrap'><table id='charges'><thead><tr>"
        "<th class='n'>Line</th><th>Type</th><th>Description</th><th>Part #</th><th>Part type</th>"
        "<th class='n'>Qty</th><th class='n'>Hours</th><th class='n'>Rate</th><th class='n'>Amount</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")

    trows = "".join(
        f"<tr><td>{escape(t['label'])}</td><td class='n'>{_n(t.get('hours'), 1)}</td>"
        f"<td class='n'>{_n(t.get('rate'), 2, '$')}</td><td class='n'>{_n(t['amount'], 2, '$')}</td></tr>"
        for t in r["totals"])
    totals = (
        "<h2>Estimate totals</h2><div class='wrap'><table><thead><tr><th>Category</th><th class='n'>Hours</th>"
        f"<th class='n'>Rate</th><th class='n'>Amount</th></tr></thead><tbody>{trows}</tbody></table></div>")

    body = (f"<p><a href='/'>← Parse another</a></p><h1>{escape(r['filename'] or 'Estimate')}</h1>"
            f"<p class='sub'>{escape(r['format'])} format · {r['pages']} pages read</p>"
            f"<div class='card'><div class='grid'>{info}</div></div>{checks_html}{charges}{totals}")
    return page(body, f"Parsed: {r['filename'] or 'estimate'}")
