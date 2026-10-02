#!/usr/bin/env python3
"""Build an ELSTER ESt XML (E10) from estYYYY.json and let ERiC check it.

  python3 est_xml.py 2025            # write ~/steuer/est2025_elster.xml (test merker)
  python3 est_xml.py 2025 --validate # ... and validate through ERiC

Field numbers, XML paths (Kontext), order and formats come from ERiC's field
database (ericfelder.db3, shipped with ERiC 43.x) - nothing is hard coded
except which form value goes into which field number (MAP below).
Always generated with test merker 700000004 / test manufacturer id 74931.
"""
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

import est_calc
import est_prefill

FIELD_DB = os.environ.get("ERIC_FIELD_DB", os.path.expanduser("~/eric-win/ericfelder.db3"))
ELSTER_NS = "http://www.elster.de/elsterxml/schema/v11"
E10_NS = "http://finkonsens.de/elster/elstererklaerung/est/e10/v{year}"
TEST_MERKER, TEST_HERSTELLER = "700000004", "74931"
# form abbreviation -> ELSTER religion key (source: erica est_mapping.py, VZ 2021)
RELIGION = {"VD": "11", "EV": "02", "RK": "03", "AK": "04", "ER": "05", "FR": "07"}


def build_map(d):
    """(vordruck, person, field number, value) for everything in the return.

    d is est_calc.Data. person: None, "A" or "B". Values None are skipped.
    """
    g = d.d["general"]
    a, b = g["person_a"], g["person_b"]
    adr = g["address"]
    N = lambda kz, p, line=None: d.get("N", kz, p, line=line, default=None)
    T = lambda form, label, p=None: d.get(form, None, p, label=label, default=None)
    m = [
        # Hauptvordruck
        ("ESt1A", None, "E0100001", "X"),
        ("ESt1A", None, "E0100002", "X" if g.get("employee_savings_bonus_requested") else None),
        ("ESt1A", None, "E0100081", a["idnr"]), ("ESt1A", None, "E0100401", a["birth"]),
        ("ESt1A", None, "E0100201", a["name"]), ("ESt1A", None, "E0100301", a["first_name"]),
        ("ESt1A", None, "E0100402", RELIGION[a["religion"]]), ("ESt1A", None, "E0100403", a["occupation"]),
        ("ESt1A", None, "E0101104", adr["street"]), ("ESt1A", None, "E0101206", adr["house_no"]),
        ("ESt1A", None, "E0100601", adr["zip"]), ("ESt1A", None, "E0100602", adr["city"]),
        ("ESt1A", None, "E0100701", g["married_since"]),
        ("ESt1A", None, "E0101201", "X" if g["assessment"] == "joint" else None),
        ("ESt1A", None, "E0100082", b["idnr"]), ("ESt1A", None, "E0101001", b["birth"]),
        ("ESt1A", None, "E0100901", b["name"]), ("ESt1A", None, "E0100801", b["first_name"]),
        ("ESt1A", None, "E0101002", RELIGION[b["religion"]]), ("ESt1A", None, "E0101003", b["occupation"]),
        ("ESt1A", None, "E0102102", g["iban"]),
        ("ESt1A", None, "E0101601" if g["account_holder"] == "A" else "E0102402", "X"),
        ("ESt1A", "A", "E0104110", "Arbeitslosengeld"),
        ("ESt1A", "A", "E0104113", d.get("ESt1A", "120", default=None)),
        ("ESt1A", "A", "E0104801", d.get("ESt1A", "120", default=None)),
        # Sonderausgaben
        ("SA", None, "E0107601", d.get("Sonderausgaben", "103", default=None)),
        ("SA", None, "E0107602", d.get("Sonderausgaben", "104", default=None)),
        ("SA", None, "E0108102", T("Sonderausgaben", "Spendenempfänger")),
        ("SA", None, "E0108103", d.get("Sonderausgaben", "123", default=None)),
        ("SA", None, "E0108105", d.get("Sonderausgaben", "123", default=None)),
        # Haushaltsnahe Aufwendungen
        ("HA_35a", None, "E0111217", T("Haushaltsnahe Aufwendungen", "Art der Handwerkerleistung")),
        ("HA_35a", None, "E0170601", d.get("Haushaltsnahe Aufwendungen", label="Rechnungsbetrag", default=None)),
        ("HA_35a", None, "E0111214", d.get("Haushaltsnahe Aufwendungen", "214", default=None)),
        ("HA_35a", None, "E0111215", d.get("Haushaltsnahe Aufwendungen", "214", default=None)),
    ]
    for p in ("A", "B"):
        m += [
            ("N", p, "E0200002", N("168", p)),
            ("N", p, "E0200201", N("110", p, 5)), ("N", p, "E0200301", N("140", p)),
            ("N", p, "E0200401", N("150", p)), ("N", p, "E0200501", N("142", p)),
            ("N", p, "E0200203", N("111", p, 5)), ("N", p, "E0200303", N("141", p)),
            ("N", p, "E0200503", N("143", p)),
        ]
    m += [
        ("N", "A", "E0201806", N("165", "A")),
        ("N", "A", "E0204401", T("N", "Art der Arbeitsmittel", "A")),
        ("N", "A", "E0204402", N("310", "A")), ("N", "A", "E0204403", N("310", "A")),
        ("N", "A", "E0205405", T("N", "Bezeichnung weitere Werbungskosten", "A")), ("N", "A", "E0205406", N("380", "A")),
        ("N", "A", "E0206503", T("N", "Art der Aufwendungen Entschädigung", "A")), ("N", "A", "E0206502", N("660", "A")),
        ("N", "B", "E0203003", "1"),
        ("N", "B", "E0203501", T("N", "Adresse erste Tätigkeitsstätte", "B")),
        ("N", "B", "E0203101", "01.01-31.12"),
        ("N", "B", "E0203508", str(d.get("N", None, "B", label="Arbeitstage je Woche"))),
        ("N", "B", "E0203509", d.get("N", None, "B", label="Urlaubs-")),
        ("N", "B", "E0203503", N("110", "B", 29)), ("N", "B", "E0203504", N("111", "B", 30)),
        ("N", "B", "E0203505", N("112", "B", 31)),
        ("N", "B", "E0204001", T("N", "Bezeichnung Berufsverband", "B")), ("N", "B", "E0204003", N("310", "B")),
        ("N", "B", "E0204002", N("310", "B")),
        ("N", "B", "E0205405", T("N", "Bezeichnung weitere Werbungskosten", "B")), ("N", "B", "E0205406", N("380", "B")),
        # doppelte Haushaltsfuehrung
        ("N_DHH", "A", "E0206103", d.get("N-DHF", "501", "A")),
        ("N_DHH", "A", "E0206205", d.get("N-DHF", None, "A", label="Grund")),
        ("N_DHH", "A", "E0206304", str(d.get("N-DHF", "502", "A"))[:6]),
        ("N_DHH", "A", "E0206404", d.get("N-DHF", None, "A", label="Beschäftigungsort")),
        ("N_DHH", "A", "E0206504", d.get("N-DHF", "503", "A")),
        ("N_DHH", "A", "E0206505", T("N-DHF", "Ort eigener Hausstand", "A")),
        ("N_DHH", "A", "E0206506", d.get("N-DHF", "504", "A")),
        ("N_DHH", "A", "E0206805", d.get("N-DHF", "510", "A")),
        ("N_DHH", "A", "E0207611", d.get("N-DHF", "530", "A")),
        # Kapitalertraege
        ("KAP", "A", "E1900501", d.get("KAP", "202", "A")),
        ("KAP", "A", "E1900701", d.get("KAP", "210", "A")),
        ("KAP", "A", "E1900901", d.get("KAP", "212", "A")),
        ("KAP", "A", "E1901401", d.get("KAP", "217", "A")),
        ("KAP", "A", "E1901402", d.get("KAP", "218", "A")),
        ("KAP", "A", "E1904701", d.get("KAP", "280", "A")),
        ("KAP", "A", "E1904901", d.get("KAP", "281", "A")),
        ("KAP", "A", "E1904801", d.get("KAP", "282", "A")),
        # Rente
        ("R", "B", "E1800301", d.get("R", "101", "B")),
        ("R", "B", "E1800606", d.get("R", "102", "B")),
        ("R", "B", "E1800501", d.get("R", "103", "B")),
        # Vermietung
        ("V", None, "E0700407", T("V", "Straße Objekt")), ("V", None, "E0700503", T("V", "PLZ Objekt")),
        ("V", None, "E0700504", T("V", "Ort Objekt")),
        ("V", None, "E0700605", d.get("V", None, label="Aktenzeichen")),
        ("V", None, "E0700707", T("V", "Bauantrag vom")), ("V", None, "E0700103", T("V", "Fertig gestellt am")),
        ("V", None, "E0700703", d.get("V", "61")), ("V", None, "E0700705", d.get("V", "63")),
        ("V", None, "E0700704", d.get("V", "62")),
        ("V", None, "E0700702", d.get("V", "54")), ("V", None, "E0700104", d.get("V", "55")),
        ("V", None, "E0700106", d.get("V", "56")),
        ("V", None, "E0701202", T("V", "Bezeichnung Wohneinheit")),
        ("V", None, "E0700302", T("V", "Wohnfläche Wohneinheit")),
        ("V", None, "E0700201", d.get("V", "01")), ("V", None, "E0700206", d.get("V", "01")),
        ("V", None, "E0701401", d.get("V", "01")),
        ("V", None, "E0702404", d.get("V", "13")),
        ("V", None, "E0703417", "1"), ("V", None, "E0703419", "1"),
        ("V", None, "E0703424", d.get("V", "30")), ("V", None, "E0703511", d.get("V", "30")),
        ("V", None, "E0707301", T("V", "Einzelangaben umgelegte Kosten")), ("V", None, "E0707304", d.get("V", "52")),
        ("V", None, "E0704418", d.get("V", "52")),
        ("V", None, "E0707601", T("V", "Einzelangaben nicht umgelegte Kosten")),
        ("V", None, "E0707602", T("V", "Gesamtbetrag nicht umgelegte Kosten")),
        ("V", None, "E0707603", T("V", "Anteil nicht umgelegte Kosten")), ("V", None, "E0707604", d.get("V", "48")),
        ("V", None, "E0705515", d.get("V", "48")),
        ("V", None, "E0705701", d.get("V", "30") + d.get("V", "52") + d.get("V", "48")),
        ("V", None, "E0701601", d.get("V", "01") - d.get("V", "30") - d.get("V", "52") - d.get("V", "48")),
        ("V", None, "E0701801", d.get("V", "20")), ("V", None, "E0701802", d.get("V", "21")),
        # Ferienwohnung
        ("V_FeWo", None, "E0730501", d.get("V", None, label="Aktenzeichen")),
        ("V_FeWo", None, "E0730602", "Ferienwohnung"),
        ("V_FeWo", None, "E0730601", d.get("V-FeWo", None, label="Wohnfläche")),
        ("V_FeWo", None, "E0730701", d.get("V-FeWo", None, label="auch selbst genutzt")),
        ("V_FeWo", None, "E0730801", d.get("V-FeWo", None, label="Tage Selbstnutzung")),
        ("V_FeWo", None, "E0730802", d.get("V-FeWo", None, label="Vermietungstage")),
        ("V_FeWo", None, "E0730803", d.get("V-FeWo", None, label="Leerstandstage")),
        # Vorsorgeaufwand (person specific sub elements)
        ("VOR", "A", "E2000401", d.get("Vorsorgeaufwand", "300", default=None)),
        ("VOR", "B", "E2000401", d.get("Vorsorgeaufwand", "400", default=None)),
        ("VOR", "A", "E2000701", d.get("Vorsorgeaufwand", "303", default=None)),
        ("VOR", "B", "E2000701", d.get("Vorsorgeaufwand", "403", default=None)),
        ("VOR", "A", "E2000801", d.get("Vorsorgeaufwand", "304", default=None)),
        ("VOR", "B", "E2000801", d.get("Vorsorgeaufwand", "404", default=None)),
        ("VOR", "B", "E2001203", d.get("Vorsorgeaufwand", "420", default=None)),
        ("VOR", "B", "E2001505", d.get("Vorsorgeaufwand", "423", default=None)),
        ("VOR", "A", "E2003104", d.get("Vorsorgeaufwand", "350", default=None)),
        ("VOR", "A", "E2003202", d.get("Vorsorgeaufwand", "351", default=None)),
        ("VOR", "A", "E2003302", d.get("Vorsorgeaufwand", "352", default=None)),
        ("VOR", "A", "E2004403", d.get("Vorsorgeaufwand", "370", default=None)),
        ("VOR", "B", "E2004403", d.get("Vorsorgeaufwand", "470", default=None)),
        ("VOR", "A", "E2005303", d.get("Vorsorgeaufwand", "382", default=None)),
        ("VOR", "A", "E2002301", T("Vorsorgeaufwand", "Tätigkeitsbezeichnung keine RV-Pflicht A")),
        ("VOR", "A", "E2002401", d.get("Vorsorgeaufwand", "383", default=None)),
        # Altersvorsorge (Riester)
        ("AV", "A", "E2003901", d.get("AV", "106", default=None)),
        ("AV", "A", "E2004001", d.get("AV", "100", default=None)),
    ]
    return [x for x in m if x[3] not in (None, "", "None")]


class FieldDB:
    def __init__(self, year, path=FIELD_DB):
        self.year = year
        self.c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def field(self, vordruck, nr):
        rows = self.c.execute(
            "select rowid, Kontext, Formatkennzeichen, Formattext from Feldformate "
            "where VZ=? and Steuerart='EST' and Vordruck=? and Feldnummer=? order by rowid",
            (self.year, vordruck, nr)).fetchall()
        if len(rows) != 1:
            raise KeyError(f"{vordruck}/{nr}: {len(rows)} matches in field db")
        return rows[0]

    def person_contexts(self, vordruck):
        return [k for (k,) in self.c.execute(
            "select Kontext from Feldformate where VZ=? and Steuerart='EST' and Vordruck=? "
            "and Feldnummer='Person'", (self.year, vordruck))]

    def form_order(self):
        return {n: i for i, (n,) in enumerate(self.c.execute(
            "select Bezeichnung from Formulare where VZ=? and Steuerart='EST' order by rowid",
            (self.year,)))}


def fmt(value, kz, text):
    """Format a value as ELSTER expects it (decimal comma, X / 1 flags)."""
    if kz == "X":
        return "X"
    if isinstance(value, (int, float)):
        if "MitCent" in text or "genau 2 Nachkomma" in text:
            return f"{value:.2f}".replace(".", ",")
        if "OhneCent" in text or "ohne Nachkomma" in text or kz in "JYH":
            return str(int(round(value)))
    return str(value)


class Node:
    def __init__(self, name, order=None):
        self.name, self.order, self.children, self.text = name, order, [], None

    def child(self, name, key):
        for c in self.children:
            if c.name == name and getattr(c, "key", None) == key:
                return c
        n = Node(name)
        n.key = key
        self.children.append(n)
        return n

    def sort_key(self):
        if self.order is not None:
            return self.order
        # a leading <Person> must not pull its container to the front
        return min((c.sort_key() for c in self.children if c.name != "Person"), default=10**9)

    def to_xml(self, parent):
        e = ET.SubElement(parent, self.name)
        if self.text is not None:
            e.text = self.text
        for c in sorted(self.children, key=Node.sort_key):
            c.to_xml(e)


def build_e10(year, data):
    db = FieldDB(year)
    root = Node("E10")
    forms_order = db.form_order()
    for vordruck, person, nr, value in build_map(data):
        rowid, kontext, kz, text = db.field(vordruck, nr)
        pctx = db.person_contexts(vordruck)
        segments = [] if kontext == "unknown" else kontext.split("/")
        form_key = person if "unknown" in pctx else None
        node = root.child(vordruck, form_key)
        node.order = forms_order.get(vordruck, 999) * 10**6
        if form_key:
            pn = node.child("Person", None)
            pn.order, pn.text = -1, "Person" + person
        for i, seg in enumerate(segments):
            ctx = "/".join(segments[:i + 1])
            key = person if ctx in pctx else None
            node = node.child(seg, key)
            if key:
                pn = node.child("Person", None)
                pn.order, pn.text = -1, "Person" + person
        leaf = node.child(nr, None)
        leaf.order, leaf.text = rowid, fmt(value, kz, text)
    return root, db


def vorsatz(year, data, stnr13):
    g = data.d["general"]
    a, adr = g["person_a"], g["address"]
    v = Node("Vorsatz")
    items = [("Unterfallart", "10"), ("Vorgang", "01"), ("StNr", stnr13),
             ("ID", a["idnr"]), ("IDEhefrau", g["person_b"]["idnr"]), ("Zeitraum", str(year)),
             ("AbsName", f"{a['first_name']} {a['name']}"),
             ("AbsStr", f"{adr['street']} {adr['house_no']}"), ("AbsPlz", adr["zip"]),
             ("AbsOrt", adr["city"]), ("Copyright", "(C) 2026 gerontec elster_api"),
             ("OrdNrArt", "S")]
    for i, (k, val) in enumerate(items):
        n = v.child(k, None)
        n.order, n.text = i, val
    r = v.child("Rueckuebermittlung", None)
    b = r.child("Bescheid", None)
    b.order, b.text = 0, "2"
    r.order = len(items)
    return v


def datenteil(year, stnr13):
    data = est_calc.Data(est_prefill.load(year))
    e10, db = build_e10(year, data)
    v = vorsatz(year, data, stnr13)
    v.order = db.form_order().get("Vorsatz", 999) * 10**6
    e10.children.append(v)
    ET.register_namespace("", ELSTER_NS)
    top = ET.Element(f"{{{ELSTER_NS}}}Elster")
    dt = ET.SubElement(top, "DatenTeil")
    nb = ET.SubElement(dt, "Nutzdatenblock")
    nh = ET.SubElement(nb, "NutzdatenHeader", version="11")
    ET.SubElement(nh, "NutzdatenTicket").text = "1"
    ET.SubElement(nh, "Empfaenger", id="F").text = data.d["general"]["tax_office_bufa"]
    nd = ET.SubElement(nb, "Nutzdaten")
    holder = ET.Element("x")
    e10.to_xml(holder)
    e10_el = holder[0]
    e10_el.set("xmlns", E10_NS.format(year=year))
    e10_el.set("version", str(year))
    nd.append(e10_el)
    xml = minidom.parseString(ET.tostring(top)).childNodes[0].toprettyxml(indent="  ")
    return xml


def generate(eric, year, validate=False):
    """Returns (full xml, validation result or None)."""
    g = est_prefill.load(year)["general"]
    calls = [["make_elster_stnr", g["tax_number"], g["tax_office_land"], g["tax_office_bufa"]]]
    (rc, stnr13), = eric.batch(calls) if hasattr(eric, "batch") else [eric.make_elster_stnr(*calls[0][1:])]
    if rc != 0:
        raise RuntimeError(f"tax number: {stnr13}")
    body = datenteil(year, stnr13)
    th_kw = {"datenart": "ESt", "testmerker": TEST_MERKER, "hersteller_id": TEST_HERSTELLER}
    if hasattr(eric, "batch"):
        res = eric.batch([["create_th", body, th_kw]])
        rc, full = res[0]
    else:
        rc, full = eric.create_th(body, **th_kw)
    if rc != 0:
        raise RuntimeError(f"EricCreateTH rc={rc}: {full[:500]}")
    result = None
    if validate:
        # schema check only: plausibility checks (EricBearbeiteVorgang) need an own manufacturer id
        rc, out = eric.check_xml(full, f"ESt_{year}")
        result = {"ok": rc == 0, "rc": rc, "result": out}
    return full, result


if __name__ == "__main__":
    import eric_lib
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    wdir = os.environ.get("ERIC_WINE_DIR", os.path.expanduser("~/eric-win"))
    eric = (eric_lib.Eric(os.environ["ERIC_HOME"]) if os.environ.get("ERIC_HOME")
            else eric_lib.WineEric(wdir, os.path.join(wdir, "python", "python.exe")))
    full, res = generate(eric, yr, "--validate" in sys.argv)
    out = os.path.join(est_prefill.DATA_DIR, f"est{yr}_elster.xml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(full)
    os.chmod(out, 0o600)
    print("written", out, len(full), "bytes")
    if res:
        print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])
