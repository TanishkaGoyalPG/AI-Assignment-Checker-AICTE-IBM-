"""
app.py  –  Plagiarism Intelligence System  (Flask entry point)
=================================================================
Routes:
  GET  /                          → Dashboard (all reports)
  GET  /submit                    → Upload form
  POST /submit                    → Analyse a new submission
  GET  /report/<id>               → Full report view
  POST /report/<id>/decide        → Faculty decision form
  GET  /students                  → Student management
  POST /students/add              → Add a student
  GET  /api/reports               → JSON list of all reports
  GET  /api/report/<id>           → JSON single report
"""

import os
import uuid
from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, flash, abort)
from werkzeug.utils import secure_filename

import config
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER, SUPPORTED_COURSES
from utils.text_extractor import extract_text
from utils.storage import (
    get_all_students, get_student, add_or_update_student,
    save_submission, get_student_submissions, get_all_submissions,
    save_report, get_report, get_all_reports, update_report_decision,
)
from analyzer import analyze_submission

# ── app setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)


def _allowed(filename: str) -> bool:
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)


# ── context processor (inject config into all templates) ─────────────────────
@app.context_processor
def inject_globals():
    return {
        "institution_name": config.INSTITUTION_NAME,
        "max_upload_mb":    config.MAX_UPLOAD_MB,
        "app_version":      "1.0.0",
    }


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    reports  = get_all_reports()
    students = get_all_students()
    # summary stats
    total    = len(reports)
    critical = sum(1 for r in reports if r.get("risk_level") == "CRITICAL")
    high     = sum(1 for r in reports if r.get("risk_level") == "HIGH")
    pending  = sum(1 for r in reports if not r.get("faculty_decision"))
    return render_template(
        "dashboard.html",
        reports=reports,
        students=students,
        stats=dict(total=total, critical=critical, high=high, pending=pending),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SUBMIT ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/submit", methods=["GET"])
def submit_form():
    students = get_all_students()
    return render_template("submit.html",
                           students=students,
                           courses=SUPPORTED_COURSES)


@app.route("/submit", methods=["POST"])
def submit():
    # ── validate form fields ────────────────────────────────────────────────
    student_id      = request.form.get("student_id", "").strip()
    new_name        = request.form.get("new_student_name", "").strip()
    new_course      = request.form.get("new_student_course", "").strip()
    assignment_title = request.form.get("assignment_title", "").strip()
    file            = request.files.get("assignment_file")

    if not assignment_title:
        flash("Assignment title is required.", "error")
        return redirect(url_for("submit_form"))

    if not file or file.filename == "":
        flash("Please upload an assignment file.", "error")
        return redirect(url_for("submit_form"))

    if not _allowed(file.filename):
        flash(f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", "error")
        return redirect(url_for("submit_form"))

    # ── resolve / create student ────────────────────────────────────────────
    if student_id == "__new__" or not student_id:
        if not new_name:
            flash("Please enter a name for the new student.", "error")
            return redirect(url_for("submit_form"))
        student = add_or_update_student(new_name, new_course or "Other")
        student_id = student["id"]
    else:
        student = get_student(student_id)
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("submit_form"))

    # ── extract text ────────────────────────────────────────────────────────
    try:
        text = extract_text(file)
    except Exception as exc:
        flash(f"Could not read the file: {exc}", "error")
        return redirect(url_for("submit_form"))

    if len(text.strip()) < 50:
        flash("The uploaded file appears to be empty or unreadable.", "error")
        return redirect(url_for("submit_form"))

    # ── save submission ─────────────────────────────────────────────────────
    safe_name = secure_filename(file.filename)
    submission = save_submission(student_id, assignment_title, text, safe_name)

    # ── gather references & baselines ───────────────────────────────────────
    # references: other students' past submissions in the same course
    all_subs      = get_all_submissions()
    course        = student.get("course", "")
    all_students  = {s["id"]: s for s in get_all_students()}

    reference_texts = [
        s["text"] for s in all_subs
        if s["student_id"] != student_id
        and all_students.get(s["student_id"], {}).get("course") == course
        and s["id"] != submission["id"]
    ]

    # baselines: same student's previous submissions
    baseline_texts = [
        s["text"] for s in get_student_submissions(student_id)
        if s["id"] != submission["id"]
    ]

    # ── run analysis ────────────────────────────────────────────────────────
    report = analyze_submission(
        submitted_text   = text,
        reference_texts  = reference_texts,
        baseline_texts   = baseline_texts,
        assignment_title = assignment_title,
        student_name     = student["name"],
        course           = course,
    )
    report["student_id"]    = student_id
    report["submission_id"] = submission["id"]

    saved_report = save_report(report)
    flash("Analysis complete!", "success")
    return redirect(url_for("view_report", report_id=saved_report["id"]))


# ─────────────────────────────────────────────────────────────────────────────
# REPORT VIEW
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/report/<report_id>")
def view_report(report_id: str):
    report = get_report(report_id)
    if not report:
        abort(404)
    student = get_student(report.get("student_id", "")) or {}
    return render_template("report.html", report=report, student=student)


# ─────────────────────────────────────────────────────────────────────────────
# FACULTY DECISION
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/report/<report_id>/decide", methods=["POST"])
def faculty_decide(report_id: str):
    decision     = request.form.get("decision", "").strip()
    notes        = request.form.get("notes", "").strip()
    faculty_name = request.form.get("faculty_name", "Faculty").strip()

    if decision not in ("CONFIRMED", "DISMISSED", "REFERRED"):
        flash("Invalid decision value.", "error")
        return redirect(url_for("view_report", report_id=report_id))

    ok = update_report_decision(report_id, decision, notes, faculty_name)
    if ok:
        flash(f"Decision recorded: {decision}", "success")
    else:
        flash("Report not found.", "error")
    return redirect(url_for("view_report", report_id=report_id))


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/students")
def students():
    all_students = get_all_students()
    return render_template("students.html",
                           students=all_students,
                           courses=SUPPORTED_COURSES)


@app.route("/students/add", methods=["POST"])
def add_student():
    name   = request.form.get("name", "").strip()
    course = request.form.get("course", "Other").strip()
    if not name:
        flash("Student name is required.", "error")
    else:
        add_or_update_student(name, course)
        flash(f"Student '{name}' added.", "success")
    return redirect(url_for("students"))


# ─────────────────────────────────────────────────────────────────────────────
# JSON API
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/reports")
def api_reports():
    return jsonify(get_all_reports())


@app.route("/api/report/<report_id>")
def api_report(report_id: str):
    r = get_report(report_id)
    if not r:
        return jsonify({"error": "Not found"}), 404
    return jsonify(r)


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(413)
def too_large(e):
    flash(f"File too large. Maximum size is {config.MAX_UPLOAD_MB} MB.", "error")
    return redirect(url_for("submit_form"))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
