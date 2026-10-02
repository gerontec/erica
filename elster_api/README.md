# elster_api

Small FastAPI service for German income tax: tariff maths, a full assessment
calculation, prefill from the previous year, and ELSTER XML generation checked
by ERiC. Independent of the archived erica service in this repository; only the
XML envelope layout was taken over from `erica/worker/elster_xml`.

| Module | Purpose |
|---|---|
| `tax_calc.py` | § 32a tariff 2023–2026, splitting, § 32b progression clause, § 34 fifth rule, Soli, church tax, § 32d flat tax |
| `est_calc.py` | assessment from form values to refund (verified cent-exact against a commercial tax program for 2025) |
| `est_prefill.py` | roll a return forward to the next year (carry / check / e-data / one-off) |
| `est_xml.py` | ELSTER E10 XML from the form values; field numbers, paths, order and formats from ERiC's `ericfelder.db3` |
| `eric_lib.py` | ctypes binding for ERiC (Linux `.so` or Windows `.dll`, the latter through Wine) |
| `elster_api.py` | REST endpoints |

## Run

```
pip install fastapi uvicorn
ERIC_HOME=/path/to/ERiC uvicorn elster_api:app --port 8095   # Linux ERiC
ERIC_WINE_DIR=/path/to/eric-win uvicorn elster_api:app        # ericapi.dll via Wine, check only
```

Endpoints: `/tax/income`, `/tax/severance`, `/tax/capital`, `/prefill/{year}`,
`/calc/{year}`, `/est/{year}/xml`, `/eric/version`, `/eric/validate`, `/eric/send`.

Tax data is read from `EST_DATA_DIR` (default `~/steuer`, files `estYYYY.json`)
and never belongs in this repository.

## Notes

- ERiC is not open source; get it from the ELSTER developer area with your own
  manufacturer id. The public test id 74931 is blocked in ERiC 43, so without an
  own id only the schema check (`EricCheckXML`) works, not the plausibility check.
- `/eric/send` is disabled unless `ERIC_ALLOW_SEND=1`; never through Wine.
- Struct layout of `eric_verschluesselungs_parameter_t` must be checked against
  `ericdef.h` of the ERiC release in use.
