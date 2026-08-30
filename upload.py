"""
Parses and validates a teacher-supplied marks sheet (CSV, or pasted text in
the same shape) and turns each row into either:

  - an accepted student record, in the same shape data.py produces
    ({"id", "name", "class_name", "marks"}), ready for grading.py, or
  - a rejection: the 1-based row number (counting the header as row 1, so
    the first data row is row 2 — matching what a spreadsheet shows) plus
    a specific, human-readable reason.

Nothing here decides pass/fail — that's grading.py's job. This module only
answers "is this row well-formed enough to grade at all?".

## Required file format

A CSV (or pasted CSV text) with a header row. Required columns:

  student_id, name, class_name

...plus one column per ordinary (non-practical) subject, named after the
subject code, and TWO columns per practical subject: ``<code>_theory`` and
``<code>_practical``.

For the standard 7-subject roster (data.SUBJECTS) that header row is:

  student_id,name,class_name,BAN,ENG,MATH,SCI_theory,SCI_practical,REL,ICT_theory,ICT_practical,HMATH

Column order does not matter, but every required column must be present
(case-insensitive match; spaces/hyphens in header names are treated as
underscores). Marks are accepted as:

  - a plain integer, 0-100 for an ordinary subject or a practical's
    combined range (0-75 for a *_theory column, 0-8..25 for a
    *_practical column — see exact bounds below)
  - the literal ``AB`` (any case) for a student absent in that
    subject/part

An empty cell is NOT treated as AB — it's rejected, so a blank cell can
never silently become an absence. Use ``AB`` explicitly.
"""

import csv
import io
from dataclasses import dataclass

from grading import THEORY_MAX, PRACTICAL_MAX


REQUIRED_ID_COLUMNS = ["student_id", "name", "class_name"]


@dataclass
class ColumnSpec:
    header: str          # exact header name expected in the CSV
    subject_code: str
    subject_name: str
    kind: str            # "ordinary" | "theory" | "practical"


def build_column_specs(subjects):
    """One ColumnSpec per required mark column, driven by the live roster
    (data.SUBJECTS) so the format always matches whatever subjects are
    actually configured."""
    specs = []
    for s in subjects:
        if s["practical"]:
            specs.append(ColumnSpec(f"{s['code']}_theory", s["code"], s["name"], "theory"))
            specs.append(ColumnSpec(f"{s['code']}_practical", s["code"], s["name"], "practical"))
        else:
            specs.append(ColumnSpec(s["code"], s["code"], s["name"], "ordinary"))
    return specs


def expected_header(subjects):
    specs = build_column_specs(subjects)
    return REQUIRED_ID_COLUMNS + [s.header for s in specs]


def _normalize_key(k):
    return (k or "").strip().lower().replace("-", "_").replace(" ", "_")


def _mark_bounds(kind):
    if kind == "ordinary":
        return 0, 100
    if kind == "theory":
        return 0, THEORY_MAX
    if kind == "practical":
        return 0, PRACTICAL_MAX
    raise ValueError(kind)


def _parse_mark_cell(raw, colname, kind, errors):
    """Returns a mark value (int) or None (AB), appending to `errors` (a
    list of strings) and returning a sentinel object on any problem so the
    caller can tell the row is unusable."""
    text = (raw or "").strip()
    if text == "":
        errors.append(f"'{colname}' is empty — leave marks blank for nothing; use AB for absent")
        return _INVALID
    if text.upper() == "AB":
        return None
    try:
        value = int(text)
    except ValueError:
        errors.append(f"'{colname}' = '{raw}' is not a whole number or AB")
        return _INVALID
    lo, hi = _mark_bounds(kind)
    if value < lo or value > hi:
        errors.append(f"'{colname}' = {value} is out of range ({lo}-{hi})")
        return _INVALID
    return value


class _Invalid:
    def __repr__(self):
        return "<invalid>"


_INVALID = _Invalid()


def parse_and_validate(file_text, subjects, existing_ids=None):
    """
    file_text: the raw CSV text (str).
    subjects:  data.SUBJECTS (or an equivalent roster).
    existing_ids: iterable of student IDs already in the system, so
                   duplicates against the *existing* roster are caught too
                   (duplicates *within* the uploaded file are always caught).

    Returns (accepted, rejected):
      accepted: list of {"id", "name", "class_name", "marks"} dicts,
                ready for grading.evaluate_student.
      rejected: list of {"row": int, "student_id": str, "reason": str}
                dicts. `row` counts the header as row 1, so the first data
                row is row 2 (matches what a spreadsheet shows).
    """
    existing_ids = set(existing_ids or [])
    specs = build_column_specs(subjects)
    accepted = []
    rejected = []

    reader = csv.reader(io.StringIO(file_text))
    rows = list(reader)
    if not rows:
        return [], [{"row": 0, "student_id": "", "reason": "File is empty."}]

    raw_header = rows[0]
    header_map = {}  # normalized_name -> column_index
    for i, h in enumerate(raw_header):
        header_map[_normalize_key(h)] = i

    required_headers = REQUIRED_ID_COLUMNS + [s.header for s in specs]
    missing = [h for h in required_headers if _normalize_key(h) not in header_map]
    if missing:
        return [], [{
            "row": 1,
            "student_id": "",
            "reason": (
                "Header row is missing required column(s): " + ", ".join(missing) +
                ". Expected header: " + ",".join(required_headers)
            ),
        }]

    seen_ids_in_file = set()

    for row_num, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # silently skip fully blank lines

        errors = []

        def cell(colname):
            idx = header_map[_normalize_key(colname)]
            return row[idx].strip() if idx < len(row) else ""

        if len(row) < len(raw_header):
            errors.append(
                f"row has {len(row)} column(s), expected {len(raw_header)} — a value is missing"
            )

        student_id = cell("student_id")
        name = cell("name")
        class_name = cell("class_name")

        if not student_id:
            errors.append("missing student_id")
        elif student_id in seen_ids_in_file:
            errors.append(f"duplicate student_id '{student_id}' (already appears earlier in this file)")
        elif student_id in existing_ids:
            errors.append(
                f"student_id '{student_id}' already exists in the system "
                "— use the edit page to change an existing student's marks instead"
            )

        if not name:
            errors.append("missing name")
        if not class_name:
            errors.append("missing class_name")

        marks = {}
        if not errors:  # only bother parsing marks if the row is well-formed so far
            for spec in specs:
                value = _parse_mark_cell(cell(spec.header), spec.header, spec.kind, errors)
                entry = marks.setdefault(spec.subject_code, {})
                if spec.kind == "ordinary":
                    entry["mark"] = None if value is _INVALID else value
                elif spec.kind == "theory":
                    entry["theory"] = None if value is _INVALID else value
                elif spec.kind == "practical":
                    entry["practical"] = None if value is _INVALID else value

        if errors:
            rejected.append({
                "row": row_num,
                "student_id": student_id or "(none)",
                "reason": "; ".join(errors),
            })
            continue

        seen_ids_in_file.add(student_id)
        accepted.append({
            "id": student_id,
            "name": name,
            "class_name": class_name,
            "marks": marks,
        })

    return accepted, rejected