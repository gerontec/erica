#!/usr/bin/env python3
"""Prefill an income tax return from a previous one (JSON in EST_DATA_DIR).

  python3 est_prefill.py 2026          # roll est2025.json forward to 2026
  python3 est_prefill.py 2025 --test   # test copy of 2025 (same year, all values)

Field kinds (see "kinds" in the JSON):
  master/carry -> value taken over
  variable     -> value taken over, flagged "check"
  edata        -> left empty (Belegabruf), last value kept as reference
  oneoff       -> dropped (listed separately)
A test copy (target year == source year) keeps every value unchanged.
"""
import copy
import json
import os
import re
import sys

DATA_DIR = os.environ.get("EST_DATA_DIR", os.path.expanduser("~/steuer"))


def load(year):
    with open(os.path.join(DATA_DIR, f"est{year}.json"), encoding="utf-8") as f:
        return json.load(f)


def _shift_year(value, src, dst):
    # only dates ending in the source year, e.g. 31.12.2025 or 01.01.-31.12.2025
    if isinstance(value, str):
        return re.sub(rf"(\d\d\.\d\d\.){src}\b", rf"\g<1>{dst}", value)
    return value


def prefill(target, source=None):
    source = source or target - 1
    src = load(source)
    test = target == source
    out = {"year": target, "source_year": source, "test_copy": test,
           "general": copy.deepcopy(src["general"]), "forms": [], "dropped": []}
    for form in src["forms"]:
        nf = {k: v for k, v in form.items() if k != "fields"}
        nf["fields"] = []
        for fld in form["fields"]:
            f = dict(fld)
            kind = f["kind"]
            if test:
                f["status"] = "test"
            elif kind == "oneoff":
                out["dropped"].append({"form": form["form"], **f})
                continue
            elif kind == "edata":
                f["reference"], f["value"], f["status"] = f["value"], None, "edata"
            else:
                f["value"] = _shift_year(f["value"], source, target)
                f["status"] = "check" if kind == "variable" else "ok"
            nf["fields"].append(f)
        if nf["fields"]:
            out["forms"].append(nf)
    return out


def print_table(p):
    print(f"ESt {p['year']} prefilled from {p['source_year']}"
          + (" (TEST COPY)" if p["test_copy"] else ""))
    for form in p["forms"]:
        who = f" ({form['person']})" if form.get("person") else ""
        print(f"\n== Anlage {form['form']}{who}")
        for f in form["fields"]:
            val = f["value"] if f["value"] is not None else f"[eDaten, VJ {f['reference']}]"
            note = f"  ! {f['note']}" if f.get("note") else ""
            print(f"  Z{f['line']:>3} Kz{(f['kz'] or '-'):>4}  {f['status']:<5} "
                  f"{f['label'][:58]:<58} {val}{note}")
    if p["dropped"]:
        print("\n== not carried over (one-off)")
        for f in p["dropped"]:
            print(f"  {f['form']:<26} Z{f['line']:>3}  {f['label'][:50]:<50} {f['value']}")


if __name__ == "__main__":
    tgt = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    print_table(prefill(tgt, tgt if "--test" in sys.argv else None))
