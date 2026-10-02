#!/usr/bin/env python3
"""German income tax maths (§ 32a EStG tariff, splitting, Soli, church tax,
fifth rule § 34 for severance pay, flat tax on capital income § 32d).

Pure functions, no I/O. Amounts in EUR. Rounding as in the law:
zvE and tax rounded down to full euro, Soli/church tax down to full cent.
"""
import math

# § 32a (1) EStG per year:
# basic allowance, end zone 2, end zone 3, end zone 4,
# zone 2 coeff, zone 3 coeff, zone 3 constant, zone 4 deduction, zone 5 deduction
TARIFF = {
    2023: (10908, 15999, 62809, 277825, 979.18, 192.59, 966.53, 9972.98, 18307.73),
    2024: (11784, 17005, 66760, 277825, 954.80, 181.19, 991.21, 10636.31, 18971.06),
    2025: (12096, 17443, 68480, 277825, 932.30, 176.64, 1015.13, 10911.92, 19246.67),
    2026: (12348, 17799, 69878, 277825, 914.51, 173.10, 1034.87, 11135.63, 19470.38),
}

# § 3 SolZG exemption limit on income tax (single assessment; doubled for joint)
SOLI_LIMIT = {2023: 17543, 2024: 18130, 2025: 19950, 2026: 20350}

SAVER_ALLOWANCE = 1000  # § 20 (9) EStG, doubled for joint assessment


def _params(year):
    if year not in TARIFF:
        raise ValueError(f"year {year} not supported, known: {sorted(TARIFF)}")
    return TARIFF[year]


def tariff(zve, year):
    """Income tax for a single person per § 32a (1) EStG."""
    gfb, e2, e3, e4, a2, a3, c3, d4, d5 = _params(year)
    x = math.floor(max(zve, 0))
    if x <= gfb:
        tax = 0.0
    elif x <= e2:
        y = (x - gfb) / 10000
        tax = (a2 * y + 1400) * y
    elif x <= e3:
        z = (x - e2) / 10000
        tax = (a3 * z + 2397) * z + c3
    elif x <= e4:
        tax = 0.42 * x - d4
    else:
        tax = 0.45 * x - d5
    return math.floor(tax)


def income_tax(zve, year, joint=False):
    """Income tax, with splitting (§ 32a (5)) when joint."""
    if joint:
        return 2 * tariff(math.floor(zve) / 2, year)
    return tariff(zve, year)


def progression_rate(base, year, joint=False):
    """Average rate for § 32b, truncated to 4 decimals of a percent."""
    if base <= 0:
        return 0.0
    return math.floor(income_tax(base, year, joint) / math.floor(base) * 1e6) / 1e6


def tax_with_pv(zve, year, joint=False, pv=0.0):
    """Income tax incl. progression clause § 32b (pv = exempt replacement income)."""
    if not pv:
        return income_tax(zve, year, joint)
    rate = progression_rate(zve + pv, year, joint)
    return math.floor(math.floor(max(zve, 0)) * rate)


def tax_extraordinary(zve, year, joint=False, pv=0.0, extraordinary=0.0):
    """Income tax with fifth rule § 34 (1) and progression clause § 32b.

    If the extraordinary income exceeds zvE, the negative remaining zvE is
    first offset against the progression income (BFH), as WISO does it.
    Returns the cheaper of fifth rule and normal taxation, plus both values.
    """
    normal = tax_with_pv(zve, year, joint, pv)
    if extraordinary <= 0:
        return {"tax": normal, "fifth_rule": None, "normal": normal}
    rest = zve - extraordinary
    e = extraordinary
    pv_eff = pv
    if rest < 0:
        pv_eff = max(pv + rest, 0)
        e, rest = zve, 0
    base = tax_with_pv(rest, year, joint, pv_eff)
    fifth = tax_with_pv(rest + e / 5, year, joint, pv_eff)
    fifth_total = base + 5 * (fifth - base)
    return {"tax": min(fifth_total, normal), "fifth_rule": fifth_total,
            "normal": normal, "fifth_base": math.floor(rest + e / 5),
            "pv_used": pv_eff,
            "rate": progression_rate(rest + e / 5 + pv_eff, year, joint)}


def _cent(v):
    return math.floor(round(v * 100, 6)) / 100


def soli(est, year, joint=False):
    """Solidarity surcharge incl. phase-in zone (11.9 % of the excess)."""
    limit = SOLI_LIMIT[year] * (2 if joint else 1)
    if est <= limit:
        return 0.0
    return _cent(min(0.055 * est, 0.119 * (est - limit)))


def church_tax(est, rate):
    """rate 0.08 (BY, BW) or 0.09 (other states), 0 = not a member."""
    return _cent(est * rate)


def summary(zve, year, joint=False, church_rate=0.0):
    est = income_tax(zve, year, joint)
    s = soli(est, year, joint)
    k = church_tax(est, church_rate)
    total = est + s + k
    return {
        "year": year, "zve": math.floor(zve), "joint": joint,
        "income_tax": est, "soli": s, "church_tax": k,
        "total": round(total, 2),
        "avg_rate": round(est / zve, 4) if zve > 0 else 0.0,
        "marginal_rate": round(income_tax(zve + 100, year, joint) / 100
                               - est / 100, 4),
    }


def severance(zve_other, payment, year, joint=False, church_rate=0.0):
    """Fifth rule § 34 (1) EStG for extraordinary income (e.g. severance).

    zve_other = taxable income without the payment.
    """
    base = income_tax(zve_other, year, joint)
    fifth = income_tax(zve_other + payment / 5, year, joint)
    extra = 5 * (fifth - base)
    normal = income_tax(zve_other + payment, year, joint)
    est = base + extra
    return {
        "year": year, "zve_other": math.floor(zve_other), "payment": payment,
        "income_tax_total": est,
        "income_tax_on_payment": extra,
        "without_fifth_rule": normal - base,
        "saving": normal - est,
        "soli": soli(est, year, joint),
        "church_tax": church_tax(est, church_rate),
    }


def capital(income, joint=False, church_rate=0.0, allowance_used=0.0):
    """Flat tax on capital income § 32d EStG (25 %, reduced by church tax
    per § 32d (1) S. 3: tax = e / (4 + k)). Soli always 5.5 % here, the
    exemption limit does not apply to the flat tax."""
    allowance = SAVER_ALLOWANCE * (2 if joint else 1) - allowance_used
    base = max(income - max(allowance, 0), 0)
    tax = _cent(base / (4 + church_rate))
    return {
        "income": income, "allowance": max(allowance, 0), "taxable": base,
        "flat_tax": tax, "soli": _cent(tax * 0.055),
        "church_tax": _cent(tax * church_rate),
        "total": round(tax + _cent(tax * 0.055) + _cent(tax * church_rate), 2),
    }


if __name__ == "__main__":
    import sys
    zve = float(sys.argv[1]) if len(sys.argv) > 1 else 50000
    yr = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    print(summary(zve, yr))
    print(summary(zve, yr, joint=True))
