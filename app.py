from flask import Flask, render_template, abort, request, redirect, url_for, flash

from data import build_roster_and_students
from grading import evaluate_student, THEORY_MAX, PRACTICAL_MAX
from upload import parse_and_validate, expected_header

app = Flask(__name__)
app.secret_key = "dev-only-secret-key-change-me"  # only used to flash messages

SUBJECTS, RAW_STUDENTS = build_roster_and_students(total_students=60, seed=42)

# RAW_MARKS keeps the original entry dicts per student (subject_code -> entry)
# so the edit form can be pre-filled and so uploads/edits can be re-graded
# without needing to re-derive marks from a StudentResult.
RAW_MARKS = {}
RESULTS = {}


def _grade_and_store(student_id, name, class_name, marks):
    """(Re)compute a student's result and store both the raw marks and the
    graded result. Used at startup, after an upload, and after an edit."""
    RAW_MARKS[student_id] = marks
    RESULTS[student_id] = evaluate_student(student_id, name, class_name, SUBJECTS, marks)


for rec in RAW_STUDENTS:
    _grade_and_store(rec["id"], rec["name"], rec["class_name"], rec["marks"])


def _class_names():
    return sorted({r.class_name for r in RESULTS.values()})


class ClassView:
    def __init__(self, name, students):
        self.name = name
        self.students = sorted(students, key=lambda s: s.student_id)


class ClassSummary:
    def __init__(self, class_name, students):
        self.class_name = class_name
        self.count = len(students)
        passed = [s for s in students if s.letter != "F"]
        self.pass_rate = round(100 * len(passed) / self.count) if self.count else 0

        order = ["A+", "A", "A-", "B", "C", "D", "F"]
        counts = {letter: 0 for letter in order}
        for s in students:
            counts[s.letter] += 1
        self.distribution = [(letter, counts[letter]) for letter in order]
        self._max_count = max(counts.values()) if counts else 1

        fail_tally = {}
        for s in students:
            for sub in s.subjects:
                if sub.status in ("FAIL", "AB"):
                    fail_tally[sub.name] = fail_tally.get(sub.name, 0) + 1
        if fail_tally:
            self.worst_subject = max(fail_tally, key=fail_tally.get)
        else:
            self.worst_subject = "None"

    def bar_width(self, n):
        if self._max_count == 0:
            return 0
        return round(100 * n / self._max_count)


@app.route("/")
def index():
    classes = []
    summaries = []
    for cname in _class_names():
        students = [r for r in RESULTS.values() if r.class_name == cname]
        classes.append(ClassView(cname, students))
        summaries.append(ClassSummary(cname, students))
    return render_template("index.html", classes=classes, summaries=summaries, active="index")


@app.route("/student/<student_id>")
def student_page(student_id):
    s = RESULTS.get(student_id)
    if s is None:
        abort(404)
    compulsory_gp_list = " + ".join(
        f"{sub.grade_point:.1f}" for sub in s.subjects if not sub.is_optional
    )
    compulsory_sum = sum(sub.grade_point for sub in s.subjects if not sub.is_optional)
    return render_template(
        "student.html",
        s=s,
        active="student",
        compulsory_gp_list=compulsory_gp_list,
        compulsory_sum=compulsory_sum,
        printable=False,
    )


@app.route("/student/<student_id>/print")
def student_print(student_id):
    """Same marksheet, rendered without navigation chrome and with
    print-friendly styling so it can go straight to Ctrl+P / Cmd+P."""
    s = RESULTS.get(student_id)
    if s is None:
        abort(404)
    compulsory_gp_list = " + ".join(
        f"{sub.grade_point:.1f}" for sub in s.subjects if not sub.is_optional
    )
    compulsory_sum = sum(sub.grade_point for sub in s.subjects if not sub.is_optional)
    return render_template(
        "student.html",
        s=s,
        active="student",
        compulsory_gp_list=compulsory_gp_list,
        compulsory_sum=compulsory_sum,
        printable=True,
    )


@app.route("/student/<student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    s = RESULTS.get(student_id)
    if s is None:
        abort(404)
    marks = RAW_MARKS[student_id]

    if request.method == "POST":
        new_marks = {}
        errors = []
        for subject in SUBJECTS:
            code = subject["code"]
            if subject["practical"]:
                t_raw = request.form.get(f"{code}_theory", "").strip()
                p_raw = request.form.get(f"{code}_practical", "").strip()
                t = _parse_form_mark(t_raw, f"{subject['name']} (theory)", 0, THEORY_MAX, errors)
                p = _parse_form_mark(p_raw, f"{subject['name']} (practical)", 0, PRACTICAL_MAX, errors)
                new_marks[code] = {"theory": t, "practical": p}
            else:
                m_raw = request.form.get(code, "").strip()
                m = _parse_form_mark(m_raw, subject["name"], 0, 100, errors)
                new_marks[code] = {"mark": m}

        new_name = request.form.get("name", "").strip()
        new_class = request.form.get("class_name", "").strip()
        if not new_name:
            errors.append("Name cannot be empty.")
        if not new_class:
            errors.append("Class cannot be empty.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "edit.html", s=s, subjects=SUBJECTS, marks=marks,
                active="student", form=request.form,
            )

        _grade_and_store(student_id, new_name, new_class, new_marks)
        flash(f"Saved changes for {new_name}.", "success")
        return redirect(url_for("student_page", student_id=student_id))

    return render_template(
        "edit.html", s=s, subjects=SUBJECTS, marks=marks, active="student", form=None,
    )


def _parse_form_mark(raw, label, lo, hi, errors):
    """Edit-form version of the same rule an uploaded CSV cell follows:
    blank means AB is intended only via the explicit AB checkbox pattern
    isn't used here — instead an empty box means 'still AB' if it was AB
    before is NOT assumed; empty box always means AB for simplicity."""
    if raw == "" or raw.upper() == "AB":
        return None
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"{label}: '{raw}' is not a whole number or AB.")
        return None
    if value < lo or value > hi:
        errors.append(f"{label}: {value} is out of range ({lo}-{hi}).")
        return None
    return value


@app.route("/upload", methods=["GET", "POST"])
def upload():
    header = expected_header(SUBJECTS)
    header_line = ",".join(header)

    if request.method == "GET":
        return render_template(
            "upload.html", active="upload", header_line=header_line,
            subjects=SUBJECTS, accepted=None, rejected=None,
        )

    text = ""
    uploaded = request.files.get("csv_file")
    if uploaded and uploaded.filename:
        text = uploaded.read().decode("utf-8-sig", errors="replace")
    else:
        text = request.form.get("pasted_csv", "")

    if not text.strip():
        flash("Please choose a CSV file or paste marks-sheet text.", "error")
        return render_template(
            "upload.html", active="upload", header_line=header_line,
            subjects=SUBJECTS, accepted=None, rejected=None,
        )

    accepted, rejected = parse_and_validate(text, SUBJECTS, existing_ids=RESULTS.keys())

    for rec in accepted:
        _grade_and_store(rec["id"], rec["name"], rec["class_name"], rec["marks"])

    if accepted:
        flash(f"Added {len(accepted)} student(s).", "success")
    if rejected:
        flash(f"{len(rejected)} row(s) rejected — see details below.", "error")

    return render_template(
        "upload.html", active="upload", header_line=header_line,
        subjects=SUBJECTS, accepted=accepted, rejected=rejected,
    )


@app.route("/checklist")
def checklist():
    students = list(RESULTS.values())

    def reason_for(student, kind):
        if kind == "optional":
            opt = next(sub for sub in student.subjects if sub.is_optional)
            if opt.status == "AB":
                return "Optional subject not sat (AB) — contributes 0 to the GPA bonus."
            return f"Optional subject grade point {opt.grade_point:.1f} (2.0 or below) — contributes 0 to the GPA bonus."
        if kind == "practical":
            names = [sub.name for sub in student.subjects
                     if sub.is_practical and sub.status == "FAIL"
                     and sub.practical_mark is not None]
            return f"Practical mark below 8 in: {', '.join(names)}."
        if kind == "absent":
            names = [sub.name for sub in student.subjects if sub.status == "AB"]
            return f"Marked AB in: {', '.join(names)}."

    def make_list(title, rule_text, kind, predicate):
        entries = []
        for s in sorted(students, key=lambda x: x.student_id):
            if predicate(s):
                entries.append({
                    "student_id": s.student_id,
                    "name": s.name,
                    "class_name": s.class_name,
                    "reason": reason_for(s, kind),
                })
        return {"title": title, "rule_text": rule_text, "students": entries}

    lists = [
        make_list(
            "Optional-subject list", "R-29 — every student whose optional grade point is 2.0 or below (an absent optional counts).",
            "optional", lambda s: s.on_optional_list,
        ),
        make_list(
            "Practical-fail list", "R-29 — every student with a practical part below 8 in any subject.",
            "practical", lambda s: s.on_practical_fail_list,
        ),
        make_list(
            "Absent list", "R-29 — every student with AB in any subject.",
            "absent", lambda s: s.on_absent_list,
        ),
    ]
    return render_template("checklists.html", lists=lists, active="checklist")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)