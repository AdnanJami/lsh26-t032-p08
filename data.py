"""
Builds the built-in demo dataset: 60 students across two classes, in the
same shape as the organisers' public case file (P08_school_results_public.json),
so the demo, an uploaded case and the published fixture all go through one
code path.

Subject layout (matches the organisers' cases):
  compulsory: Bangla, English, Mathematics, Physics*, Chemistry*, Biology*
  optional:   one of Higher Mathematics*, Agriculture*, Religion, chosen per student
  (* has a practical part: theory out of 75 + practical out of 25)

A student record is:
  {"id": "S001", "name": "...", "class": "Class 9", "optional": "HMT",
   "marks": {"BAN": 55, "PHY": {"theory": 60, "practical": 20}, "BIO": "AB", ...}}

Hand-built edge-case students (the problem asks for at least eight):
  S001  one failed compulsory subject, otherwise a strong average (R-13)
  S002  practical fail with a passing theory mark (R-11)
  S003  optional subject below the point where it helps (GP 2.0 -> bonus 0)
  S004  absent in one compulsory subject (R-12)
  S005  absent in the optional subject only -> still passes, on the checking list
  S006  theory fail with a strong practical (combined 42 would be a 2.0) (R-11)
  S007  perfect paper, GPA capped at 5.00
  S008  sits exactly on a letter boundary: GPA 3.50 = A-
  S009  optional subject failed on its practical -> does not fail the result
  S010  scored 0 in a subject (a fail) -- compare with S004, absent (AB)
  S011  optional subject lifts the GPA from A- to A

The rest are generated with a fixed random seed, so the data is identical on
every start-up.
"""

import random

SUBJECTS = [
    {"code": "BAN", "name": "Bangla", "practical": False},
    {"code": "ENG", "name": "English", "practical": False},
    {"code": "MAT", "name": "Mathematics", "practical": False},
    {"code": "PHY", "name": "Physics", "practical": True},
    {"code": "CHE", "name": "Chemistry", "practical": True},
    {"code": "BIO", "name": "Biology", "practical": True},
    {"code": "HMT", "name": "Higher Mathematics", "practical": True},
    {"code": "AGR", "name": "Agriculture", "practical": True},
    {"code": "REL", "name": "Religion", "practical": False},
]
COMPULSORY = ["BAN", "ENG", "MAT", "PHY", "CHE", "BIO"]
OPTIONAL_CHOICES = [s["code"] for s in SUBJECTS if s["code"] not in COMPULSORY]
PRACTICAL = {s["code"] for s in SUBJECTS if s["practical"]}

CLASSES = ["Class 9", "Class 10"]

FIRST_NAMES = [
    "Rafiul", "Mim", "Tanvir", "Sadia", "Arif", "Nusrat", "Farhan", "Jannatul",
    "Shakil", "Rima", "Imran", "Lamia", "Rakib", "Priya", "Hasib", "Meherun",
    "Zahid", "Tania", "Sabbir", "Onnesha", "Nayeem", "Rukhsana", "Kamrul", "Shirin",
    "Rasel", "Farzana", "Sohel", "Ayesha", "Mahin", "Sultana", "Emon", "Rehana",
    "Bappi", "Nasrin", "Ovi", "Kakoli", "Tarek", "Shathi", "Foysal", "Momtaz",
    "Anik", "Rupali", "Naim", "Halima", "Sajid", "Jesmin", "Milon", "Rozina",
    "Palash", "Afsana", "Rony", "Chandni", "Riaz", "Dolly", "Suman", "Ivy",
]
LAST_NAMES = [
    "Islam", "Rahman", "Akter", "Hossain", "Chowdhury", "Ahmed", "Khatun",
    "Uddin", "Begum", "Karim", "Sultana", "Alam",
]


def _p(theory, practical):
    return {"theory": theory, "practical": practical}


def _student(sid, name, class_name, optional, **marks):
    return {"id": sid, "name": name, "class": class_name, "optional": optional, "marks": marks}


def _edge_case_students():
    return [
        # One failed compulsory subject (MAT 28) under an otherwise ~4.6 average.
        _student("S001", "Rafiul Islam", "Class 9", "HMT",
                 BAN=88, ENG=85, MAT=28, PHY=_p(62, 21), CHE=_p(60, 22),
                 BIO=_p(58, 20), HMT=_p(55, 20)),
        # Practical fail (5/25) with a passing theory mark (60/75).
        _student("S002", "Mim Akter", "Class 9", "AGR",
                 BAN=70, ENG=65, MAT=72, PHY=_p(60, 5), CHE=_p(50, 18),
                 BIO=_p(52, 16), AGR=_p(50, 18)),
        # Optional at GP 2.0 -- exactly the point where it stops helping.
        _student("S003", "Tanvir Hasan", "Class 9", "REL",
                 BAN=75, ENG=72, MAT=80, PHY=_p(50, 15), CHE=_p(48, 16),
                 BIO=_p(52, 18), REL=45),
        # Absent in a compulsory subject.
        _student("S004", "Sadia Rahman", "Class 9", "HMT",
                 BAN=82, ENG="AB", MAT=77, PHY=_p(58, 14), CHE=_p(55, 15),
                 BIO=_p(60, 18), HMT=_p(62, 20)),
        # Absent in the optional subject only: passes, lands on the checking list.
        _student("S005", "Arif Chowdhury", "Class 9", "AGR",
                 BAN=68, ENG=71, MAT=64, PHY=_p(50, 12), CHE=_p(45, 14),
                 BIO=_p(48, 15), AGR="AB"),
        # Theory 20/75 fails even though practical 22/25 is strong (combined 42).
        _student("S006", "Nusrat Jahan", "Class 10", "REL",
                 BAN=74, ENG=69, MAT=71, PHY=_p(55, 18), CHE=_p(20, 22),
                 BIO=_p(50, 16), REL=66),
        # Perfect paper: (30 + 3) / 6 = 5.5, capped at 5.00.
        _student("S007", "Farhan Kabir", "Class 10", "HMT",
                 BAN=95, ENG=92, MAT=98, PHY=_p(70, 24), CHE=_p(68, 23),
                 BIO=_p(66, 24), HMT=_p(70, 24)),
        # Every compulsory at 3.5, optional at 2.0: 21 / 6 = 3.50 exactly -> A-.
        _student("S008", "Jannatul Ferdous", "Class 10", "REL",
                 BAN=65, ENG=60, MAT=69, PHY=_p(50, 15), CHE=_p(48, 14),
                 BIO=_p(46, 17), REL=42),
        # Optional failed on its practical (6/25): no bonus, but the result stands.
        _student("S009", "Kamrul Uddin", "Class 10", "AGR",
                 BAN=81, ENG=76, MAT=84, PHY=_p(58, 20), CHE=_p(56, 19),
                 BIO=_p(61, 21), AGR=_p(55, 6)),
        # Sat the paper and scored 0 -- a FAIL, shown differently from S004's AB.
        _student("S010", "Lamia Hossain", "Class 10", "REL",
                 BAN=0, ENG=66, MAT=70, PHY=_p(52, 17), CHE=_p(50, 16),
                 BIO=_p(55, 18), REL=58),
        # Compulsory sum 22.5 (3.75, A-) + HMT bonus 2.0 -> 24.5 / 6 = 4.08, A.
        _student("S011", "Shirin Akter", "Class 10", "HMT",
                 BAN=72, ENG=68, MAT=75, PHY=_p(47, 16), CHE=_p(50, 14),
                 BIO=_p(52, 18), HMT=_p(55, 18)),
    ]


def _random_mark(rng):
    band = rng.choices(["fail", "low", "mid", "high"], weights=[6, 15, 49, 30], k=1)[0]
    if band == "fail":
        return rng.randint(8, 32)
    if band == "low":
        return rng.randint(33, 49)
    if band == "mid":
        return rng.randint(50, 79)
    return rng.randint(80, 100)


def _random_practical(rng):
    theory = max(0, min(75, _random_mark(rng) * 75 // 100 + rng.randint(-3, 3)))
    practical = rng.choices([rng.randint(3, 7), rng.randint(8, 25)], weights=[8, 92], k=1)[0]
    return _p(theory, practical)


def _random_student(rng, sid, name, class_name):
    optional = rng.choice(OPTIONAL_CHOICES)
    marks = {}
    for code in COMPULSORY + [optional]:
        if rng.random() < 0.02:
            marks[code] = "AB"
        elif code in PRACTICAL:
            marks[code] = _random_practical(rng)
        else:
            marks[code] = _random_mark(rng)
    return {"id": sid, "name": name, "class": class_name, "optional": optional, "marks": marks}


def build_demo_students(total_students=60, seed=42):
    """Returns the demo roster as a list of student records."""
    rng = random.Random(seed)
    students = _edge_case_students()
    used_names = {s["name"] for s in students}

    per_class = {c: sum(s["class"] == c for s in students) for c in CLASSES}
    for i in range(len(students), total_students):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        class_name = min(CLASSES, key=lambda c: per_class[c])  # keep the classes even
        per_class[class_name] += 1
        students.append(_random_student(rng, f"S{i + 1:03d}", name, class_name))

    return students
