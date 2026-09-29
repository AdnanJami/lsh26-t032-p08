"""
Run with:  python -m unittest discover -s tests -v

Covers the grading engine (against an independent re-implementation of the
published rules, on the demo data and on the organisers' public cases), the
JSON importer's accept/reject decisions, and every route through Flask's
test client.
"""

import importlib
import json
import re
import sys
import unittest
from decimal import ROUND_HALF_UP, Decimal
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
import data  # noqa: E402
from datasets import Dataset  # noqa: E402
from upload import validate_student  # noqa: E402

PUBLIC_FILE = ROOT / "P08_school_results_public.json"


# ---------- independent reference implementation of the published rules ----------

def ref_gp(mark):
    for lo, gp in ((80, 5.0), (70, 4.0), (60, 3.5), (50, 3.0), (40, 2.0), (33, 1.0)):
        if mark >= lo:
            return gp
    return 0.0


def reference(subjects, compulsory, student):
    practical = {s["code"]: s["practical"] for s in subjects}
    gps, fail, lists = {}, False, set()
    for code in compulsory + [student["optional"]]:
        value = student["marks"][code]
        is_opt = code == student["optional"]
        if value == "AB":
            gp, bad = 0.0, True
            lists.add("absent")
        elif practical[code]:
            t, p = value["theory"], value["practical"]
            if p < 8:
                lists.add("practical")
            if t < 25 or p < 8:
                gp, bad = 0.0, True
            else:
                gp, bad = ref_gp(t + p), False
        else:
            gp = ref_gp(value)
            bad = gp == 0
        gps[code] = gp
        if bad and not is_opt:
            fail = True
    opt_gp = gps[student["optional"]]
    if opt_gp <= 2.0:
        lists.add("optional")
    raw = min((sum(gps[c] for c in compulsory) + max(0.0, opt_gp - 2.0)) / 6, 5.0)
    raw = float(Decimal(repr(raw)).quantize(Decimal("0.01"), ROUND_HALF_UP))
    gpa = 0.0 if fail else raw
    if fail:
        letter = "F"
    else:
        letter = next(l for lo, l in ((5, "A+"), (4, "A"), (3.5, "A-"), (3, "B"), (2, "C"), (1, "D"), (0, "F")) if gpa >= lo)
    return gps, gpa, letter, lists, raw


def fresh_app():
    """Reload so every test starts from the seeded state."""
    mod = importlib.reload(app_module)
    mod.app.config["TESTING"] = True
    return mod


class ReferenceMixin:
    def assert_matches_reference(self, ds, record):
        r = ds.results[record["id"]]
        gps, gpa, letter, lists, raw = reference(ds.subjects, ds.compulsory, record)
        self.assertEqual({s.code: s.grade_point for s in r.subjects}, gps, record["id"])
        self.assertEqual(r.gpa, gpa, record["id"])
        self.assertEqual(r.letter, letter, record["id"])
        self.assertEqual(set(r.flags), lists, record["id"])
        self.assertEqual(r.raw_gpa, raw, record["id"])


# ---------- demo dataset ----------

class DemoDatasetTests(unittest.TestCase, ReferenceMixin):
    def setUp(self):
        self.students = data.build_demo_students()
        self.ds = Dataset("demo", "Demo", "", data.SUBJECTS, data.COMPULSORY, self.students)

    def test_shape_matches_the_problem(self):
        self.assertEqual(len(self.students), 60)
        classes = {s["class"] for s in self.students}
        self.assertEqual(classes, {"Class 9", "Class 10"})
        self.assertEqual(sum(s["class"] == "Class 9" for s in self.students), 30)
        self.assertEqual(len({s["id"] for s in self.students}), 60)
        self.assertEqual(data.COMPULSORY, ["BAN", "ENG", "MAT", "PHY", "CHE", "BIO"])
        self.assertEqual(data.OPTIONAL_CHOICES, ["HMT", "AGR", "REL"])
        self.assertEqual(data.PRACTICAL, {"PHY", "CHE", "BIO", "HMT", "AGR"})
        for s in self.students:
            self.assertIn(s["optional"], data.OPTIONAL_CHOICES)
            self.assertEqual(set(s["marks"]), set(data.COMPULSORY) | {s["optional"]})
            for code, value in s["marks"].items():
                if value == "AB":
                    continue
                if code in data.PRACTICAL:
                    self.assertEqual(set(value), {"theory", "practical"})
                    self.assertTrue(0 <= value["theory"] <= 75 and 0 <= value["practical"] <= 25)
                else:
                    self.assertTrue(0 <= value <= 100)
        # every optional subject is taken by someone
        self.assertEqual({s["optional"] for s in self.students}, set(data.OPTIONAL_CHOICES))

    def test_demo_data_is_reproducible(self):
        self.assertEqual(self.students, data.build_demo_students())

    def test_every_demo_student_matches_reference(self):
        for rec in self.students:
            self.assert_matches_reference(self.ds, rec)

    def test_edge_cases(self):
        r = self.ds.results
        # S001: compulsory fail under a strong average; the failing subject is identified
        self.assertEqual((r["S001"].gpa, r["S001"].letter), (0.0, "F"))
        self.assertEqual(r["S001"].raw_gpa, 4.33)
        self.assertEqual([s.code for s in r["S001"].failing_subjects], ["MAT"])
        # S002: practical fail with passing theory
        phy = next(s for s in r["S002"].subjects if s.code == "PHY")
        self.assertEqual((phy.theory_mark, phy.practical_mark, phy.status, phy.rule), (60, 5, "FAIL", "R-11"))
        self.assertIn("practical", r["S002"].flags)
        self.assertEqual(r["S002"].letter, "F")
        # S003: optional at 2.0 adds nothing
        self.assertEqual((r["S003"].optional_gp, r["S003"].optional_bonus, r["S003"].gpa), (2.0, 0.0, 4.0))
        self.assertIn("optional", r["S003"].flags)
        # S004: absent in a compulsory subject
        eng = next(s for s in r["S004"].subjects if s.code == "ENG")
        self.assertEqual((eng.status, eng.rule, eng.grade_point), ("AB", "R-12", 0.0))
        self.assertEqual(r["S004"].letter, "F")
        self.assertIn("absent", r["S004"].flags)
        # S005: absent optional only -> still passes, on optional and absent lists
        self.assertEqual((r["S005"].gpa, r["S005"].letter), (3.5, "A-"))
        self.assertEqual(set(r["S005"].flags), {"optional", "absent"})
        # S006: theory fail even though combined would pass
        che = next(s for s in r["S006"].subjects if s.code == "CHE")
        self.assertEqual((che.combined_mark, che.status, che.grade_point), (42, "FAIL", 0.0))
        self.assertNotIn("practical", r["S006"].flags)
        # S007: capped at 5.00
        self.assertEqual((r["S007"].gpa, r["S007"].letter), (5.0, "A+"))
        # S008: exactly on the A- boundary
        self.assertEqual((r["S008"].gpa, r["S008"].letter), (3.5, "A-"))
        # S009: optional failed on practical -> no bonus, result stands, on both lists
        self.assertEqual((r["S009"].gpa, r["S009"].letter), (4.5, "A"))
        self.assertEqual(set(r["S009"].flags), {"optional", "practical"})
        # S011: optional lifts A- to A
        self.assertEqual((r["S011"].optional_bonus, r["S011"].gpa, r["S011"].letter), (2.0, 4.08, "A"))

    def test_absent_is_not_zero(self):
        absent = next(s for s in self.ds.results["S004"].subjects if s.code == "ENG")
        zero = next(s for s in self.ds.results["S010"].subjects if s.code == "BAN")
        self.assertEqual(absent.status, "AB")
        self.assertEqual(zero.status, "FAIL")
        self.assertEqual(zero.single_mark, 0)
        self.assertIsNone(absent.single_mark)
        self.assertNotEqual(absent.rule, zero.rule)
        self.assertIn("absent", self.ds.results["S004"].flags)
        self.assertNotIn("absent", self.ds.results["S010"].flags)


@unittest.skipUnless(PUBLIC_FILE.exists(), "organisers' public case file not present")
class PublicCasesTests(unittest.TestCase, ReferenceMixin):
    def test_all_public_cases_load_and_match_reference(self):
        mod = fresh_app()
        raw = json.loads(PUBLIC_FILE.read_text(encoding="utf-8"))
        checked = 0
        for case in raw["cases"]:
            ds = mod.REGISTRY.get(case["case_id"])
            self.assertIsNotNone(ds, case["case_id"])
            self.assertEqual(len(ds), len(case["students"]))
            for rec in case["students"]:
                self.assert_matches_reference(ds, rec)
                checked += 1
        self.assertEqual(checked, sum(len(c["students"]) for c in raw["cases"]))


# ---------- importer ----------

class ValidateStudentTests(unittest.TestCase):
    def setUp(self):
        self.ds = Dataset("t", "t", "", data.SUBJECTS, data.COMPULSORY)

    def check(self, student, taken=()):
        return validate_student(student, self.ds.subject_by_code, self.ds.compulsory,
                                self.ds.optional_choices, set(taken))

    def good(self):
        return {"id": "X1", "name": "Good", "class": "Class 9", "optional": "REL",
                "marks": {"BAN": 50, "ENG": 50, "MAT": 50, "PHY": {"theory": 40, "practical": 10},
                          "CHE": {"theory": 40, "practical": 10}, "BIO": "AB", "REL": 70}}

    def test_accepts_valid_student_and_normalises_ab(self):
        s = self.good()
        s["marks"]["BAN"] = "ab"
        s["marks"]["ENG"] = 55.0
        rec, sid, reasons = self.check(s)
        self.assertEqual(reasons, [])
        self.assertEqual(rec["marks"]["BAN"], "AB")
        self.assertEqual(rec["marks"]["ENG"], 55)

    def test_rejections_have_specific_reasons(self):
        cases = [
            (lambda s: s["marks"].update(BAN=101), "BAN = 101 is out of range (0–100)"),
            (lambda s: s["marks"].update(PHY={"theory": 76, "practical": 10}), "PHY theory = 76 is out of range (0–75)"),
            (lambda s: s["marks"].update(PHY={"theory": 40, "practical": 26}), "PHY practical = 26 is out of range (0–25)"),
            (lambda s: s["marks"].update(PHY=60), "Physics (PHY) has a practical part"),
            (lambda s: s["marks"].update(PHY={"theory": 40}), "PHY is missing its practical mark"),
            (lambda s: s["marks"].update(BAN="fifty"), 'BAN is the text "fifty"'),
            (lambda s: s["marks"].update(BAN=""), 'BAN is the text ""'),
            (lambda s: s["marks"].update(BAN=50.5), "BAN = 50.5 is not a whole number"),
            (lambda s: s["marks"].update(BAN=True), "BAN must be a whole number"),
            (lambda s: s["marks"].pop("MAT"), 'no mark for Mathematics (MAT) — use "AB" if absent'),
            (lambda s: s["marks"].update(HMT={"theory": 40, "practical": 10}), "mark given for Higher Mathematics (HMT), which is not one of this student's subjects"),
            (lambda s: s["marks"].update(XYZ=5), "mark given for unknown subject code XYZ"),
            (lambda s: s.update(optional="ICT"), '"optional" is ICT; it must be one of HMT, AGR, REL'),
            (lambda s: s.update(optional="BAN"), '"optional" is BAN, which is already a compulsory subject'),
            (lambda s: s.pop("name"), 'missing "name"'),
            (lambda s: s.update({"class": " "}), 'missing "class"'),
            (lambda s: s.pop("id"), 'missing "id"'),
            (lambda s: s.update(id="a/b"), 'must not contain "/"'),
            (lambda s: s.pop("marks"), 'missing "marks" object'),
        ]
        for mutate, expected in cases:
            s = self.good()
            mutate(s)
            rec, _, reasons = self.check(s)
            self.assertIsNone(rec, expected)
            self.assertTrue(any(expected in r for r in reasons), f"{expected!r} not in {reasons}")

    def test_collects_every_reason(self):
        s = self.good()
        s["marks"].update(BAN=101, ENG=-1)
        s.pop("name")
        _, _, reasons = self.check(s)
        self.assertEqual(len(reasons), 3, reasons)

    def test_duplicate_id(self):
        _, _, reasons = self.check(self.good(), taken={"X1"})
        self.assertTrue(any("already used" in r for r in reasons))


# ---------- routes ----------

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.mod = fresh_app()
        self.client = self.mod.app.test_client()

    def get(self, url, status=200):
        res = self.client.get(url)
        self.assertEqual(res.status_code, status, url)
        return unescape(unescape(res.get_data(as_text=True)))

    def post(self, url, data, **kw):
        res = self.client.post(url, data=data, **kw)
        return res, unescape(unescape(res.get_data(as_text=True)))

    def visible_ids(self, html):
        rows = re.findall(r'<tr class="[^"]*"\s+data-id="([^"]+)"(.*?)>', html, re.S)
        return [sid for sid, attrs in rows if re.search(r"\bhidden\b", attrs) is None]

    def test_home_redirects_to_demo_ledger(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/d/demo/"))

    def test_ledger_renders_summary_and_all_rows(self):
        html = self.get("/d/demo/")
        self.assertIn("Showing 60 of 60 students", html)
        self.assertIn("Class 9", html)
        self.assertIn("Class 10", html)
        self.assertIn("pass rate", html)
        self.assertIn("failed the most students", html)
        self.assertIn('id="search-input"', html)
        self.assertEqual(len(self.visible_ids(html)), 60)
        self.assertIn('hidden>', html.split('id="detail-pane"')[1][:200])  # panel closed

    def test_search_filters_on_the_server(self):
        html = self.get("/d/demo/?q=rafiul+islam")
        self.assertEqual(self.visible_ids(html), ["S001"])
        # tokens match in any order, and against the roll too
        self.assertEqual(self.visible_ids(self.get("/d/demo/?q=islam+s001")), ["S001"])
        self.assertIn("Showing 1 of 60 students", html)
        html = self.get("/d/demo/?q=S00")
        self.assertEqual(len(self.visible_ids(html)), 9)
        html = self.get("/d/demo/?q=nobody-by-this-name")
        self.assertIn("Showing 0 of 60 students", html)
        self.assertRegex(html, r'class="list-empty" id="list-empty"\s*>')  # empty state visible

    def test_filters(self):
        ds = self.mod.REGISTRY.get("demo")
        fails = sorted(r.student_id for r in ds.results.values() if r.letter == "F")
        self.assertEqual(sorted(self.visible_ids(self.get("/d/demo/?result=fail"))), fails)
        absent = sorted(r.student_id for r in ds.results.values() if "absent" in r.flags)
        self.assertEqual(sorted(self.visible_ids(self.get("/d/demo/?result=absent"))), absent)
        class10 = self.visible_ids(self.get("/d/demo/?cls=Class+10"))
        self.assertEqual(len(class10), 30)
        self.assertTrue(all(ds.results[i].class_name == "Class 10" for i in class10))
        # unknown values fall back instead of erroring
        self.assertEqual(len(self.visible_ids(self.get("/d/demo/?cls=Nope&result=zzz&sort=zzz"))), 60)

    def test_sorting(self):
        ds = self.mod.REGISTRY.get("demo")
        ids = self.visible_ids(self.get("/d/demo/?sort=gpa_desc"))
        gpas = [ds.results[i].gpa for i in ids]
        self.assertEqual(gpas, sorted(gpas, reverse=True))
        ids = self.visible_ids(self.get("/d/demo/?sort=name"))
        names = [ds.results[i].name.lower() for i in ids]
        self.assertEqual(names, sorted(names))
        ids = self.visible_ids(self.get("/d/demo/?sort=avg_desc"))
        raws = [ds.results[i].raw_gpa for i in ids]
        self.assertEqual(raws, sorted(raws, reverse=True))
        # rank attributes for client-side sorting are present for every sort
        html = self.get("/d/demo/")
        for key in ("roll", "name", "gpa-desc", "gpa-asc", "avg-desc", "class"):
            self.assertEqual(html.count(f"data-rank-{key}="), 60, key)

    def test_student_opens_in_panel_beside_list(self):
        html = self.get("/d/demo/s/S001?q=raf")
        self.assertIn('class="workspace has-panel"', html)
        self.assertIn("Rafiul Islam", html)
        self.assertIn("Per-subject trace", html)
        self.assertIn("Failed compulsory", html)
        self.assertIn("<strong>Mathematics</strong>", html)
        self.assertIn("4.33", html)
        self.assertIn('aria-current=true', html)
        self.assertIn('href="/d/demo/?q=raf"', html)  # close keeps the search

    def test_partial_panel_for_javascript(self):
        html = self.get("/d/demo/s/S004?partial=1")
        self.assertNotIn("<html", html)
        self.assertIn('data-student="S004"', html)
        self.assertIn("R-12", html)
        self.assertIn("Absent. Recorded as AB", html)

    def test_trace_shows_real_numbers(self):
        html = self.get("/d/demo/s/S002")
        self.assertIn("T 60</span>", html)
        self.assertIn("+ P 5</span>", html)
        self.assertIn("Failed practical 5/25 (pass 8)", html)
        html = self.get("/d/demo/s/S007")
        self.assertIn("capped at 5.00", html)
        html = self.get("/d/demo/s/S003")
        self.assertIn("adds max(0, 2.0 - 2.0) = 0.0", html)

    def test_print_page(self):
        html = self.get("/d/demo/s/S001/print")
        self.assertIn("Individual marksheet", html)
        self.assertNotIn('class="spine', html)
        self.assertIn("data-print", html)

    def test_checklist(self):
        html = self.get("/d/demo/checklist")
        ds = self.mod.REGISTRY.get("demo")
        for kind, title in (("optional", "Optional-subject list"), ("practical", "Practical-fail list"), ("absent", "Absent list")):
            n = sum(1 for r in ds.results.values() if kind in r.flags)
            self.assertIn(f'{title} <span class="check-count">{n}</span>', html)
        self.assertIn("Physics practical 5/25", html)                                   # S002
        self.assertIn("Agriculture (optional) not sat", html)                           # S005
        self.assertIn("Religion (optional) grade point 2.0", html)                      # S003
        self.assertIn('href="/d/demo/s/S002"', html)

    def test_results_json(self):
        res = self.client.get("/d/demo/results.json")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(len(body["students"]), 60)
        s1 = next(s for s in body["students"] if s["id"] == "S001")
        self.assertEqual((s1["gpa"], s1["letter"], s1["uncancelled_gpa"], s1["failed_compulsory"]),
                         ("0.00", "F", "4.33", ["MAT"]))
        s4 = next(s for s in body["students"] if s["id"] == "S004")
        eng = next(x for x in s4["subjects"] if x["code"] == "ENG")
        self.assertEqual((eng["mark"], eng["status"]), ("AB", "AB"))

    def test_edit_regrades(self):
        html = self.get("/d/demo/s/S001/edit")
        self.assertIn('name="MAT" value="28"', html)
        self.assertIn('name="PHY_theory" value="62"', html)
        form = {"name": "Rafiul Islam", "class": "Class 9", "optional": "HMT",
                "BAN": "88", "ENG": "85", "MAT": "60", "PHY_theory": "62", "PHY_practical": "21",
                "CHE_theory": "60", "CHE_practical": "22", "BIO_theory": "58", "BIO_practical": "20",
                "HMT_theory": "55", "HMT_practical": "20"}
        res = self.client.post("/d/demo/s/S001/edit?q=raf", data=form)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/d/demo/s/S001?q=raf"))
        r = self.mod.REGISTRY.get("demo").results["S001"]
        # (5 + 5 + 3.5 + 5 + 5 + 4) + (4 - 2) = 29.5 / 6 = 4.92
        self.assertEqual((r.gpa, r.letter), (4.92, "A"))
        html = self.get("/d/demo/s/S001")
        self.assertIn("Saved Rafiul Islam", html)

    def test_edit_can_switch_optional_subject_and_mark_absent(self):
        form = {"name": "Rafiul Islam", "class": "Class 9", "optional": "REL",
                "BAN": "88", "ENG": "AB", "MAT": "70", "PHY_theory": "62", "PHY_practical": "21",
                "CHE_theory": "60", "CHE_practical": "22", "BIO_theory": "58", "BIO_practical": "20",
                "REL": "90", "HMT_theory": "999"}   # ignored: HMT is no longer the optional
        res = self.client.post("/d/demo/s/S001/edit", data=form)
        self.assertEqual(res.status_code, 302)
        rec = self.mod.REGISTRY.get("demo").records["S001"]
        self.assertEqual(rec["optional"], "REL")
        self.assertEqual(rec["marks"]["ENG"], "AB")
        self.assertNotIn("HMT", rec["marks"])

    def test_edit_rejects_bad_input_and_keeps_values(self):
        form = {"name": "", "class": "Class 9", "optional": "HMT",
                "BAN": "", "ENG": "85", "MAT": "150", "PHY_theory": "62", "PHY_practical": "x",
                "CHE_theory": "60", "CHE_practical": "22", "BIO_theory": "58", "BIO_practical": "20",
                "HMT_theory": "55", "HMT_practical": "20"}
        res = self.client.post("/d/demo/s/S001/edit", data=form)
        self.assertEqual(res.status_code, 400)
        html = unescape(res.get_data(as_text=True))
        self.assertIn("MAT = 150 is out of range (0–100)", html)
        self.assertIn('missing "name"', html)
        self.assertIn("BAN is the text", html)
        self.assertIn("PHY practical is the text", html)
        self.assertIn('name="MAT" value="150"', html)
        self.assertEqual(self.mod.REGISTRY.get("demo").results["S001"].raw_gpa, 4.33)  # unchanged

    def test_upload_students_into_existing_dataset(self):
        payload = {"students": self.mod.EXAMPLE_STUDENTS}
        res = self.client.post("/upload", data={"pasted_json": json.dumps(payload), "target": "demo"})
        self.assertEqual(res.status_code, 200)
        html = unescape(res.get_data(as_text=True))
        self.assertIn("<strong>2</strong> students accepted", html)
        self.assertIn("<strong>2</strong> rejected", html)
        self.assertIn("BAN = 104 is out of range (0–100)", html)
        self.assertIn("PHY theory = 80 is out of range (0–75)", html)
        self.assertIn("already used in this dataset", html)
        self.assertIn('"optional" is ICT', html)
        ds = self.mod.REGISTRY.get("demo")
        self.assertEqual(len(ds), 62)
        self.assertEqual(ds.results["N002"].letter, "F")
        self.assertIn("Showing 62 of 62", self.get("/d/demo/"))

    def test_upload_single_case_creates_dataset(self):
        case = {"case_id": "MY-CASE", "subjects": data.SUBJECTS, "compulsory": data.COMPULSORY,
                "students": data.build_demo_students()[:3]}
        res = self.client.post("/upload", data={"pasted_json": json.dumps(case)})
        self.assertEqual(res.status_code, 200)
        self.assertIn("open new dataset", unescape(res.get_data(as_text=True)))
        ds = self.mod.REGISTRY.get("MY-CASE")
        self.assertEqual(len(ds), 3)
        self.get("/d/MY-CASE/")
        self.get("/d/MY-CASE/checklist")
        # uploading the same case again gets a distinct dataset id
        self.client.post("/upload", data={"pasted_json": json.dumps(case)})
        self.assertIsNotNone(self.mod.REGISTRY.get("MY-CASE-2"))

    def test_upload_file(self):
        from io import BytesIO
        case = {"cases": [{"case_id": "FILE-1", "subjects": data.SUBJECTS, "compulsory": data.COMPULSORY,
                           "students": data.build_demo_students()[:5]}]}
        res = self.client.post("/upload", data={"json_file": (BytesIO(json.dumps(case).encode()), "marks.json")},
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(self.mod.REGISTRY.get("FILE-1")), 5)
        self.assertEqual(self.mod.REGISTRY.get("FILE-1").source, "Uploaded file marks.json")

    @unittest.skipUnless(PUBLIC_FILE.exists(), "organisers' public case file not present")
    def test_upload_public_file(self):
        from io import BytesIO
        before = len(self.mod.REGISTRY)
        res = self.client.post("/upload", data={"json_file": (BytesIO(PUBLIC_FILE.read_bytes()), PUBLIC_FILE.name)},
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<strong>0</strong> rejected across 25 cases", unescape(res.get_data(as_text=True)))
        self.assertEqual(len(self.mod.REGISTRY), before + 25)

    def test_upload_errors(self):
        cases = [
            ({"pasted_json": ""}, "Nothing to import"),
            ({"pasted_json": "{not json"}, "Not valid JSON"),
            ({"pasted_json": "42"}, "Expected a JSON object or array"),
            ({"pasted_json": '{"foo": 1}'}, "Unrecognised JSON"),
            ({"pasted_json": '{"cases": []}'}, "non-empty array"),
            ({"pasted_json": '{"students": [1]}', "target": "nope"}, "Choose which dataset"),
        ]
        for form, expected in cases:
            res = self.client.post("/upload", data=form)
            self.assertEqual(res.status_code, 400, form)
            self.assertIn(expected, res.get_data(as_text=True), form)

    def test_upload_rejects_malformed_case_structure(self):
        bad = {"case_id": "BAD", "subjects": data.SUBJECTS, "compulsory": ["BAN", "ENG", "ZZZ"], "students": []}
        res = self.client.post("/upload", data={"pasted_json": json.dumps(bad)})
        html = unescape(res.get_data(as_text=True))
        self.assertEqual(res.status_code, 400)
        self.assertIn("Case rejected", html)
        self.assertIn("must list 6 different subject codes (got 3)", html)
        self.assertIn("ZZZ are not in", html)
        self.assertIsNone(self.mod.REGISTRY.get("BAD"))

    def test_dataset_switcher_and_legacy_urls(self):
        res = self.client.get("/go?ds=demo&page=checklist")
        self.assertTrue(res.headers["Location"].endswith("/d/demo/checklist"))
        self.assertTrue(self.client.get("/student/S001").headers["Location"].endswith("/d/demo/s/S001"))
        self.assertTrue(self.client.get("/checklist").headers["Location"].endswith("/d/demo/checklist"))

    def test_not_found_pages(self):
        self.assertIn("No student with roll", self.get("/d/demo/s/NOPE", 404))
        self.assertIn("There is no dataset", self.get("/d/nope/", 404))
        self.get("/go?ds=nope", 404)
        self.get("/definitely/not/here", 404)

    def test_upload_page_renders(self):
        html = self.get("/upload")
        self.assertIn("Fill in an example", html)
        self.assertIn('id="example-json"', html)
        json.loads(re.search(r'<script type="application/json" id="example-json">(.*?)</script>', html, re.S).group(1))


if __name__ == "__main__":
    unittest.main()
