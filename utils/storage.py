"""
utils/storage.py
Lightweight JSON-based persistence for students, submissions, and reports.
No external database required – everything lives in the data/ folder.
"""

import os
import json
import uuid
import hashlib
from datetime import datetime

DATA_DIR      = "data"
STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.json")
REPORTS_FILE  = os.path.join(DATA_DIR, "reports.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("reports", exist_ok=True)


def _load(path: str) -> list:
    _ensure_dir()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(path: str, data: list):
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Student helpers ───────────────────────────────────────────────────────────

def get_all_students() -> list[dict]:
    return _load(STUDENTS_FILE)


def get_student(student_id: str) -> dict | None:
    return next((s for s in _load(STUDENTS_FILE) if s["id"] == student_id), None)


def add_or_update_student(name: str, course: str,
                           student_id: str | None = None) -> dict:
    students = _load(STUDENTS_FILE)
    if student_id:
        for s in students:
            if s["id"] == student_id:
                s["name"]   = name
                s["course"] = course
                _save(STUDENTS_FILE, students)
                return s
    # create new
    student = {
        "id":        str(uuid.uuid4())[:8].upper(),
        "name":      name,
        "course":    course,
        "created_at": datetime.utcnow().isoformat(),
    }
    students.append(student)
    _save(STUDENTS_FILE, students)
    return student


# ── Submission helpers ────────────────────────────────────────────────────────

def save_submission(student_id: str, assignment_title: str,
                    text: str, filename: str) -> dict:
    submissions = _load(SUBMISSIONS_FILE)
    submission = {
        "id":              str(uuid.uuid4()),
        "student_id":      student_id,
        "assignment_title": assignment_title,
        "filename":        filename,
        "text_hash":       hashlib.sha256(text.encode()).hexdigest()[:16],
        "text":            text[:50_000],   # cap stored text at 50k chars
        "submitted_at":    datetime.utcnow().isoformat(),
    }
    submissions.append(submission)
    _save(SUBMISSIONS_FILE, submissions)
    return submission


def get_student_submissions(student_id: str) -> list[dict]:
    return [s for s in _load(SUBMISSIONS_FILE) if s["student_id"] == student_id]


def get_all_submissions() -> list[dict]:
    return _load(SUBMISSIONS_FILE)


# ── Report helpers ────────────────────────────────────────────────────────────

def save_report(report: dict) -> dict:
    reports = _load(REPORTS_FILE)
    if "id" not in report:
        report["id"] = str(uuid.uuid4())
    report["created_at"] = datetime.utcnow().isoformat()
    reports.append(report)
    _save(REPORTS_FILE, reports)
    return report


def get_report(report_id: str) -> dict | None:
    return next((r for r in _load(REPORTS_FILE) if r["id"] == report_id), None)


def get_all_reports() -> list[dict]:
    return sorted(_load(REPORTS_FILE),
                  key=lambda r: r.get("created_at", ""), reverse=True)


def update_report_decision(report_id: str, decision: str,
                            notes: str, faculty_name: str) -> bool:
    reports = _load(REPORTS_FILE)
    for r in reports:
        if r["id"] == report_id:
            r["faculty_decision"] = decision
            r["faculty_notes"]    = notes
            r["faculty_name"]     = faculty_name
            r["decided_at"]       = datetime.utcnow().isoformat()
            _save(REPORTS_FILE, reports)
            return True
    return False
