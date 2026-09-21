"""Format detection and the shared output shape for parsed estimates."""
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
    finally:
        pdf.close()

    rates = {t["label"]: t["rate"] for t in totals if t.get("rate")}
    if "Body Labor" in rates:  # labor types without their own totals row bill at the body rate
        for cat in LABOR_CATEGORIES:
            rates.setdefault(cat, rates["Body Labor"])
    for c in charges:
        if c["hours"] is not None and c.get("rate") is None:
            c["rate"] = rates.get(c["category"])
            if c["rate"] is not None:
                c["amount"] = round(c["hours"] * c["rate"], 2)
    result = {
        "filename": filename, "format": fmt, "pages": n_pages, "header": header,
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
        amt = round(sum(c["amount"] for c in rows if c["amount"] is not None), 2)
        rate = next((c["rate"] for c in rows if c.get("rate")), None) or next((rates[c] for c in cats if c in rates), None)
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
        "customer": h.get("customer", ""),
        "ro_number": ro if ro.isdigit() and len(ro) == 4 else "",
        "vehicle": " ".join(x for x in (v.get("year"), v.get("make"), v.get("model")) if x),
        "vin": v.get("vin", ""),
        "insurance": h.get("insurance", ""),
        "claim": h.get("claim", ""),
        "labor": labor,
        "total_labor_hours": round(sum(x["hours"] for x in labor), 2),
        "total_labor_amount": round(sum(x["amount"] for x in labor), 2),
        "parts_total": parts,
        "other_charges": dedup,
        "checks_ok": all(c["ok"] for c in r["checks"]) if r["checks"] else None,
    }
