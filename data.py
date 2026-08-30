"""
Builds the roster (subjects) and the student marks for two classes.

Eight students are hand-built to hit every edge case the problem statement
calls out by name:
  1. one failed compulsory subject, otherwise a strong average (R-13 trace)
  2. a practical fail with a passing theory mark
  3. an optional subject that scores below the point where it helps (GP <= 2)
  4. a student absent in one (non-practical) compulsory subject
  5. a student absent only in the optional subject (does not fail overall)
  6. a student absent in only the practical part of a practical subject
  7. a perfect A+ student, to test the top boundary
  8. a student sitting exactly on a letter-grade boundary (GPA 3.50)

The remaining ~52 students are generated with a fixed random seed so the
data is reproducible across runs.
"""

import random

SUBJECTS = [
    {"code": "BAN", "name": "Bangla", "optional": False, "practical": False},
    {"code": "ENG", "name": "English", "optional": False, "practical": False},
    {"code": "MATH", "name": "Mathematics", "optional": False, "practical": False},
    {"code": "SCI", "name": "Science", "optional": False, "practical": True},
    {"code": "REL", "name": "Religion & Moral Education", "optional": False, "practical": False},
    {"code": "ICT", "name": "ICT", "optional": False, "practical": True},
    {"code": "HMATH", "name": "Higher Mathematics", "optional": True, "practical": False},
]

COMPULSORY_CODES = [s["code"] for s in SUBJECTS if not s["optional"]]
OPTIONAL_CODE = next(s["code"] for s in SUBJECTS if s["optional"])
PRACTICAL_CODES = [s["code"] for s in SUBJECTS if s["practical"]]

CLASSES = ["Class 9A", "Class 9B"]

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


def _mk_ordinary(mark):
    return {"mark": mark}


def _mk_practical(theory, practical):
    return {"theory": theory, "practical": practical}


def _full_marks(defaults):
    """defaults: dict code -> entry, for every subject in SUBJECTS."""
    return {s["code"]: defaults[s["code"]] for s in SUBJECTS}


def _edge_case_students():
    students = []

    students.append({
        "id": "9A-01", "name": "Rafiul Islam", "class_name": "Class 9A",
        "marks": _full_marks({
            "BAN": _mk_ordinary(88), "ENG": _mk_ordinary(85), "MATH": _mk_ordinary(90),
            "SCI": _mk_practical(60, 20), "REL": _mk_ordinary(30),
            "ICT": _mk_practical(55, 15), "HMATH": _mk_ordinary(78),
        }),
    })

    students.append({
        "id": "9A-02", "name": "Mim Akter", "class_name": "Class 9A",
        "marks": _full_marks({
            "BAN": _mk_ordinary(70), "ENG": _mk_ordinary(65), "MATH": _mk_ordinary(72),
            "SCI": _mk_practical(60, 5),
            "REL": _mk_ordinary(68), "ICT": _mk_practical(50, 18), "HMATH": _mk_ordinary(60),
        }),
    })

    students.append({
        "id": "9A-03", "name": "Tanvir Hasan", "class_name": "Class 9A",
        "marks": _full_marks({
            "BAN": _mk_ordinary(75), "ENG": _mk_ordinary(72), "MATH": _mk_ordinary(80),
            "SCI": _mk_practical(55, 15), "REL": _mk_ordinary(66),
            "ICT": _mk_practical(50, 12), "HMATH": _mk_ordinary(45),
        }),
    })

    students.append({
        "id": "9A-04", "name": "Sadia Rahman", "class_name": "Class 9A",
        "marks": _full_marks({
            "BAN": _mk_ordinary(82), "ENG": _mk_ordinary(None),
            "MATH": _mk_ordinary(77), "SCI": _mk_practical(58, 14),
            "REL": _mk_ordinary(70), "ICT": _mk_practical(50, 10), "HMATH": _mk_ordinary(80),
        }),
    })

    students.append({
        "id": "9A-05", "name": "Arif Chowdhury", "class_name": "Class 9A",
        "marks": _full_marks({
            "BAN": _mk_ordinary(68), "ENG": _mk_ordinary(71), "MATH": _mk_ordinary(64),
            "SCI": _mk_practical(50, 12), "REL": _mk_ordinary(60),
            "ICT": _mk_practical(45, 10), "HMATH": _mk_ordinary(None),
        }),
    })

    students.append({
        "id": "9B-01", "name": "Nusrat Jahan", "class_name": "Class 9B",
        "marks": _full_marks({
            "BAN": _mk_ordinary(74), "ENG": _mk_ordinary(69), "MATH": _mk_ordinary(71),
            "SCI": _mk_practical(52, None),
            "REL": _mk_ordinary(65), "ICT": _mk_practical(48, 14), "HMATH": _mk_ordinary(70),
        }),
    })

    students.append({
        "id": "9B-02", "name": "Farhan Kabir", "class_name": "Class 9B",
        "marks": _full_marks({
            "BAN": _mk_ordinary(95), "ENG": _mk_ordinary(92), "MATH": _mk_ordinary(98),
            "SCI": _mk_practical(70, 24), "REL": _mk_ordinary(90),
            "ICT": _mk_practical(70, 23), "HMATH": _mk_ordinary(85),
        }),
    })

    students.append({
        "id": "9B-03", "name": "Jannatul Ferdous", "class_name": "Class 9B",
        "marks": _full_marks({
            "BAN": _mk_ordinary(65), "ENG": _mk_ordinary(60), "MATH": _mk_ordinary(69),
            "SCI": _mk_practical(50, 15), "REL": _mk_ordinary(62),
            "ICT": _mk_practical(45, 15), "HMATH": _mk_ordinary(40),
        }),
    })

    return students


def _random_ordinary(rng):
    band = rng.choices(
        ["fail", "low", "mid", "high"],
        weights=[8, 15, 47, 30],
        k=1,
    )[0]
    if band == "fail":
        return rng.randint(10, 32)
    if band == "low":
        return rng.randint(33, 49)
    if band == "mid":
        return rng.randint(50, 79)
    return rng.randint(80, 100)


THEORY_MAX_LOCAL = 75


def _random_practical(rng):
    theory = min(THEORY_MAX_LOCAL, max(0, _random_ordinary(rng) * 75 // 100 + rng.randint(-3, 3)))
    theory = max(0, min(75, theory))
    practical = rng.randint(4, 25)
    return theory, practical


def _generate_random_students(rng, count, start_index, class_name, class_prefix):
    students = []
    used_names = set()
    for i in range(count):
        while True:
            fname = rng.choice(FIRST_NAMES)
            lname = rng.choice(LAST_NAMES)
            full = f"{fname} {lname}"
            if full not in used_names:
                used_names.add(full)
                break
        marks = {}
        for s in SUBJECTS:
            absent = rng.random() < 0.04
            if s["practical"]:
                if absent:
                    which = rng.choice(["theory", "practical", "both"])
                    t = None if which in ("theory", "both") else _random_practical(rng)[0]
                    p = None if which in ("practical", "both") else _random_practical(rng)[1]
                    marks[s["code"]] = _mk_practical(t, p)
                else:
                    t, p = _random_practical(rng)
                    marks[s["code"]] = _mk_practical(t, p)
            else:
                marks[s["code"]] = _mk_ordinary(None if absent else _random_ordinary(rng))
        sid = f"{class_prefix}-{start_index + i:02d}"
        students.append({"id": sid, "name": full, "class_name": class_name, "marks": marks})
    return students


def build_roster_and_students(total_students=60, seed=42):
    rng = random.Random(seed)
    students = _edge_case_students()

    existing_9a = sum(1 for s in students if s["class_name"] == "Class 9A")
    existing_9b = sum(1 for s in students if s["class_name"] == "Class 9B")

    remaining = max(0, total_students - len(students))
    half = remaining // 2
    count_9a = half
    count_9b = remaining - half

    students += _generate_random_students(rng, count_9a, existing_9a + 1, "Class 9A", "9A")
    students += _generate_random_students(rng, count_9b, existing_9b + 1, "Class 9B", "9B")

    return SUBJECTS, students