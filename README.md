# Result Register & GPA Engine

Solution for **LofiStack Hackathon 2026 — P08**

## Project information

- **Team:** `Larpcoder`
- **Team ID:** `LSH26-T032`
- **Problem:** `P08 — School Result Processing and GPA Engine`
- **Live application:** <https://lsh26-t032-p08.onrender.com/>

## Solution summary

A Flask app that grades students under the school's published GPA rules (R-10 to R-13, R-29) and shows its working, not just the result. Every subject on a marksheet shows the exact mark, the grade point it produced and the rule that decided it. A compulsory fail that cancels a strong average is named, with the uncancelled average kept alongside it.

It uses the organisers' subject layout and data format. There are six compulsory subjects: Bangla, English, Mathematics, and Physics, Chemistry and Biology (each with a theory and a practical part). Each student also takes one optional subject: Higher Mathematics or Agriculture (both with practicals), or Religion. Marks are loaded as JSON in the organisers' case format. Every case in the published file `P08_school_results_public.json` loads as its own dataset, and each student is checked individually with specific rejection reasons.

The ledger is a search, filter and sort list of students. Clicking a student opens their marksheet in a panel on the right, and the list moves left so you can keep working through it (arrow keys step through students). Each class gets a summary: pass rate, grade distribution and the subject failing the most students. The office checklist lists every student affected by the optional-subject rule, a practical fail or an absence, with the reason for each.

## Requirements

| Requirement | Status | Where to verify |
|---|---|---|
| R1 — 60+ students, 2 classes, 6 compulsory + 1 optional, separate theory/practical marks, 8+ hard edge cases | Complete | `data.py` → `build_demo_students()`, `_edge_case_students()` (11 edge cases, S001–S011) |
| R2 — Grade point per subject, final GPA, letter grade | Complete | `grading.py` → `evaluate_subject()`, `evaluate_student()`; ledger GPA/grade columns |
| R3 — Per-student trace with the real numbers and the deciding rule; failing subject shown for high-average fails | Complete | `templates/_marksheet.html` (open any student, e.g. S001) |
| R4 — Office checking list: optional, practical-fail and absent lists with reasons | Complete | `/d/<dataset>/checklist`, `templates/checklists.html` |
| Bonus — paste or upload marks and report rejected rows and why | Complete | `/upload`, `upload.py` |
| Bonus — class summary: pass rate, grade distribution, most-failed subject | Complete | Top of every ledger |
| Bonus — printable individual marksheet | Complete | "Printable marksheet" in the student panel |

## How to test the application

1. Open the live app. You land on the **Ledger** for the built-in demo dataset: class summaries on top, the student list below.
2. Type in the **search box** (press <kbd>/</kbd> to jump to it), or change **Class**, **Show** (pass, fail, or one of the checking lists) and **Sort by**. The list updates as you type and the URL keeps the state.
3. **Click a student.** Their marksheet opens on the right and the list moves left. Use <kbd>↑</kbd>/<kbd>↓</kbd> (or the arrow buttons) to step through the filtered list, and <kbd>Esc</kbd> to close. On a phone the marksheet takes the full screen with a "← List" button.
4. Students worth opening: **S001** (strong average, failed Mathematics), **S002** (practical fail with passing theory), **S003** (optional at 2.0, adds nothing), **S004** (absent, AB) next to **S010** (sat the paper, scored 0), **S005** (absent in the optional only, still passes), **S007** (GPA capped at 5.00), **S008** (exactly 3.50 → A-), **S011** (optional lifts A- to A).
5. Open **Office checklist** for the three R-29 lists.
6. Use the **Dataset** menu to switch to any of the organisers' published cases (PUB-01 … PUB-25). They are loaded at start-up.
7. On **Upload marks**, click **Fill in an example**, then **Validate and add**. Two students are accepted and two are rejected, each with its reasons. You can also upload the whole published JSON file.
8. From a marksheet, **Edit marks** changes marks or the optional subject and re-grades at once.
9. **Export results (JSON)** on the ledger gives every graded result in the dataset, for checking against another tool.

### Test or sample data

- **Demo dataset:** 60 students (30 in Class 9, 30 in Class 10), generated in code from a fixed seed (`data.py`, `seed=42`), so it's identical on every run. S001–S011 are hand-built edge cases.
- **Organisers' published cases:** if `P08_school_results_public.json` is next to `app.py`, all 25 cases (1,765 students) load at start-up as separate datasets.
- **Reset:** uploads and edits live only in server memory. Restart the process to return to the seeded state.

## Run locally

Requires Python 3.10+; no database.

```bash
git clone https://github.com/AdnanJami/lsh26-t032-p08.git
cd lsh26-t032-p08
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app starts on `http://127.0.0.1:5000` (set `PORT` to change it). `SECRET_KEY` can be set in the environment; otherwise a development placeholder is used, only for flash messages.

### Tests

```bash
python -m unittest discover -s tests -v
```

The suite checks:
- every student in the demo and in all 25 published cases against a separate implementation of the rules, written from the problem statement;
- each edge case's expected GPA, letter and checklist membership;
- every rejection reason the importer can give;
- every route: search, filters, sorts, panel, partial panel, edit, upload, checklist, export and 404s.

## Problem-solving approach

The system is in layers that don't know about each other's internals:

- `grading.py` is a pure rules engine with no Flask dependency. It grades one subject or one student and returns, alongside each number, the rule code and a plain-language note built from that student's own marks.
- `datasets.py` holds datasets in memory. A dataset is one case in the organisers' format (its own subject list, compulsory codes and students). This module also does the list view's search, filtering and sorting.
- `upload.py` validates JSON in the organisers' format and collects every reason a record is rejected.
- `app.py` is the Flask layer.

The same validator checks uploaded files and the edit form, and one engine call produces the GPA, the trace and the checklist membership. The marksheet and the checklist therefore can't disagree.

The ledger is built as progressive enhancement. The server can filter, sort and render the page with a student's panel already open, so every state has a shareable URL and works without JavaScript. `static/app.js` makes filtering instant and loads the panel beside the list without a page reload. It uses the history API, so Back and Forward work.

## Technology used

- **Frontend:** Server-rendered Jinja2 templates, hand-written CSS, one small vanilla JavaScript file (no framework, no build step)
- **Backend:** Python 3, Flask
- **Database:** None — in-memory
- **Deployment:** Render (free web service)
- **Other material:** Google Fonts (Lora, IBM Plex Sans, IBM Plex Mono) via CDN

See [`LICENSES.md`](LICENSES.md) for third-party materials.

## What is mocked

- **Student data:** the demo roster is synthetic (seeded random marks and made-up names). The published cases are the organisers' synthetic data.
- **Storage:** everything is in memory. There is no database, so edits and uploads disappear on restart.
- **Users:** there are no accounts or sign-in. Anyone with the URL can upload or edit.

## What's next

- Persist datasets and edits (SQLite) with an audit log of who changed which mark.
- Teacher sign-in, and a "lock results" step once the office checklist is signed off.
- CSV or Excel import alongside JSON, since most schools keep marks in spreadsheets.
- A batch "print all marksheets for a class" view.

## Known limitations

- Absence in only one part of a practical subject (for example `{"theory": 60, "practical": "AB"}`) is treated as absence for the whole subject. R-12 doesn't split theory and practical, so this is an interpretation. The published cases only use `"AB"` for whole subjects.
- No persistence and no authentication (see "What is mocked").
- Upload size is capped at 8 MB.

## Team contributions

| Registered member | GitHub username | Major contribution | Evidence |
|---|---|---|---|
| Abdullah Mohammad Muntasir Adnan Jami | `AdnanJami` | Grading engine, Flask routes, templates, the synthetic dataset with its 11 edge-case students, the upload format and validation, README and `evaluation-manifest.json`. | `e31a168`, `bec9701` |

Commit count alone does not represent contribution.

## AI usage

- **Claude (Anthropic)** — Helped write the grading engine, routes, templates, dataset, the JSON importer, and the ledger's search, sort and side-panel UI. Verified in three ways:
  - by comparing all 1,765 published-case students, plus the demo, against a separate implementation of R-10 to R-13 and R-29 (`tests/test_app.py`);
  - by hand-checking each edge case's sums, bonus, GPA and letter against the rules;
  - by driving the running app in a browser (search, sort, the panel, keyboard navigation, the mobile layout).

## Major design decisions

- **The organisers' data model is the only model.** The demo, an uploaded case and the published file all go through the same `Dataset` → `evaluate_student` path, so there's no separate data model for the demo.
- **One dataset per case.** Student ids repeat between published cases (every case has an `S001`), so each case keeps its own ledger and checklist rather than being merged.
- **Every rejection reason, not just the first.** A record with three problems lists all three, and one bad record never blocks the rest.
- **`AB` must be explicit.** A blank edit box or an empty string is rejected rather than treated as absent or as 0. Absent and zero produce different results (R-12 vs a fail), and the trace labels them differently.
- **`Decimal` + `ROUND_HALF_UP`** is used for the 2-decimal GPA, so boundary values land on the right letter grade.
- **The uncancelled average is computed for every student.** The same code path gives both the published GPA and the R-13 audit figure.
- **Progressive enhancement over a single-page app.** Every view is a real URL rendered by the server. JavaScript only makes it faster.

## Repository records

- [`EVENT.md`](EVENT.md) — event start code and pre-event-material declaration
- [`evaluation-manifest.json`](evaluation-manifest.json) — structured judging evidence
- [`LICENSES.md`](LICENSES.md) — frameworks, libraries, fonts and data
