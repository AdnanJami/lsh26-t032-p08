# Result Register & GPA Engine

Solution for **LofiStack Hackathon 2026 — P08**

## Project information

- **Team:** `Larpcoder`
- **Team ID:** `LSH26-T032`
- **Problem:** `P08 — School Result Processing and GPA Engine`
- **Live application:** <https://lsh26-t032-p08.onrender.com/>
## Solution summary

A Flask app that grades 60 students across two classes under the school's published GPA rules (R-10 to R-13, R-29), and shows the working, not just the result: every subject on a student's marksheet carries the exact mark, the grade point it produced, and the rule that decided it, so a compulsory failure that cancels a strong average is visible rather than hidden behind a flat "F." A class ledger gives pass rate, grade distribution and the subject failing the most students per class, and an office checklist lists every student whose result was touched by the optional-subject rule, a practical fail, or an absence, with a reason per student. Beyond the four required items, the app also supports uploading a CSV of additional marks (with per-row validation and rejection reasons) and editing an individual student's marks in place, both re-grading through the same rules engine used everywhere else.

## Requirements

| Requirement                                                                                 | Status   | Where to verify                                                                                  |
| -------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| R1 — 60 students, 2 classes, 6 compulsory + 1 optional subject each, 8 hand-built edge cases  | Complete | `data.py` → `build_roster_and_students()`, `_edge_case_students()`                                 |
| R2 — Grade point per subject, final GPA, letter grade per student                            | Complete | `grading.py` → `evaluate_subject()`, `evaluate_student()`; `/student/<id>` route, `student.html`   |
| R3 — Per-student trace: mark used, grade point, deciding rule; failing subject shown for high-average fails | Complete | `templates/student.html` (per-subject trace cards + "uncancelled average" note on compulsory fail) |
| R4 — Office checking list: optional, practical-fail, and absent lists with reasons             | Complete | `/checklist` route in `app.py`, `templates/checklists.html`                                        |

## How to test the application

1. Open the live application — you land on the **Ledger**, showing both classes' pass rate, grade distribution, and rosters.
2. Click any student's name to open their **individual trace** — every subject's mark, grade point, and rule (e.g. R-11, R-12) is shown, with the subject that caused a failure highlighted if applicable.
3. Open **Office checklist** in the nav to see the three R-29 lists (optional, practical-fail, absent), each with a per-student reason.
4. Optionally, try **Upload marks** to add a small CSV of new students (the page documents the exact column format and shows accepted/rejected rows with reasons), or **Edit** a student from the ledger to change their marks and see the marksheet re-grade live.

### Test or sample data

The 60-student dataset is not an uploaded fixture — it's generated in code at process start-up from a fixed random seed (`data.py`, `seed=42`), so it's identical on every run. There is nothing to "load"; it's already present the moment the app starts.

To **reset** back to the original 60 students (discarding anything added via Upload or changed via Edit, since both only live in server memory): restart the Flask process. The next start regenerates the exact same 60 students, marks, and edge cases from the fixed seed.

## Run locally

### Requirements

- Python 3.10+
- Flask (see `requirements.txt` / install command below)
- No database required

### Setup

```bash
git clone https://github.com/AdnanJami/lsh26-t032-p08.git

cd lsh26-t032-p08

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt

python app.py
```

The app starts on `http://0.0.0.0:5000` in debug mode. No `.env` file or secrets are required to run it locally; `app.secret_key` in `app.py` is a hardcoded development placeholder used only to enable flash messages (see Known limitations).

## Problem-solving approach

We split the system into three layers that don't know about each other's internals. `data.py` builds the roster (6 compulsory subjects + 1 optional, two of them with a separate theory/practical mark) and a reproducible seeded fixture of 60 students, including 8 hand-built edge cases that hit every scenario the clarifications name explicitly. `grading.py` is a pure rules engine with no Flask dependency: it evaluates one subject or one student at a time and returns not just a number but the rule code (R-11, R-12, R-13, ...) and a plain-language note that produced it, so every figure on a marksheet is auditable back to the clarification that decided it. `app.py` wires Flask routes on top, holding graded results in memory and re-deriving them through the same `evaluate_student()` call whether the source is the start-up fixture, an uploaded CSV row, or an edited student. The most important decision was making the checklist (R4) and the per-student trace (R3) both read off the same `StudentResult` object the GPA itself is computed from, rather than maintaining a separate "why is this student flagged" calculation — that removes an entire class of bug where the checklist and the marksheet could disagree. Testing was done by manually tracing all 8 edge-case students against the clarifications by hand (compulsory sum, optional bonus, GPA, letter-grade boundary, checklist membership) before accepting the grading code, plus route-level checks (via curl / Flask's test client) confirming every page renders and that the upload/edit flows accept valid rows and reject invalid ones with the correct reason.

## Technology used

- **Frontend:** Server-rendered Jinja2 templates, hand-written CSS (no build step, no JS framework)
- **Backend:** Python 3, Flask
- **Database:** None — in-memory, seeded at start-up
- **Deployment:** `<FILL IN — hosting provider used for the live URL>`
- **Other material tools:** Google Fonts (Lora, IBM Plex Sans, IBM Plex Mono) loaded via CDN link in `base.html`

See [`LICENSES.md`](LICENSES.md) for third-party materials.

## Team contributions

| Registered member                        | GitHub username | Major contribution                | Evidence                |
| ----------------------------------------- | ---------------- | ---------------------------------- | ------------------------ |
| Abdullah Mohammad Muntasir Adnan Jami     | `AdnanJami`       | `Made the grading engine, Flask routes, templates, and synthetic student dataset, including the 4 required edge-case students. Designed the CSV upload format and validation, and wrote the README and evaluation-manifest.json. `  | `<FILL IN — file/commit>` |

Commit count alone does not represent contribution.

## AI usage

- **Claude (Anthropic)** — Designed and wrote the grading engine, Flask routes, templates, and synthetic student dataset, including the 8 required edge-case students, plus the CSV upload/validation module, per-student edit flow, and printable marksheet added beyond the four required items. Verified by running the grading engine against all 8 edge-case students and manually checking every compulsory-subject sum, optional bonus, GPA, letter-grade boundary, and checklist membership against R-10/R-11/R-12/R-13/R-29 line by line, plus exercising every route with valid and deliberately invalid input (curl / Flask test client) before accepting the code.

## Major design decisions

- **In-memory storage, no database:** Graded results and raw marks are kept in server-side dicts (`RESULTS`, `RAW_MARKS`) rather than a database, since the roster is small, judging is a single-session activity, and it keeps the whole system inspectable as a handful of plain Python modules with no migrations or ORM.
- **CSV format derived from the live roster, not hardcoded:** The upload page's documented column format and the parser's validation are both generated from `data.SUBJECTS`, so they can never drift out of sync if the subject list changes.
- **`AB` must be explicit:** An absence is only ever accepted as the literal text `AB` — an empty cell is always rejected, not silently treated as an absence — so a blank spreadsheet cell can't accidentally fail a student.
- **Every subject result carries its deciding rule:** `SubjectResult` stores the rule code and a plain-language note explaining exactly why a mark produced the grade it did, so the individual marksheet is an audit trail, not just a final number.
- **`Decimal` + `ROUND_HALF_UP` for GPA rounding:** Used instead of Python's built-in `round()`, so boundary GPAs (e.g. exactly 3.50) land on the correct letter grade deterministically rather than depending on binary float rounding.
- **The "uncancelled average" is computed for every student, not just failing ones:** The same code path produces both the published GPA and the R-13 audit figure — there is no separate "what if" calculation that could drift out of sync.
- **Practical-only absence treated as a full subject absence:** Since R-12 doesn't explicitly split theory/practical, an absence in only the practical half of a practical subject is treated as an absence for the whole subject. Flagged as an interpretive call in Known limitations, not a certainty.
- **All 60 students graded once at start-up:** This is a read-only judging/demo tool rather than a live data-entry system, so there's no need to recompute per request.

## Known limitations

- Absence in only the practical part of a practical subject (see Major design decisions) is an interpretive reading of R-12, not an explicitly confirmed one — worth a judge's ruling if it matters to scoring.
- No persistence: marks added via Upload or changed via Edit live only in server memory and are lost on restart (by design, so judges can always reset to the seeded fixture — see "Test or sample data" above).
- No authentication on `/upload` or `/student/<id>/edit` — anyone with the URL can add or change marks; acceptable for a single-judge/single-session demo but not production-ready.
- CSV parsing expects a well-formed header row with the exact expected column names (case/space/hyphen-insensitive); it doesn't attempt to auto-detect delimiters or alternate encodings beyond UTF-8/UTF-8-BOM.
- `app.secret_key` is a hardcoded development placeholder, used only to enable flash messages — not suitable for a real deployment.

## Repository records

- [`EVENT.md`](EVENT.md) — event start code and pre-event-material declaration
- [`evaluation-manifest.json`](evaluation-manifest.json) — structured judging evidence
- [`LICENSES.md`](LICENSES.md) — frameworks, libraries, templates and assets