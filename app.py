import json
import os
from pathlib import Path

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)

from data import COMPULSORY, SUBJECTS, build_demo_students
from datasets import (RESULT_FILTERS, SORTS, Dataset, Registry, matches,
                      natural_key, non_default, normalise_view_args,
                      sort_results)
from grading import PRACTICAL_MAX, THEORY_MAX
from upload import (CaseReport, ImportReport, classify, load_json, parse_case,
                    validate_student, validate_students)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me")  # only used to flash messages
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

PUBLIC_FILE = Path(__file__).with_name("P08_school_results_public.json")

REGISTRY = Registry()
REGISTRY.add(Dataset(
    "demo", "Demo school — 60 students",
    "Built in: generated from a fixed seed (data.py), with 11 hand-built edge cases",
    SUBJECTS, COMPULSORY, build_demo_students(),
))


# ---------- importing ----------

def import_cases(raw_cases, source):
    """Each valid case becomes a new dataset. Returns a list of CaseReport."""
    reports = []
    for position, raw in enumerate(raw_cases, start=1):
        case, label, error = parse_case(raw, position)
        report = CaseReport(label=label)
        reports.append(report)
        if error:
            report.error = error
            continue
        dataset = Dataset(REGISTRY.unique_id(label), label, source, case.subjects, case.compulsory)
        records = validate_students(case.students, dataset.subject_by_code, dataset.compulsory,
                                    dataset.optional_choices, (), report)
        if not records:
            report.error = "no valid students, so no dataset was created"
            continue
        for rec in records:
            dataset.put(rec)
        REGISTRY.add(dataset)
        report.dataset_id = dataset.id
        report.created = True
    return reports


def import_students(raw_students, dataset):
    report = CaseReport(label=dataset.title, dataset_id=dataset.id)
    records = validate_students(raw_students, dataset.subject_by_code, dataset.compulsory,
                                dataset.optional_choices, dataset.records.keys(), report)
    for rec in records:
        dataset.put(rec)
    return report


def load_public_cases():
    """Load the organisers' published case file at start-up if it ships with the app."""
    if not PUBLIC_FILE.exists():
        return
    data, error = load_json(PUBLIC_FILE.read_text(encoding="utf-8"))
    if error:
        app.logger.warning("Could not load %s: %s", PUBLIC_FILE.name, error)
        return
    kind, payload = classify(data)
    if kind == "cases":
        import_cases(payload, f"Organisers' published cases ({PUBLIC_FILE.name})")


load_public_cases()


# ---------- helpers ----------

@app.context_processor
def inject_globals():
    return {"datasets": list(REGISTRY), "THEORY_MAX": THEORY_MAX, "PRACTICAL_MAX": PRACTICAL_MAX}


def get_dataset(ds_id):
    ds = REGISTRY.get(ds_id)
    if ds is None:
        abort(404, description=f'There is no dataset called "{ds_id}".')
    return ds


def get_student(ds, sid):
    s = ds.results.get(sid)
    if s is None:
        abort(404, description=f'No student with roll "{sid}" in {ds.title}.')
    return s


class ClassSummary:
    ORDER = ["A+", "A", "A-", "B", "C", "D", "F"]

    def __init__(self, class_name, students):
        self.class_name = class_name
        self.count = len(students)
        passed = sum(1 for s in students if s.letter != "F")
        self.pass_rate = round(100 * passed / self.count) if self.count else 0
        self.passed = passed

        counts = {letter: 0 for letter in self.ORDER}
        for s in students:
            counts[s.letter] += 1
        self.distribution = [(letter, counts[letter]) for letter in self.ORDER]
        self._max_count = max(counts.values()) if students else 0

        fail_tally = {}
        for s in students:
            for sub in s.subjects:
                if sub.status in ("FAIL", "AB"):
                    fail_tally[sub.name] = fail_tally.get(sub.name, 0) + 1
        if fail_tally:
            self.worst_subject = max(fail_tally, key=lambda name: (fail_tally[name], name))
            self.worst_count = fail_tally[self.worst_subject]
        else:
            self.worst_subject, self.worst_count = "None", 0

    def bar_width(self, n):
        return round(100 * n / self._max_count) if self._max_count else 0


def marksheet_context(s):
    compulsory = s.compulsory_subjects
    return {
        "s": s,
        "compulsory_gp_list": " + ".join(f"{sub.grade_point:.1f}" for sub in compulsory),
        "compulsory_sum": sum(sub.grade_point for sub in compulsory),
    }


def render_ledger(ds, selected=None):
    view = normalise_view_args(request.args)
    classes = ds.class_names()
    if view["cls"] not in classes:
        view["cls"] = ""
    results = list(ds.results.values())
    ranks = {key: {r.student_id: i for i, r in enumerate(sort_results(results, key))} for key, _ in SORTS}
    rows = [(r, matches(r, view)) for r in sort_results(results, view["sort"])]
    summaries = [ClassSummary(c, [r for r in results if r.class_name == c]) for c in classes]
    ctx = {
        "ds": ds, "rows": rows, "ranks": ranks, "view": view, "view_args": non_default(view),
        "visible_count": sum(1 for _, v in rows if v), "classes": classes,
        "summaries": summaries, "sorts": SORTS, "result_filters": RESULT_FILTERS,
        "selected": selected, "active": "ledger",
    }
    if selected is not None:
        ctx.update(marksheet_context(selected))
    return render_template("ledger.html", **ctx)


# ---------- pages ----------

@app.route("/")
def home():
    return redirect(url_for("ledger", ds_id=REGISTRY.first().id))


@app.route("/go")
def go():
    """Dataset switcher target (works without JavaScript)."""
    ds = get_dataset(request.args.get("ds", ""))
    page = "checklist" if request.args.get("page") == "checklist" else "ledger"
    return redirect(url_for(page, ds_id=ds.id))


@app.route("/d/<ds_id>/")
def ledger(ds_id):
    return render_ledger(get_dataset(ds_id))


@app.route("/d/<ds_id>/s/<sid>")
def student_view(ds_id, sid):
    ds = get_dataset(ds_id)
    s = get_student(ds, sid)
    if request.args.get("partial") == "1":
        view = normalise_view_args(request.args)
        return render_template("_panel.html", ds=ds, view_args=non_default(view), **marksheet_context(s))
    return render_ledger(ds, selected=s)


@app.route("/d/<ds_id>/s/<sid>/print")
def student_print(ds_id, sid):
    ds = get_dataset(ds_id)
    return render_template("print.html", ds=ds, **marksheet_context(get_student(ds, sid)))


def _form_value(raw):
    """Edit-form text -> organiser JSON value, so the form goes through the
    exact validator an uploaded file does. Blank is kept as a string so the
    validator rejects it instead of it silently becoming AB or 0."""
    raw = (raw or "").strip()
    if raw.upper() == "AB":
        return "AB"
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw


@app.route("/d/<ds_id>/s/<sid>/edit", methods=["GET", "POST"])
def student_edit(ds_id, sid):
    ds = get_dataset(ds_id)
    s = get_student(ds, sid)
    record = ds.records[sid]
    view_args = non_default(normalise_view_args(request.args))

    if request.method == "POST":
        optional = request.form.get("optional", "")
        marks = {}
        for code in ds.compulsory + ([optional] if optional in ds.optional_choices else []):
            if ds.subject_by_code[code]["practical"]:
                marks[code] = {"theory": _form_value(request.form.get(f"{code}_theory")),
                               "practical": _form_value(request.form.get(f"{code}_practical"))}
            else:
                marks[code] = _form_value(request.form.get(code))
        raw = {"id": sid, "name": request.form.get("name", ""), "class": request.form.get("class", ""),
               "optional": optional, "marks": marks}
        taken = set(ds.records) - {sid}
        rec, _, reasons = validate_student(raw, ds.subject_by_code, ds.compulsory, ds.optional_choices, taken)
        if reasons:
            for reason in reasons:
                flash(reason, "error")
            return render_template("edit.html", ds=ds, s=s, record=raw, form=request.form,
                                   view_args=view_args, active="ledger"), 400
        ds.put(rec)
        flash(f"Saved {rec['name']}. The marksheet below has been re-graded.", "success")
        return redirect(url_for("student_view", ds_id=ds.id, sid=sid, **view_args))

    return render_template("edit.html", ds=ds, s=s, record=record, form=None,
                           view_args=view_args, active="ledger")


@app.route("/d/<ds_id>/checklist")
def checklist(ds_id):
    ds = get_dataset(ds_id)
    students = sorted(ds.results.values(), key=lambda r: (natural_key(r.class_name), natural_key(r.student_id)))

    def reason_for(student, kind):
        if kind == "optional":
            opt = student.optional_subject
            if opt.status == "AB":
                return f"{opt.name} (optional) not sat — AB, contributes 0 to the GPA."
            return f"{opt.name} (optional) grade point {opt.grade_point:.1f} — 2.0 or below, adds nothing to the GPA."
        if kind == "practical":
            parts = [f"{sub.name} practical {sub.practical_mark}/{PRACTICAL_MAX}"
                     for sub in student.subjects
                     if sub.is_practical and sub.practical_mark is not None and sub.practical_mark < 8]
            return "Below the practical pass mark of 8: " + ", ".join(parts) + "."
        names = [sub.name + (" (optional)" if sub.is_optional else "") for sub in student.subjects if sub.status == "AB"]
        return "Marked AB in: " + ", ".join(names) + "."

    def make_list(title, rule_text, kind):
        entries = [{"s": s, "reason": reason_for(s, kind)} for s in students if kind in s.flags]
        return {"title": title, "rule_text": rule_text, "kind": kind, "students": entries}

    lists = [
        make_list("Optional-subject list",
                  "R-29 — every student whose optional grade point is 2.0 or below (an absent optional counts).",
                  "optional"),
        make_list("Practical-fail list",
                  "R-29 — every student with a practical part below 8 in any subject.", "practical"),
        make_list("Absent list", "R-29 — every student with AB in any subject.", "absent"),
    ]
    return render_template("checklists.html", ds=ds, lists=lists, active="checklist")


@app.route("/d/<ds_id>/results.json")
def results_json(ds_id):
    """Every graded result in the dataset, for checking against another tool."""
    ds = get_dataset(ds_id)
    students = []
    for r in sort_results(list(ds.results.values()), "roll"):
        subjects = []
        for sub in r.subjects:
            entry = {"code": sub.code, "name": sub.name, "optional": sub.is_optional,
                     "practical": sub.is_practical}
            if sub.is_practical:
                entry["theory"] = "AB" if sub.theory_mark is None else sub.theory_mark
                entry["practical_mark"] = "AB" if sub.practical_mark is None else sub.practical_mark
            else:
                entry["mark"] = "AB" if sub.single_mark is None else sub.single_mark
            entry.update({"grade_point": sub.grade_point, "status": sub.status, "rule": sub.rule})
            subjects.append(entry)
        students.append({
            "id": r.student_id, "name": r.name, "class": r.class_name,
            "optional": r.optional_subject.code if r.optional_subject else None,
            "gpa": f"{r.gpa:.2f}", "letter": r.letter, "uncancelled_gpa": f"{r.raw_gpa:.2f}",
            "failed_compulsory": [sub.code for sub in r.failing_subjects],
            "checking_lists": r.flags, "subjects": subjects,
        })
    body = json.dumps({"dataset": ds.id, "title": ds.title, "students": students}, indent=2, ensure_ascii=False)
    return Response(body, mimetype="application/json")


EXAMPLE_STUDENTS = [
    {"id": "N001", "name": "Example Pass", "class": "Class 9", "optional": "HMT",
     "marks": {"BAN": 78, "ENG": 71, "MAT": 85, "PHY": {"theory": 60, "practical": 21},
               "CHE": {"theory": 55, "practical": 19}, "BIO": {"theory": 58, "practical": 20},
               "HMT": {"theory": 62, "practical": 22}}},
    {"id": "N002", "name": "Example Absent", "class": "Class 10", "optional": "REL",
     "marks": {"BAN": 64, "ENG": "AB", "MAT": 70, "PHY": {"theory": 50, "practical": 15},
               "CHE": {"theory": 48, "practical": 14}, "BIO": {"theory": 52, "practical": 16}, "REL": 72}},
    {"id": "N003", "name": "Bad Range", "class": "Class 9", "optional": "AGR",
     "marks": {"BAN": 104, "ENG": 60, "MAT": 70, "PHY": {"theory": 80, "practical": 15},
               "CHE": {"theory": 48, "practical": 14}, "BIO": {"theory": 52, "practical": 16},
               "AGR": {"theory": 50, "practical": 20}}},
    {"id": "S001", "name": "Duplicate Roll", "class": "Class 9", "optional": "ICT",
     "marks": {"BAN": 60, "ENG": 60, "MAT": 60, "PHY": {"theory": 50, "practical": 15},
               "CHE": {"theory": 48, "practical": 14}}},
]


@app.route("/upload", methods=["GET", "POST"])
def upload():
    target_id = request.values.get("target") or "demo"
    ctx = {"active": "upload", "report": None, "target_id": target_id,
           "example_json": json.dumps({"students": EXAMPLE_STUDENTS}, indent=2)}
    if request.method == "GET":
        return render_template("upload.html", **ctx)

    uploaded = request.files.get("json_file")
    if uploaded and uploaded.filename:
        text = uploaded.read().decode("utf-8", errors="replace")
        source = f"Uploaded file {uploaded.filename}"
    else:
        text = request.form.get("pasted_json", "")
        source = "Pasted on the upload page"

    report = ImportReport()
    ctx["report"] = report
    data, report.error = load_json(text)
    if not report.error:
        kind, payload = classify(data)
        if kind == "error":
            report.error = payload
        elif kind == "cases":
            report.cases = import_cases(payload, source)
        else:
            target = REGISTRY.get(target_id)
            if target is None:
                report.error = "Choose which dataset these students should be added to."
            else:
                report.cases = [import_students(payload, target)]

    status = 400 if report.error or (report.cases and not report.accepted_count) else 200
    return render_template("upload.html", **ctx), status


# ---------- old URLs and errors ----------

@app.route("/student/<sid>")
def legacy_student(sid):
    return redirect(url_for("student_view", ds_id="demo", sid=sid))


@app.route("/checklist")
def legacy_checklist():
    return redirect(url_for("checklist", ds_id="demo"))


@app.errorhandler(404)
def not_found(err):
    return render_template("error.html", title="Not found", message=err.description,
                           active=None), 404


@app.errorhandler(413)
def too_large(err):
    return render_template("error.html", title="File too large",
                           message="Uploads are limited to 8 MB. Split the file into smaller cases.",
                           active="upload"), 413


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
