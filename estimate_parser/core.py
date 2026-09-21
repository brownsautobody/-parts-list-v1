"""Format detection and the shared output shape for parsed estimates."""
import re
from datetime import datetime

from . import ccc, mitchell
from .pdfutil import open_pages, page_text

PRICED = {"Part", "Other Charge", "Sublet"}
LABOR_CATEGORIES = ["Body Labor", "Paint Labor", "Mechanical Labor", "Structural Labor",
                    "Frame Labor", "Electrical Labor", "Diagnostic Labor", "Glass Labor"]


def detect_format(pages):
    text = "\n".join(page_text(p) for p in pages[:2])
    if "Mitchell" in text:
        return "Mitchell"
    if "CCC ONE" in text or "Workfile ID" in text or "RO Number" in text:
        return "CCC ONE"
    raise ValueError("Unrecognized estimate format (expected CCC ONE or Mitchell).")


STAGE_RANK = {"unknown": 0, "preliminary": 1, "estimate": 2, "to_repair": 3, "of_record": 4}
STAGE_LABEL = {"unknown": "Unknown", "preliminary": "Preliminary", "estimate": "Estimate", "to_repair": "Estimate to repair",
               "of_record": "Of record"}


def classify_document(title, supplement_hint=None, context=""):
    """Work out stage + supplement number from a document title (never raises; unknown titles stay 'unknown')."""
    t = f"{title} {context}".lower()
    if "prelim" in t:
        stage = "preliminary"
    elif "of record" in t:
        stage = "of_record"
    elif "to repair" in t:
        stage = "to_repair"
    elif "estimate" in t or "supplement" in t:
        stage = "estimate"
    else:
        stage = "unknown"
    m = re.search(r"supplement(?:\s+of\s+record)?\s*#?\s*(\d+)", title.lower())
    if m:
        n = int(m.group(1))
    elif supplement_hint is not None:
        n = supplement_hint
    else:
        n = 1 if "supplement" in title.lower() else 0
    label = STAGE_LABEL[stage] + (f" - supplement {n}" if n else "")
    if stage == "estimate" and n:
        label = f"Supplement {n}"
    return {"title_raw": title, "stage": stage, "supplement_no": n, "label": label}


def _parse_dt(text, fmts):
    for f in fmts:
        try:
            return datetime.strptime(text, f).isoformat(timespec="seconds")
        except ValueError:
            pass
    return ""


def document_info(fmt, header, page1_text, all_text):
    """Type, version and print time of the document."""
    if fmt == "Mitchell":
        pm = re.search(r"Supplement (\d+) Printed (\d{1,2}/\d{1,2}/\d{4} \d\d:\d\d [AP]M)", all_text)
        tag = re.search(r"\bS(\d+)\b", page1_text)
        hint = int(pm.group(1)) if pm else int(tag.group(1)) if tag else 0
        title = f"Supplement {hint}" if hint else "Estimate"
        doc = classify_document(title, hint, context="of record" if "of record" in page1_text.lower() else "")
        pt = pm.group(2) if pm else ""
        if not pt:
            m = re.search(r"Printed On.*?(\d{1,2}/\d{1,2}/\d{4})", all_text)
            pt = ""
        doc["printed_at"] = _parse_dt(pt, ["%m/%d/%Y %I:%M %p"]) if pt else ""
        m = re.search(r"Net Supplement Amount\s+(-?)\$?(-?[\d,]+\.\d\d)", all_text)
    else:
        doc = classify_document(header.get("document", ""))
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d\d:\d\d [AP]M)", all_text)
        doc["printed_at"] = _parse_dt(m.group(1), ["%m/%d/%Y %I:%M:%S %p"]) if m else ""
        m = re.search(r"NET COST OF SUPPLEMENT\s+(-?)([\d,]+\.\d\d)", all_text)
    doc["supplement_amount"] = (-1 if m.group(1) else 1) * float(m.group(2).replace(",", "")) if m else None
    return doc


def _history_check(h):
    """Add a sum check to the printed history; nothing is estimated or filled in."""
    if not h:
        return None
    parts = round(sum(e["amount"] for e in h["entries"]), 2)
    h["sum"] = parts
    h["ok"] = bool(h["total"]) and abs(parts - h["total"]["amount"]) <= 0.02
    return h


def version_key(doc):
    """Sort key: the highest value is the job's current document."""
    return (doc["supplement_no"], STAGE_RANK[doc["stage"]], doc["printed_at"] or "")


def _close(a, b, tol=0.06):
    return abs(a - b) <= tol


def _checks(fmt, charges, totals, subtotals):
    """Compare what we extracted line by line against the estimate's own totals."""
    by_label = {}
    for t in totals:
        by_label.setdefault(t["label"], t)
    checks = []

    def hours(cat):
        return round(sum(c["hours"] for c in charges if c["category"] == cat and c["hours"] is not None), 2)

    # CCC folds any labor type without its own totals row into Body Labor
    body_like = ["Body Labor"] + [c for c in LABOR_CATEGORIES[2:] if c not in by_label]
    if fmt != "CCC ONE":
        body_like = ["Body Labor"]
    for label, cats in (("Body Labor", body_like), ("Paint Labor", ["Paint Labor"]), ("Mechanical Labor", ["Mechanical Labor"])):
        exp = by_label.get(label, {}).get("hours")
        if exp is None:
            continue
        got = round(sum(hours(c) for c in cats), 2)
        checks.append({"name": f"{label} hours", "parsed": got, "expected": exp, "ok": _close(got, exp, 0.01)})

    price_total = round(sum(c["amount"] for c in charges if c["category"] in PRICED and c["amount"] is not None), 2)
    if fmt == "CCC ONE":
        exp = subtotals[0] if subtotals else by_label.get("Parts", {}).get("amount")
        name = "Line price total"
    else:
        exp = None
        tp = by_label.get("Taxable Parts", {}).get("amount")
        cost = sum(t["amount"] for t in totals if t["label"] in ("Paint Materials", "Shop Materials", "Other Additional"))
        if tp is not None:
            exp = round(tp + cost, 2)
        name = "Parts + charges total"
    if exp is not None:
        checks.append({"name": name, "parsed": price_total, "expected": exp, "ok": _close(price_total, exp)})
    return checks


def parse_pdf(src, filename=""):
    pdf, pages = open_pages(src)
    try:
        fmt = detect_format(pages)
        mod = ccc if fmt == "CCC ONE" else mitchell
        header = mod.parse_header(pages)
        if fmt == "CCC ONE":
            items, subtotals = ccc.parse_items(pages)
        else:
            items, subtotals = mitchell.parse_items(pages), []
        totals = mod.parse_totals(pages)
        charges = [c for i in items for c in mod.expand(i)]
        n_pages = len(pages)
        history = mod.parse_history(pages)
        document = document_info(fmt, header, page_text(pages[0]), chr(10).join(page_text(p) for p in pages))
    finally:
        pdf.close()

    rates = {t["label"]: t["rate"] for t in totals if t.get("rate")}
    for c in charges:
        if c["hours"] is not None and c.get("rate") is None:
            c["rate"] = rates.get(c["category"])
            if c["rate"] is not None:
                c["amount"] = round(c["hours"] * c["rate"], 2)
    result = {
        "filename": filename, "format": fmt, "pages": n_pages, "header": header, "document": document, "history": _history_check(history),
        "charges": charges, "totals": totals, "checks": _checks(fmt, charges, totals, subtotals),
    }
    result["summary"] = summarize(result)
    return result


# --------------------------------------------------------------- key-data summary

_DROP = {"Parts", "Taxable Parts", "Parts Total", "Parts Adjustments", "Taxable", "Non-Taxable", "Pre-Tax Discount",
         "Total Labor", "Labor Total", "Original", "Original Estimate", "Net Supplement", "Less Original Net Total",
         "Net Supplement Amount"}


def summarize(r):
    """The handful of fields the shop needs from an estimate."""
    h, v = r["header"], r["header"]["vehicle"]
    charges, totals = r["charges"], r["totals"]
    ro = h.get("ro_number", "")
    rates = {t["label"]: t["rate"] for t in totals if t.get("rate")}

    groups = {"Body": ["Body Labor"], "Paint": ["Paint Labor"], "Mechanical": ["Mechanical Labor"]}
    other_cats = [c for c in LABOR_CATEGORIES if c not in sum(groups.values(), [])]
    groups["Other"] = other_cats
    labor = []
    for name, cats in groups.items():
        rows = [c for c in charges if c["category"] in cats and c["hours"] is not None]
        hrs = round(sum(c["hours"] for c in rows), 2)
        rate = next((c["rate"] for c in rows if c.get("rate")), None) or next((rates[c] for c in cats if c in rates), None)
        # only price hours when the estimate prints a rate for that labor type
        amt = round(sum(c["amount"] for c in rows if c["amount"] is not None), 2) if rate else None
        labor.append({"category": f"{name} labor", "hours": hrs, "rate": rate, "amount": amt})

    by = {t["label"]: t["amount"] for t in totals}
    parts = by.get("Parts", by.get("Taxable Parts"))
    if parts is None:
        parts = round(sum(c["amount"] for c in charges if c["category"] == "Part"), 2)

    labels = {t["label"] for t in totals}
    other_rows, tax_n = [], 0
    for t in totals:
        lab = t["label"]
        is_tax = lab.split(" ")[0] == "Tax" and r["format"] == "Mitchell"
        if is_tax:  # Mitchell prints tax for labor, parts, materials, then the grand total
            lab = ["Labor tax", "Parts tax", "Materials tax", "Total tax"][min(tax_n, 3)] + lab[3:]
            tax_n += 1
        if lab in _DROP or lab in LABOR_CATEGORIES or t["hours"] is not None or not t["amount"]:
            continue
        other_rows.append({"label": lab, "amount": t["amount"]})
    seen, dedup = set(), []
    for o in other_rows:
        k = (o["label"], o["amount"])
        if k not in seen:
            seen.add(k)
            dedup.append(o)

    return {
        "document": r["document"],
        "history": r["history"],
        "customer": h.get("customer", ""),
        "ro_number": ro if ro.isdigit() and len(ro) == 4 else "",
        "vehicle": " ".join(x for x in (v.get("year"), v.get("make"), v.get("model")) if x),
        "vin": v.get("vin", ""),
        "insurance": h.get("insurance", ""),
        "claim": h.get("claim", ""),
        "labor": labor,
        "total_labor_hours": round(sum(x["hours"] for x in labor), 2),
        "total_labor_amount": round(sum(t["amount"] for t in totals if t["hours"] is not None and t["rate"] and t["label"].endswith("Labor")), 2) or None,
        "parts_total": parts,
        "other_charges": dedup,
        "checks_ok": all(c["ok"] for c in r["checks"]) if r["checks"] else None,
    }
