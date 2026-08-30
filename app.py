from flask import Flask, render_template, abort

from data import build_roster_and_students
from grading import evaluate_student

app = Flask(__name__)

SUBJECTS, RAW_STUDENTS = build_roster_and_students(total_students=60, seed=42)

# Evaluate every student once at startup; this is a read-heavy demo tool,
# not a system taking live data-entry, so there's no need to recompute
# per-request.
RESULTS = {}
for rec in RAW_STUDENTS:
    result = evaluate_student(rec["id"], rec["name"], rec["class_name"], SUBJECTS, rec["marks"])
    RESULTS[rec["id"]] = result

CLASS_NAMES = sorted({r.class_name for r in RESULTS.values()})


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

        # Subject that failed the most students (FAIL or AB counts as failing it).
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
    for cname in CLASS_NAMES:
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