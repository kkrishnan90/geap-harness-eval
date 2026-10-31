"""Deterministic synthetic patient population (no real data).

generate(n_people, seed) creates people and 0-3 additional registrations per
person with realistic data-entry noise: typos, nicknames, swapped day/month,
missing phone, changed postcode.
"""

import random
from datetime import date, timedelta

from .model import PatientRecord

FAMILY = ["SMITH", "JONES", "TAYLOR", "BROWN", "WILLIAMS", "WILSON", "JOHNSON", "DAVIES",
          "PATEL", "WRIGHT", "ROBINSON", "THOMPSON", "EVANS", "WALKER", "WHITE", "ROBERTS",
          "GREEN", "HALL", "THOMAS", "CLARKE", "JACKSON", "WOOD", "HARRIS", "EDWARDS",
          "TURNER", "MARTIN", "COOPER", "HILL", "WARD", "HUGHES", "MOORE", "CLARK", "KING",
          "HARRISON", "LEWIS", "BAKER", "LEE", "ALLEN", "MORRIS", "KHAN", "SCOTT", "WATSON",
          "DAVIS", "PARKER", "JAMES", "BENNETT", "YOUNG", "PHILLIPS", "RICHARDSON", "MITCHELL"]
GIVEN = ["OLIVIA", "AMELIA", "ISLA", "AVA", "MIA", "IVY", "LILY", "ISABELLA", "ROSIE", "SOPHIA",
         "NOAH", "OLIVER", "GEORGE", "ARTHUR", "MUHAMMAD", "LEO", "HARRY", "OSCAR", "ARCHIE",
         "HENRY", "JACK", "CHARLIE", "FREDDIE", "THEO", "THOMAS", "JAMES", "WILLIAM", "ALFIE",
         "EMILY", "GRACE", "FREYA", "ELLA", "CHLOE", "JESSICA", "LUCY", "DANIEL", "SAMUEL"]
NICK = {"WILLIAM": "BILL", "THOMAS": "TOM", "JAMES": "JIM", "SAMUEL": "SAM",
        "DANIEL": "DAN", "ISABELLA": "BELLA", "JESSICA": "JESS", "HENRY": "HAL"}
SOURCES = ["HOSP-A", "HOSP-B", "GPNET", "LAB"]


def _typo(rng, s):
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def generate(n_people, seed=20260314, dup_rate=0.35):
    rng = random.Random(seed)
    records = []
    truth = []  # list of lists of record_ids belonging to one person
    seq = 0
    for p in range(n_people):
        family = rng.choice(FAMILY)
        given = rng.choice(GIVEN)
        dob = date(1930, 1, 1) + timedelta(days=rng.randrange(0, 80 * 365))
        sex = rng.choice("FFMMX")
        postcode = f"N{rng.randrange(1, 23)} {rng.randrange(1, 10)}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"
        phone = f"07{rng.randrange(100000000, 999999999)}" if rng.random() < 0.8 else ""
        n_rec = 1
        if rng.random() < dup_rate:
            n_rec += rng.choice([1, 1, 1, 2, 3])
        ids = []
        for k in range(n_rec):
            seq += 1
            rid = f"R{seq:06d}"
            f, g, d, ph, pc = family, given, dob, phone, postcode
            if k > 0:
                roll = rng.random()
                if roll < 0.25:
                    f = _typo(rng, f)
                elif roll < 0.40:
                    g = NICK.get(g, g[0])
                elif roll < 0.50 and d.day <= 12:
                    d = date(d.year, d.day, d.month)
                elif roll < 0.60:
                    ph = ""
                elif roll < 0.70:
                    pc = ""
                if rng.random() < 0.1:
                    d = None
            records.append(PatientRecord(rid, rng.choice(SOURCES), f.title(), g.title(),
                                         d, sex, pc, ph))
            ids.append(rid)
        truth.append(ids)
    rng.shuffle(records)
    return records, truth
