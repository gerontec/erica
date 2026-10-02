#!/usr/bin/env python3
"""Recompute a joint income tax assessment from estYYYY.json (see est_prefill.py)
and compare it with a reference calculation (e.g. WISO "Steuerberechnung").

  python3 est_calc.py 2025            # calculation
  python3 est_calc.py 2025 --compare  # diff against ~/steuer/wiso2025_calc.json

Covers what the 2025 return contains: employment (incl. § 34 severance), rental
income, basic pension, provision expenses § 10 (3)/(4), church tax, donations,
Riester § 10a with comparison, § 35a craftsmen, flat tax § 32d, § 32b progression.
"""
import json
import math
import os
import sys

import est_prefill
import tax_calc

# per-year parameters (only years verified against a reference)
PARAMS = {
    2025: {
        "employee_allowance": 1230,    # § 9a Nr. 1a
        "pension_wk_allowance": 102,   # § 9a Nr. 3
        "commute_rate": (0.30, 0.38),  # per km, from km 21 on
        "pension_cap": 29344,          # § 10 (3), doubled for joint
        "other_cap_reduced": 1900,     # § 10 (4)
        "other_cap_full": 2800,
        "special_allowance": 36,       # § 10c, doubled for joint
        "riester_base_bonus": 175,
        "riester_max": 2100,
        "craftsman_rate": 0.20, "craftsman_max": 1200,
    },
}


def pension_share(start_year):
    """Taxable share of basic pensions § 22 Nr. 1 S. 3 a aa (as of 2024 law)."""
    if start_year <= 2005:
        return 0.50
    if start_year <= 2020:
        return 0.50 + 0.02 * (start_year - 2005)
    if start_year <= 2022:
        return 0.80 + 0.01 * (start_year - 2020)
    return min(0.825 + 0.005 * (start_year - 2023), 1.0)


class Data:
    def __init__(self, d):
        self.d = d

    def get(self, form, kz=None, person=None, label=None, default=0, line=None):
        # Kz numbers repeat within a form (e.g. N: 110 = wage in line 5, days in line 29)
        for f in self.d["forms"]:
            if f["form"] != form or (person and f.get("person") != person):
                continue
            for fld in f["fields"]:
                if line is not None and fld["line"] != line:
                    continue
                if kz is not None and fld["kz"] == kz:
                    return fld["value"]
                if label is not None and fld["kz"] is None and label in fld["label"]:
                    return fld["value"]
        return default


def calculate(year):
    p = PARAMS[year]
    d = Data(est_prefill.load(year))
    church = d.d["general"].get("church_rate", 0.0)
    r = {}

    # employment income per person
    gross_a = d.get("N", "110", "A", line=5) + d.get("N", "111", "A", line=5)
    wk_a = (d.get("N", "310", "A") + d.get("N", "380", "A") + d.get("N", "660", "A")
            + d.get("N-DHF", "530", "A"))
    days, km = d.get("N", "110", "B", line=29), d.get("N", "111", "B", line=30)
    commute = days * (min(km, 20) * p["commute_rate"][0] + max(km - 20, 0) * p["commute_rate"][1])
    wk_b = math.floor(commute) + d.get("N", "310", "B") + d.get("N", "380", "B")
    gross_b = d.get("N", "110", "B", line=5)
    inc_a = gross_a - max(wk_a, p["employee_allowance"])
    inc_b = gross_b - max(wk_b, p["employee_allowance"])
    r["income_employment"] = {"A": inc_a, "B": inc_b}
    extraordinary = d.get("N", "165", "A") - d.get("N", "660", "A")

    # rental income, surplus split as in line 86
    rent = d.get("V", "01")
    rent_wk = d.get("V", "30") + d.get("V", "52") + d.get("V", "48")
    surplus = rent - rent_wk
    r["income_rental"] = {"A": math.ceil(surplus / 2), "B": surplus - math.ceil(surplus / 2)}

    # basic pension B
    pension = d.get("R", "101", "B")
    adj = d.get("R", "102", "B")
    start = int(str(d.get("R", "103", "B", default="01.01.2005"))[-4:])
    free = math.ceil((pension - adj) * (1 - pension_share(start)))
    taxable_pension = pension - free
    r["income_other"] = {"A": 0, "B": max(taxable_pension - p["pension_wk_allowance"], 0)}

    gde = sum(sum(r[k].values()) for k in ("income_employment", "income_rental", "income_other"))
    r["gde"] = gde

    # § 10 (3) pension provision
    an_rv = d.get("Vorsorgeaufwand", "300") + d.get("Vorsorgeaufwand", "400")
    ag_rv = d.get("Vorsorgeaufwand", "304") + d.get("Vorsorgeaufwand", "404")
    rurup = d.get("Vorsorgeaufwand", "303") + d.get("Vorsorgeaufwand", "403")
    r["pension_provision"] = min(an_rv + rurup + ag_rv, 2 * p["pension_cap"]) - ag_rv

    # § 10 (4) health / care / other
    kv_sick = d.get("Vorsorgeaufwand", "420")          # with sick pay -> minus 4 %
    cut = math.floor(kv_sick * 0.04)
    basic = (d.get("Vorsorgeaufwand", "350") + kv_sick - cut
             + d.get("Vorsorgeaufwand", "351") + d.get("Vorsorgeaufwand", "423")
             - d.get("Vorsorgeaufwand", "352"))
    other = basic + cut + d.get("Vorsorgeaufwand", "370") + d.get("Vorsorgeaufwand", "470")
    cap = 2 * (p["other_cap_reduced"] if d.get("Vorsorgeaufwand", "307") == 1 else p["other_cap_full"])
    r["basic_health"] = basic
    r["provision_total"] = r["pension_provision"] + max(min(other, cap), basic)

    special = (d.get("Sonderausgaben", "103") - d.get("Sonderausgaben", "104")
               + d.get("Sonderausgaben", "123"))
    r["special_unlimited"] = max(special, 2 * p["special_allowance"])

    zve_before_riester = gde - r["provision_total"] - r["special_unlimited"]

    # § 10a Riester (person A, directly entitled)
    own = d.get("AV", label="Riester-Eigenbeitrag", default=0)
    prev_income = d.get("AV", "100")
    min_own = max(min(prev_income * 0.04, p["riester_max"]) - p["riester_base_bonus"], 60)
    bonus = p["riester_base_bonus"] * min(own / min_own, 1) if own else 0.0
    deduction = math.ceil(min(own + bonus, p["riester_max"])) if own else 0
    joint = d.d["general"]["assessment"] == "joint"
    pv = d.get("ESt1A", "120")

    def tariff(zve):
        return tax_calc.tax_extraordinary(zve, year, joint, pv, extraordinary)

    with_ded = tariff(zve_before_riester - deduction)["tax"] + math.floor(bonus)
    without = tariff(zve_before_riester)["tax"]
    use_riester = own and with_ded < without
    r["riester_deduction"] = deduction if use_riester else 0
    r["riester_bonus_added"] = math.floor(bonus) if use_riester else 0
    r["riester_benefit"] = without - with_ded if use_riester else 0
    r["zve"] = zve_before_riester - r["riester_deduction"]

    t = tariff(r["zve"])
    r["tax_fifth_rule"], r["tax_normal"] = t["fifth_rule"], t["normal"]
    r["fifth_rule_detail"] = {k: t.get(k) for k in ("fifth_base", "pv_used", "rate")}
    labour = d.get("Haushaltsnahe Aufwendungen", "214")
    r["reduction_35a"] = min(math.floor(labour * p["craftsman_rate"]), p["craftsman_max"])
    tariff_tax = max(t["tax"] - r["reduction_35a"], 0) + r["riester_bonus_added"]

    # § 32d flat tax on capital income
    cap_inc = d.get("KAP", "210", "A")
    allowance = tax_calc.SAVER_ALLOWANCE * (2 if joint else 1)
    r["flat_tax"] = math.floor(max(cap_inc - allowance, 0) / (4 + church))
    r["income_tax"] = tariff_tax + r["flat_tax"]
    r["soli"] = tax_calc.soli(tariff_tax, year, joint) + tax_calc._cent(r["flat_tax"] * 0.055)
    r["church_tax"] = round(tax_calc.church_tax(tariff_tax, church)
                            + tax_calc.church_tax(r["flat_tax"], church), 2)

    # credits: wage tax rounded up, capital gains tax
    wage_tax = math.ceil(d.get("N", "140", "A") + d.get("N", "141", "A") + d.get("N", "140", "B"))
    wage_soli = d.get("N", "150", "A") + d.get("N", "150", "B")
    wage_church = d.get("N", "142", "A") + d.get("N", "143", "A") + d.get("N", "142", "B")
    r["refund_income_tax"] = round(wage_tax + d.get("KAP", "280", "A") - r["income_tax"], 2)
    r["refund_soli"] = round(wage_soli + d.get("KAP", "281", "A") - r["soli"], 2)
    r["refund_church_tax"] = round(wage_church + d.get("KAP", "282", "A") - r["church_tax"], 2)
    r["refund_total"] = round(r["refund_income_tax"] + r["refund_soli"] + r["refund_church_tax"], 2)
    return r


def compare(year, ref_path=None):
    ref_path = ref_path or os.path.join(est_prefill.DATA_DIR, f"wiso{year}_calc.json")
    with open(ref_path, encoding="utf-8") as f:
        ref = json.load(f)
    mine = calculate(year)
    rows = []
    for key, want in ref.items():
        if key == "source":
            continue
        got = mine.get(key)
        rows.append({"item": key, "reference": want, "calculated": got, "match": got == want})
    return {"year": year, "reference": ref.get("source"), "all_match": all(x["match"] for x in rows),
            "rows": rows}


if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    if "--compare" in sys.argv:
        c = compare(yr)
        for row in c["rows"]:
            mark = "ok " if row["match"] else "XX "
            print(f"{mark}{row['item']:<22} WISO {str(row['reference']):>22}   calc {row['calculated']}")
        print("\nALL MATCH" if c["all_match"] else "\nDIFFERENCES FOUND")
    else:
        print(json.dumps(calculate(yr), indent=2))
