"""HTML rendering for parsed estimates and saved jobs."""
from datetime import datetime
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
.err,.review{background:var(--card);border:1px solid var(--bad);color:var(--bad);border-radius:10px;padding:12px 14px;margin:14px 0}
.review ul{margin:6px 0 0;padding-left:20px}
nav{display:flex;gap:18px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--card)}
nav b{margin-right:auto}nav a{color:var(--accent);text-decoration:none}a{color:var(--accent)}
.flag{background:var(--bad);color:#fff}.note{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 14px}
form.ro{display:flex;gap:8px;align-items:center}form.ro input{width:90px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
button.small{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:5px 12px;cursor:pointer}
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


NAV = "<nav><b>Shop Database</b><a href='/'>Upload estimate</a><a href='/jobs'>Jobs</a></nav>"


def page(body, title="Shop Database"):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style>{CSS}</style></head>"
            f"<body>{NAV}<main>{body}</main><script>{JS}</script></body></html>")


def upload_form(error=""):
    err = f"<div class='err'>{escape(error)}</div>" if error else ""
    return page(
        "<h1>Upload estimate</h1><p class='sub'>Upload a CCC ONE or Mitchell estimate or supplement PDF. It is read and saved "
        "to its job (matched by RO #, then claim #, then VIN); a supplement becomes a new version of the same job.</p>"
        f"{err}<div class='card'><form class='up' method='post' action='/' enctype='multipart/form-data'>"
        "<input type='file' name='pdf' accept='application/pdf,.pdf' required>"
        "<button class='go' type='submit'>Save estimate</button></form></div>")


def _dt(v):
    """ISO text or datetime -> '9/17/2026 1:20 PM'."""
    if not v:
        return ""
    d = v if isinstance(v, datetime) else datetime.fromisoformat(v)
    if d.tzinfo:
        d = d.astimezone()
    return f"{d.month}/{d.day}/{d.year} {d.strftime('%I:%M %p').lstrip('0')}"


def jobs_list(jobs):
    """jobs: dicts with id, ro, customer, vehicle, insurance, claim, current, needs_review, versions, updated."""
    rows = "".join(
        f"<tr><td><a href='/jobs/{j['id']}'>{escape(j['ro']) or '&mdash;'}</a></td><td>{escape(j['customer'])}</td>"
        f"<td>{escape(j['vehicle'])}</td><td>{escape(j['insurance'])}</td><td>{escape(j['claim'])}</td>"
        f"<td>{escape(j['current'])}{' <span class=\"chip flag\">Needs review</span>' if j['needs_review'] else ''}</td>"
        f"<td class='n'>{j['versions']}</td><td class='n'>{_dt(j['updated'])}</td></tr>" for j in jobs)
    table = ("<div class='wrap'><table><thead><tr><th>RO #</th><th>Customer</th><th>Vehicle</th><th>Insurance</th>"
             "<th>Claim #</th><th>Current estimate</th><th class='n'>Versions</th><th class='n'>Updated</th></tr></thead>"
             f"<tbody>{rows}</tbody></table></div>") if jobs else "<p class='sub'>No jobs yet - upload an estimate.</p>"
    return page(f"<h1>Jobs</h1><p class='sub'>{len(jobs)} open job{'s' if len(jobs) != 1 else ''}</p>{table}", "Jobs")


def job_page(j, versions, log):
    """j: job dict; versions: dicts with id, display, printed, amount, needs_review, uploaded, file_id; log: audit dicts."""
    fields = [("Customer", j["customer"]), ("Vehicle", j["vehicle"]), ("VIN", j["vin"]), ("Insurance", j["insurance"]),
              ("Claim #", j["claim"]), ("Adjuster", j["adjuster"]), ("Estimator", j["estimator"]),
              ("Deductible", j["deductible"]), ("Loss date", j["loss_date"])]
    info = "".join(f"<div><span>{escape(k)}</span>{escape(str(v)) or '&nbsp;'}</div>" for k, v in fields)
    ro = (f"<form class='ro' method='post' action='/jobs/{j['id']}/ro'><label for='ro'>RO #</label>"
          f"<input id='ro' name='ro' value='{escape(j['ro'])}' maxlength='20'><button class='small'>Save</button></form>")
    vrows = "".join(
        f"<tr><td><a href='/documents/{v['id']}'>{escape(v['display'])}</a>{' (current)' if v['id'] == j['current_id'] else ''}"
        f"{' <span class=\"chip flag\">Needs review</span>' if v['needs_review'] else ''}</td>"
        f"<td>{_dt(v['printed'])}</td><td class='n'>{_n(v['amount'], 2, '$')}</td><td>{_dt(v['uploaded'])}</td>"
        f"<td>{f'<a href=\"/files/{v['file_id']}\">PDF</a>' if v['file_id'] else ''}</td></tr>" for v in versions)
    lrows = "".join(
        f"<tr><td>{_dt(a['at'])}</td><td>{escape(a['who'])}</td><td>{escape(a['what'])}</td></tr>" for a in log)
    body = (f"<p><a href='/jobs'>&larr; All jobs</a></p><h1>{escape(j['customer']) or 'Job'} "
            f"<span class='sec'>{escape(j['vehicle'])}</span></h1><div class='card'>{ro}</div>"
            f"<h2>Job</h2><div class='card'><div class='grid'>{info}</div></div>"
            "<h2>Estimate versions</h2><div class='wrap'><table><thead><tr><th>Document</th><th>Printed</th>"
            f"<th class='n'>Supplement amount</th><th>Uploaded</th><th></th></tr></thead><tbody>{vrows}</tbody></table></div>"
            "<h2>Change log</h2><div class='wrap'><table><thead><tr><th>When</th><th>Who</th><th>What</th></tr></thead>"
            f"<tbody>{lrows}</tbody></table></div>")
    return page(body, f"Job {j['ro'] or j['id']}")


def results(r, note=""):
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

    review = ""
    if m["needs_review"]:
        items = "".join(f"<li>{escape(x)}</li>" for x in m["review_reasons"])
        review = f"<div class='review'><strong>Needs review</strong><ul>{items}</ul></div>"

    body = (f"{note or '<p><a href=\"/\">&larr; Upload another</a></p>'}<h1>{escape(d['display'])}</h1>"
            f"<p class='sub'>{escape(r['filename'] or '')}</p>{review}{history}"
            f"<h2>Job</h2><div class='card'><div class='grid'>{info}</div></div>{labor}{parts}{other}")
    return page(body, f"Parsed: {d['display']}")
