"""Upload page: python app.py, then open http://127.0.0.1:5000"""
import io

from flask import Flask, request

from estimate_parser.core import parse_pdf
from estimate_parser.render import results, upload_form

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return upload_form()
    f = request.files.get("pdf")
    if not f or not f.filename:
        return upload_form("Choose a PDF file first."), 400
    try:
        return results(parse_pdf(io.BytesIO(f.read()), f.filename))
    except Exception as e:  # show the reason instead of a stack trace
        return upload_form(f"Could not parse {f.filename}: {e}"), 422


if __name__ == "__main__":
    app.run(debug=True)
