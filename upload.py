"""
Parses and validates marks supplied as JSON in the organisers' case format and
reports, per student, either "accepted" or every reason it was rejected.

Nothing here decides pass/fail -- that is grading.py's job. This module only
answers "is this record well-formed enough to grade at all?".

Three shapes are accepted:

1. The full published file:     {"cases": [case, case, ...], ...}
2. A single case:               {"case_id": "PUB-01", "subjects": [...],
                                 "compulsory": [...], "students": [...]}
   -> each case becomes a new dataset (its own ledger and checklist).
3. Just students:               {"students": [...]}  or  [student, ...]
   -> added to an existing dataset chosen on the upload page, using that
      dataset's subjects.

A student is:
  {"id": "S001", "name": "Arif Hossain", "class": "Class 9", "optional": "HMT",
   "marks": {"BAN": 55, "PHY": {"theory": 60, "practical": 20}, "BIO": "AB", ...}}

A subject without a practical part is one whole number 0-100. A subject with a
practical part is {"theory": 0-75, "practical": 0-25}. "AB" means absent, for
the whole subject (or, for a practical subject, for one part). A student has
exactly the six compulsory marks plus the mark for their own optional subject.
"""

import json
from dataclasses import dataclass, field

from grading import THEORY_MAX, PRACTICAL_MAX

REQUIRED_COMPULSORY = 6


@dataclass
class CaseReport:
    label: str
    dataset_id: str = ""
    created: bool = False
    error: str = ""
    accepted: list = field(default_factory=list)   # student ids
    rejected: list = field(default_factory=list)   # {"index", "student_id", "reasons"}


@dataclass
class ImportReport:
    error: str = ""
    cases: list = field(default_factory=list)

    @property
    def accepted_count(self):
        return sum(len(c.accepted) for c in self.cases)

    @property
    def rejected_count(self):
        return sum(len(c.rejected) for c in self.cases)


class ParsedCase:
    """A structurally valid case, before its students are validated."""

    def __init__(self, label, subjects, compulsory, students):
        self.label = label
        self.subjects = subjects
        self.compulsory = compulsory
        self.students = students


def load_json(text):
    """Returns (data, error_message)."""
    text = text.lstrip("﻿")
    if not text.strip():
        return None, "Nothing to import: the file or text box is empty."
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return None, (
            f"Not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}. "
            "Nothing was imported."
        )


def classify(data):
    """Returns ("cases", [raw_case, ...]) | ("students", [raw_student, ...])
    | ("error", message)."""
    if isinstance(data, list):
        return "students", data
    if not isinstance(data, dict):
        return "error", "Expected a JSON object or array at the top level."
    if "cases" in data:
        if not isinstance(data["cases"], list) or not data["cases"]:
            return "error", '"cases" must be a non-empty array of case objects.'
        return "cases", data["cases"]
    if "subjects" in data or "compulsory" in data:
        return "cases", [data]
    if "students" in data:
        if not isinstance(data["students"], list):
            return "error", '"students" must be an array.'
        return "students", data["students"]
    return "error", (
        'Unrecognised JSON: expected {"cases": [...]}, a single case with '
        '"subjects", "compulsory" and "students", or {"students": [...]}.'
    )


def parse_case(raw, position):
    """Validates a case's structure. Returns (ParsedCase | None, label, error)."""
    if not isinstance(raw, dict):
        return None, f"Case {position}", "case is not a JSON object"
    label = raw.get("case_id") if isinstance(raw.get("case_id"), str) and raw.get("case_id").strip() else f"Case {position}"
    label = label.strip()

    problems = []
    subjects = raw.get("subjects")
    clean_subjects = []
    if not isinstance(subjects, list) or not subjects:
        problems.append('"subjects" must be a non-empty array')
    else:
        seen = set()
        for i, s in enumerate(subjects, start=1):
            if not isinstance(s, dict):
                problems.append(f"subject #{i} is not an object")
                continue
            code, name, practical = s.get("code"), s.get("name"), s.get("practical")
            if not isinstance(code, str) or not code.strip():
                problems.append(f'subject #{i} has no "code"')
                continue
            code = code.strip()
            if code in seen:
                problems.append(f"subject code {code} is listed twice")
            seen.add(code)
            if not isinstance(name, str) or not name.strip():
                problems.append(f'subject {code} has no "name"')
            if not isinstance(practical, bool):
                problems.append(f'subject {code}: "practical" must be true or false')
            clean_subjects.append({"code": code, "name": (name or code).strip() if isinstance(name, str) else code,
                                   "practical": practical is True})

    codes = {s["code"] for s in clean_subjects}
    compulsory = raw.get("compulsory")
    if not isinstance(compulsory, list) or not all(isinstance(c, str) for c in compulsory):
        problems.append('"compulsory" must be an array of subject codes')
        compulsory = []
    else:
        compulsory = [c.strip() for c in compulsory]
        if len(compulsory) != REQUIRED_COMPULSORY or len(set(compulsory)) != len(compulsory):
            problems.append(f'"compulsory" must list {REQUIRED_COMPULSORY} different subject codes (got {len(compulsory)})')
        unknown = [c for c in compulsory if c not in codes]
        if unknown and clean_subjects:
            problems.append(f"compulsory code(s) {', '.join(unknown)} are not in \"subjects\"")
        if clean_subjects and not (codes - set(compulsory)):
            problems.append("no optional subject is left once the compulsory ones are taken out")

    students = raw.get("students")
    if not isinstance(students, list):
        problems.append('"students" must be an array')

    if problems:
        return None, label, "; ".join(problems)
    return ParsedCase(label, clean_subjects, compulsory, students), label, ""


def _mark(value, where, lo, hi, reasons):
    """Returns a clean mark (int or 'AB'), or None after recording a reason."""
    if isinstance(value, str):
        if value.strip().upper() == "AB":
            return "AB"
        reasons.append(f'{where} is the text "{value}" — use a whole number or "AB"')
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        reasons.append(f"{where} must be a whole number {lo}–{hi} or \"AB\" (got {json.dumps(value)})")
        return None
    if isinstance(value, float):
        if not value.is_integer():
            reasons.append(f"{where} = {value} is not a whole number")
            return None
        value = int(value)
    if not lo <= value <= hi:
        reasons.append(f"{where} = {value} is out of range ({lo}–{hi})")
        return None
    return value


def validate_student(raw, subject_by_code, compulsory, optional_choices, taken_ids):
    """Returns (clean_record | None, student_id_for_report, reasons)."""
    if not isinstance(raw, dict):
        return None, "(none)", ["entry is not a JSON object"]
    reasons = []

    sid = raw.get("id")
    if isinstance(sid, int) and not isinstance(sid, bool):
        sid = str(sid)
    if not isinstance(sid, str) or not sid.strip():
        reasons.append('missing "id"')
        sid = ""
    else:
        sid = sid.strip()
        if "/" in sid or "?" in sid or "#" in sid:
            reasons.append(f'id "{sid}" must not contain "/", "?" or "#"')
        elif sid in taken_ids:
            reasons.append(f'id "{sid}" is already used in this dataset — edit that student instead')

    clean = {"id": sid}
    for key in ("name", "class"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f'missing "{key}"')
        else:
            clean[key] = value.strip()

    optional = raw.get("optional")
    if not isinstance(optional, str) or not optional.strip():
        reasons.append(f'missing "optional" (one of {", ".join(optional_choices)})')
        optional = None
    else:
        optional = optional.strip()
        if optional in compulsory:
            reasons.append(f'"optional" is {optional}, which is already a compulsory subject')
            optional = None
        elif optional not in optional_choices:
            reasons.append(f'"optional" is {optional}; it must be one of {", ".join(optional_choices)}')
            optional = None
    clean["optional"] = optional

    marks = raw.get("marks")
    if not isinstance(marks, dict):
        reasons.append('missing "marks" object')
        return None, sid or "(none)", reasons

    expected = compulsory + ([optional] if optional else [])
    for code in expected:
        if code not in marks:
            reasons.append(f'no mark for {subject_by_code[code]["name"]} ({code}) — use "AB" if absent')
    extra = [c for c in marks if c not in expected and not (optional is None and c in optional_choices)]
    for code in extra:
        if code in subject_by_code:
            reasons.append(f"mark given for {subject_by_code[code]['name']} ({code}), which is not one of this student's subjects")
        else:
            reasons.append(f"mark given for unknown subject code {code}")

    clean_marks = {}
    for code in expected:
        if code not in marks:
            continue
        subject = subject_by_code[code]
        value = marks[code]
        if subject["practical"]:
            if isinstance(value, str) and value.strip().upper() == "AB":
                clean_marks[code] = "AB"
                continue
            if not isinstance(value, dict):
                reasons.append(
                    f'{subject["name"]} ({code}) has a practical part: give '
                    f'{{"theory": 0–{THEORY_MAX}, "practical": 0–{PRACTICAL_MAX}}} or "AB"'
                )
                continue
            for part in value:
                if part not in ("theory", "practical"):
                    reasons.append(f'{code} has an unexpected key "{part}"')
            parts = {}
            for part, hi in (("theory", THEORY_MAX), ("practical", PRACTICAL_MAX)):
                if part not in value:
                    reasons.append(f"{code} is missing its {part} mark")
                    continue
                parts[part] = _mark(value[part], f"{code} {part}", 0, hi, reasons)
            if len(parts) == 2 and None not in parts.values():
                clean_marks[code] = parts
        else:
            m = _mark(value, code, 0, 100, reasons)
            if m is not None:
                clean_marks[code] = m

    if reasons:
        return None, sid or "(none)", reasons
    clean["marks"] = clean_marks
    return clean, sid, []


def validate_students(raw_students, subject_by_code, compulsory, optional_choices, existing_ids, report):
    """Fills report.accepted / report.rejected; returns the clean records."""
    taken = set(existing_ids)
    records = []
    for index, raw in enumerate(raw_students, start=1):
        rec, sid, reasons = validate_student(raw, subject_by_code, compulsory, optional_choices, taken)
        if rec is None:
            report.rejected.append({"index": index, "student_id": sid, "reasons": reasons})
            continue
        taken.add(rec["id"])
        records.append(rec)
        report.accepted.append(rec["id"])
    return records
