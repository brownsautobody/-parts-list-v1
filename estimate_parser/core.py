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
    return {
        "filename": filename, "format": fmt, "pages": n_pages, "header": header,
        "charges": charges, "totals": totals, "checks": _checks(fmt, charges, totals, subtotals),
    }
