"""Low-level PDF helpers shared by the CCC and Mitchell parsers."""
import re

import pdfplumber

_NUM_RE = re.compile(r"^\(?-?\$?-?(\d[\d,]*(\.\d+)?|\.\d+)\)?[TXDEFGMS#*]?$")


def open_pages(src):
    """Open a PDF (path or file object) and return (pdf, pages) with doubled bold text removed."""
    pdf = pdfplumber.open(src)
    return pdf, [p.dedupe_chars() for p in pdf.pages]


def group_rows(page, tol=2.5):
    """Group a page's words into visual rows, each sorted left to right."""
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(w["top"] - rows[-1]["top"]) <= tol:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["text"] = " ".join(w["text"] for w in r["words"])
    return rows


def is_num(tok):
    return bool(_NUM_RE.match(tok))


def num(tok):
    """'1,386.25' -> 1386.25, '(0.4)' -> -0.4, '$5.00*' -> 5.0. None if not numeric."""
    t = tok.strip()
    if not _NUM_RE.match(t):
        return None
    neg = (t.startswith("(") and t.endswith(")")) or "-" in t
    v = float(re.sub(r"[^\d.]", "", t) or "nan")
    return -v if neg else v


def money(s):
    """Parse '1,234.56', '(500.00)' or '-$500.00' style strings."""
    return num(s.strip())


def page_text(page):
    return page.extract_text() or ""
