#!/usr/bin/env python3
"""Mini REST API: German tax maths (tax_calc.py) + ELSTER ERiC via ctypes.

Run:  uvicorn elster_api:app --host 127.0.0.1 --port 8095
Docs: http://127.0.0.1:8095/docs

ERiC is optional. Download it from the ELSTER developer area
(https://www.elster.de/elsterweb/entwickler, needs a manufacturer account),
unpack and point ERIC_HOME at the directory containing lib/libericapi.so.

Env:
  ERIC_HOME         ERiC root dir (contains lib/ with plugins2/)
  ERIC_WINE_DIR     alternative: dir with ericapi.dll + plugins/, run through Wine
                    (validation only), Windows Python in ERIC_WINE_DIR/python
  ERIC_LOG_DIR      where eric.log goes (default ~/.cache/eric)
  ERIC_CERT         path to the .pfx ELSTER certificate (only for /eric/send)
  ERIC_PIN          certificate PIN (only for /eric/send)
  ERIC_ALLOW_SEND   must be "1" to enable /eric/send (real transmission!)
  ERIC_CRYPT_VER    version field of eric_verschluesselungs_parameter_t
                    (default 3, check ericdef.h of your ERiC release)
  EST_DATA_DIR      tax return data for /prefill (default ~/steuer, estYYYY.json)
"""
import os

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import eric_lib
import est_calc
import est_xml
import est_prefill
import tax_calc

app = FastAPI(title="Mini ELSTER API", version="0.1")

# --- tax maths -------------------------------------------------------------


class IncomeReq(BaseModel):
    year: int = 2025
    zve: float = Field(..., description="taxable income (zu versteuerndes Einkommen)")
    joint: bool = False
    church_rate: float = Field(0.0, description="0, 0.08 (BY/BW) or 0.09")


class SeveranceReq(BaseModel):
    year: int = 2025
    zve_other: float
    payment: float
    joint: bool = False
    church_rate: float = 0.0


class CapitalReq(BaseModel):
    income: float
    joint: bool = False
    church_rate: float = 0.0
    allowance_used: float = 0.0


def _call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/health")
def health():
    return {"ok": True, "eric_loaded": _eric is not None,
            "tax_years": sorted(tax_calc.TARIFF)}


@app.post("/tax/income")
def tax_income(r: IncomeReq):
    return _call(tax_calc.summary, r.zve, r.year, r.joint, r.church_rate)


@app.post("/tax/severance")
def tax_severance(r: SeveranceReq):
    return _call(tax_calc.severance, r.zve_other, r.payment, r.year,
                 r.joint, r.church_rate)


@app.post("/tax/capital")
def tax_capital(r: CapitalReq):
    return tax_calc.capital(r.income, r.joint, r.church_rate, r.allowance_used)


@app.get("/prefill/{year}")
def prefill(year: int, test: bool = Query(False, description="test copy of the same year")):
    try:
        return est_prefill.prefill(year, year if test else None)
    except FileNotFoundError as e:
        raise HTTPException(404, f"no source data: {e.filename}")


@app.get("/calc/{year}")
def calc(year: int, compare: bool = Query(False, description="diff against wisoYYYY_calc.json")):
    if year not in est_calc.PARAMS:
        raise HTTPException(400, f"no parameters for {year}, known: {sorted(est_calc.PARAMS)}")
    try:
        return est_calc.compare(year) if compare else est_calc.calculate(year)
    except FileNotFoundError as e:
        raise HTTPException(404, f"no data: {e.filename}")


# --- ERiC ------------------------------------------------------------------

ERIC_OK = eric_lib.ERIC_OK

_eric = None
_eric_error = None
try:
    if os.environ.get("ERIC_HOME"):
        _eric = eric_lib.Eric(os.environ["ERIC_HOME"])
    elif os.environ.get("ERIC_WINE_DIR"):
        _eric = eric_lib.WineEric(
            os.environ["ERIC_WINE_DIR"],
            os.environ.get("ERIC_WINE_PYTHON",
                           os.path.join(os.environ["ERIC_WINE_DIR"], "python", "python.exe")))
except Exception as e:  # keep the tax endpoints usable without ERiC
    _eric_error = str(e)


def _need_eric():
    if _eric is None:
        raise HTTPException(503, _eric_error or "ERiC not configured (set ERIC_HOME)")
    return _eric


XML_BODY = Body(..., media_type="application/xml")


@app.get("/eric/version")
def eric_version():
    rc, xml = _need_eric().version()
    return {"rc": rc, "xml": xml}


@app.post("/eric/validate")
def eric_validate(xml: str = XML_BODY,
                  datenart: str = Query("ESt_2025", description="e.g. ESt_2025, UStVA_2026")):
    rc, out, _ = _need_eric().process(xml, datenart)
    return {"ok": rc == ERIC_OK, "rc": rc, "result": out}


@app.post("/eric/send")
def eric_send(xml: str = XML_BODY, datenart: str = Query("ESt_2025")):
    if os.environ.get("ERIC_ALLOW_SEND") != "1":
        raise HTTPException(403, "sending disabled (set ERIC_ALLOW_SEND=1)")
    cert, pin = os.environ.get("ERIC_CERT"), os.environ.get("ERIC_PIN")
    if not cert or not pin:
        raise HTTPException(400, "ERIC_CERT and ERIC_PIN required")
    rc, out, srv = _need_eric().process(xml, datenart, send=True, cert=cert, pin=pin)
    return {"ok": rc == ERIC_OK, "rc": rc, "result": out, "server": srv}


@app.get("/est/{year}/xml")
def est_xml_generate(year: int, check: bool = Query(True, description="ERiC schema check")):
    """ELSTER XML (test merker) from estYYYY.json, optionally schema-checked by ERiC."""
    try:
        full, res = est_xml.generate(_need_eric(), year, validate=check)
    except FileNotFoundError as e:
        raise HTTPException(404, f"no data: {e.filename}")
    except (KeyError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    return {"year": year, "check": res, "xml": full}
