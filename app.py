"""Shop Database web app: python app.py, then open http://127.0.0.1:5000"""
import io

from flask import Flask, abort, redirect, request, send_file
from sqlalchemy import select

from db.models import AuditLog, EstimateDocument, File, Job, User
from db.save import save_parse, set_field
from db.session import DATA_DIR, init_db, make_engine
from estimate_parser.core import parse_pdf
from estimate_parser.render import job_page, jobs_list, results, upload_form

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
Session = init_db(make_engine())
FILES_DIR = DATA_DIR / "files"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return upload_form()
    f = request.files.get("pdf")
    if not f or not f.filename:
        return upload_form("Choose a PDF file first."), 400
    data = f.read()
    try:
        result = parse_pdf(io.BytesIO(data), f.filename)
    except Exception as e:  # show the reason instead of a stack trace
        return upload_form(f"Could not parse {f.filename}: {e}"), 422
    with Session() as s:
        doc, is_new = save_parse(s, result, data, FILES_DIR)
        s.commit()
    return redirect(f"/documents/{doc.id}" + ("" if is_new else "?dup=1"))


def _vehicle(job):
    return job.current_document.parse["summary"]["vehicle"] if job.current_document else ""


@app.route("/jobs")
def jobs():
    with Session() as s:
        rows = s.scalars(select(Job).where(Job.archived_at.is_(None)).order_by(Job.updated_at.desc())).all()
        return jobs_list([{
            "id": j.id, "ro": j.ro_number, "customer": j.customer.name if j.customer else "", "vehicle": _vehicle(j),
            "insurance": j.insurance.name if j.insurance else "", "claim": j.claim_no,
            "current": j.current_document.display if j.current_document else "",
            "needs_review": bool(j.current_document and j.current_document.needs_review),
            "versions": len(j.documents), "updated": j.updated_at} for j in rows])


def _describe(a):
    if a.action == "create":
        return "Job created" if a.table_name == "jobs" else f"Estimate uploaded: {a.new_value}"
    if a.field == "current_document_id":
        return "Current estimate changed"
    return f"{a.field.replace('_', ' ')}: {a.old_value or '(blank)'} -> {a.new_value or '(blank)'}"


@app.route("/jobs/<int:job_id>")
def job(job_id):
    with Session() as s:
        j = s.get(Job, job_id) or abort(404)
        info = {"id": j.id, "ro": j.ro_number, "customer": j.customer.name if j.customer else "", "vehicle": _vehicle(j),
                "vin": j.vehicle.vin if j.vehicle else "", "insurance": j.insurance.name if j.insurance else "",
                "claim": j.claim_no, "adjuster": j.adjuster, "estimator": j.estimator, "deductible": j.deductible,
                "loss_date": j.loss_date, "current_id": j.current_document_id}
        versions = [{"id": d.id, "display": d.display, "printed": d.printed_at, "amount": d.supplement_amount,
                     "needs_review": d.needs_review, "uploaded": d.created_at, "file_id": d.file_id}
                    for d in sorted(j.documents, key=lambda d: d.id, reverse=True)]
        users = {u.id: u.name for u in s.scalars(select(User))}
        log = [{"at": a.at, "who": users.get(a.user_id, ""), "what": _describe(a)}
               for a in s.scalars(select(AuditLog).where(AuditLog.job_id == j.id).order_by(AuditLog.id.desc()))]
        return job_page(info, versions, log)


@app.route("/jobs/<int:job_id>/ro", methods=["POST"])
def set_ro(job_id):
    with Session() as s:
        j = s.get(Job, job_id) or abort(404)
        set_field(s, j, "ro_number", request.form.get("ro", "").strip(), job_id=j.id)
        s.commit()
    return redirect(f"/jobs/{job_id}")


@app.route("/documents/<int:doc_id>")
def document(doc_id):
    with Session() as s:
        d = s.get(EstimateDocument, doc_id) or abort(404)
        dup = "This PDF was already uploaded - showing the saved copy. " if request.args.get("dup") else "Saved to "
        note = (f"<div class='note'>{dup}<a href='/jobs/{d.job_id}'>job {d.job.ro_number or '#' + str(d.job_id)}</a>"
                f" ({len(d.job.documents)} version{'s' if len(d.job.documents) != 1 else ''}).</div>")
        return results(d.parse, note)


@app.route("/files/<int:file_id>")
def file(file_id):
    with Session() as s:
        f = s.get(File, file_id) or abort(404)
        return send_file(f.path, mimetype=f.content_type, download_name=f.original_name)


if __name__ == "__main__":
    app.run(debug=True)
