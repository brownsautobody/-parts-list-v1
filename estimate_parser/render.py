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
        "<h1>Estimate Parser</h1><p class='sub'>Upload a CCC ONE or Mitchell estimate PDF to pull out the key data: "
        "customer, RO #, vehicle, VIN, insurance, claim #, labor by type, total parts and other price breakdowns.</p>"
        f"{err}<div class='card'><form class='up' method='post' action='/' enctype='multipart/form-data'>"
        "<input type='file' name='pdf' accept='application/pdf,.pdf' required>"
        "<button class='go' type='submit'>Parse estimate</button></form></div>")


def results(r):
    m = r["summary"]
    d = m["document"]
    fields = [("Customer", m["customer"]), ("RO #", m["ro_number"]), ("Vehicle", m["vehicle"]), ("VIN", m["vin"]),
              ("Insurance", m["insurance"]), ("Claim #", m["claim"])]
    info = "".join(f"<div><span>{escape(k)}</span>{escape(str(val)) or '&nbsp;'}</div>" for k, val in fields)

    lrows = "".join(
        f"<tr><td>{escape(x['category'])}</td><td class='n'>{_n(x['hours'], 1)}</td>"
        f"<td class='n'>{_n(x['rate'], 2, '$')}</td><td class='n'>{_n(x['amount'], 2, '$')}</td></tr>" for x in m["labor"])
    lrows += (f"<tr><th>Total labor</th><th class='n'>{_n(m['total_labor_hours'], 1)}</th><th></th>"
              f"<th class='n'>{_n(m['total_labor_amount'], 2, '$')}</th></tr>")
    labor = ("<h2>Labor</h2><div class='wrap'><table><thead><tr><th>Type</th><th class='n'>Hours</th>"
             f"<th class='n'>Rate</th><th class='n'>Amount</th></tr></thead><tbody>{lrows}</tbody></table></div>")

    parts = ("<h2>Parts</h2><div class='wrap'><table><tbody><tr><td>Total parts</td>"
             f"<td class='n'>{_n(m['parts_total'], 2, '$')}</td></tr></tbody></table></div>")

    orows = "".join(f"<tr><td>{escape(o['label'])}</td><td class='n'>{_n(o['amount'], 2, '$')}</td></tr>"
                    for o in m["other_charges"])
    other = ("<h2>Other price breakdowns</h2><div class='wrap'><table><tbody>" + orows + "</tbody></table></div>") if orows else ""

    hist = m["history"]
    if hist:
        hrows = "".join(f"<tr><td>{escape(e['label'])}</td><td>{escape(e['by'])}</td><td class='n'>{_n(e['amount'], 2, '$')}</td></tr>"
                        for e in hist["entries"])
        if hist["total"]:
            hrows += (f"<tr><th>{escape(hist['total']['label'])}</th><th></th>"
                      f"<th class='n'>{_n(hist['total']['amount'], 2, '$')}</th></tr>")
        history = ("<h2>Document history</h2><div class='wrap'><table><thead><tr><th>Document</th><th>By</th>"
                   f"<th class='n'>Amount</th></tr></thead><tbody>{hrows}</tbody></table></div>")
    else:
        history = ""

    body = (f"<p><a href='/'>&larr; Parse another</a></p><h1>{escape(d['display'])}</h1>"
            f"<p class='sub'>{escape(r['filename'] or '')}</p>{history}"
            f"<h2>Job</h2><div class='card'><div class='grid'>{info}</div></div>{labor}{parts}{other}")
    return page(body, f"Parsed: {d['display']}")
