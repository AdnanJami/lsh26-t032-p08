"""
In-memory datasets. A dataset is one "case" in the organisers' format: its own
subject list, its six compulsory codes, and its students. The built-in demo is
one dataset; every case in an uploaded file becomes another.

Student records are kept exactly as they arrive (organiser JSON shape) so the
edit form can be pre-filled and the export can round-trip them; the graded
StudentResult is derived from the record through grading.evaluate_student.
"""

import re

from grading import evaluate_student


def natural_key(text):
    """'Class 9' < 'Class 10', 'S2' < 'S10'."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(text))]


def to_engine_entry(value, practical):
    """Organiser mark value -> the entry dict grading.evaluate_subject reads.
    'AB' (absent) becomes None, which the engine reports as AB, never as 0."""
    if practical:
        if value == "AB":
            return {"theory": None, "practical": None}
        return {
            "theory": None if value["theory"] == "AB" else value["theory"],
            "practical": None if value["practical"] == "AB" else value["practical"],
        }
    return {"mark": None if value == "AB" else value}


class Dataset:
    def __init__(self, ds_id, title, source, subjects, compulsory, students=()):
        self.id = ds_id
        self.title = title
        self.source = source
        self.subjects = [dict(s) for s in subjects]
        self.subject_by_code = {s["code"]: s for s in self.subjects}
        self.compulsory = list(compulsory)
        self.optional_choices = [s["code"] for s in self.subjects if s["code"] not in self.compulsory]
        self.records = {}
        self.results = {}
        for rec in students:
            self.put(rec)

    def subject_name(self, code):
        return self.subject_by_code[code]["name"]

    def engine_subjects(self, optional_code):
        return [
            {
                "code": code,
                "name": self.subject_by_code[code]["name"],
                "practical": self.subject_by_code[code]["practical"],
                "optional": code == optional_code,
            }
            for code in self.compulsory + [optional_code]
        ]

    def put(self, rec):
        """Add or replace one student and (re)grade them."""
        subjects = self.engine_subjects(rec["optional"])
        marks = {s["code"]: to_engine_entry(rec["marks"][s["code"]], s["practical"]) for s in subjects}
        self.records[rec["id"]] = rec
        self.results[rec["id"]] = evaluate_student(rec["id"], rec["name"], rec["class"], subjects, marks)

    def class_names(self):
        return sorted({r.class_name for r in self.results.values()}, key=natural_key)

    def __len__(self):
        return len(self.results)


class Registry:
    """Ordered collection of datasets, keyed by a URL-safe id."""

    def __init__(self):
        self._by_id = {}

    def __iter__(self):
        return iter(self._by_id.values())

    def __len__(self):
        return len(self._by_id)

    def get(self, ds_id):
        return self._by_id.get(ds_id)

    def first(self):
        return next(iter(self._by_id.values()), None)

    def unique_id(self, wanted):
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", wanted).strip("-") or "case"
        ds_id, n = base, 2
        while ds_id in self._by_id:
            ds_id = f"{base}-{n}"
            n += 1
        return ds_id

    def add(self, dataset):
        self._by_id[dataset.id] = dataset
        return dataset


# ---------- list view: search / filter / sort ----------

SORTS = [
    ("roll", "Roll number"),
    ("name", "Name (A–Z)"),
    ("gpa_desc", "GPA (high → low)"),
    ("gpa_asc", "GPA (low → high)"),
    ("avg_desc", "Uncancelled average (high → low)"),
    ("class", "Class, then roll"),
]
RESULT_FILTERS = [
    ("all", "All results"),
    ("pass", "Passed"),
    ("fail", "Failed"),
    ("flagged", "On any checking list"),
    ("optional", "Optional-subject list"),
    ("practical", "Practical-fail list"),
    ("absent", "Absent list"),
]
SORT_KEYS = {k for k, _ in SORTS}
RESULT_KEYS = {k for k, _ in RESULT_FILTERS}


def normalise_view_args(args):
    """Query-string args -> a clean view state (unknown values fall back)."""
    q = (args.get("q") or "").strip()
    sort = args.get("sort") if args.get("sort") in SORT_KEYS else "roll"
    result = args.get("result") if args.get("result") in RESULT_KEYS else "all"
    cls = (args.get("cls") or "").strip()
    return {"q": q, "sort": sort, "result": result, "cls": cls}


def non_default(view):
    """Only the view args that differ from the defaults, for tidy URLs."""
    defaults = {"q": "", "sort": "roll", "result": "all", "cls": ""}
    return {k: v for k, v in view.items() if v != defaults[k]}


def matches(result, view):
    if view["cls"] and result.class_name != view["cls"]:
        return False
    r = view["result"]
    if r == "pass" and result.letter == "F":
        return False
    if r == "fail" and result.letter != "F":
        return False
    if r == "flagged" and not result.flags:
        return False
    if r in ("optional", "practical", "absent") and r not in result.flags:
        return False
    haystack = f"{result.student_id} {result.name}".lower()
    return all(token in haystack for token in view["q"].lower().split())


def sort_results(results, sort):
    roll = lambda r: natural_key(r.student_id)
    if sort == "name":
        return sorted(results, key=lambda r: (r.name.lower(), roll(r)))
    if sort == "gpa_desc":
        return sorted(results, key=lambda r: (-r.gpa, -r.raw_gpa, roll(r)))
    if sort == "gpa_asc":
        return sorted(results, key=lambda r: (r.gpa, r.raw_gpa, roll(r)))
    if sort == "avg_desc":
        return sorted(results, key=lambda r: (-r.raw_gpa, roll(r)))
    if sort == "class":
        return sorted(results, key=lambda r: (natural_key(r.class_name), roll(r)))
    return sorted(results, key=roll)
