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
| `otto_lib.py` | ctypes binding for Otto (`libotto.so`): upload of large attachments to OTTER (object id for `Anhang/DateiReferenzId`, e.g. Belegnachreichung) and download by object id |
| `elster_api.py` | REST endpoints |

## Run

```
pip install fastapi uvicorn
ERIC_HOME=/path/to/ERiC-44.3.6.0/Linux-x86_64 uvicorn elster_api:app --port 8095   # Linux ERiC
ERIC_WINE_DIR=/path/to/eric-win uvicorn elster_api:app        # ericapi.dll via Wine, check only
```

Endpoints: `/tax/income`, `/tax/severance`, `/tax/capital`, `/prefill/{year}`,
`/calc/{year}`, `/est/{year}/xml`, `/eric/version`, `/eric/validate`, `/eric/send`.

Tax data is read from `EST_DATA_DIR` (default `~/steuer`, files `estYYYY.json`)
and never belongs in this repository.

## Notes

- ERiC is not open source and its licence does not allow passing it on by
  itself: get it from the ELSTER developer area (`ERiC-<ver>-Linux-x86_64.jar`,
  unzip it) with your own manufacturer id. ERiC binaries, headers, plugins,
  documentation, test certificates and `ericfelder.db3` are kept out of git
  (`.gitignore`). Bindings follow the ERiC 44.3 headers.
  Whether a manufacturer id and the runtime libraries may ship with this open
  source program is asked in an open letter:
  [doc/open_letter](../doc/open_letter/2026-10-02_hersteller_id_erica.md).
- The public test id 74931 is blocked since ERiC 43, so without an own id
  (`ERIC_HERSTELLER_ID`) only the schema check (`EricCheckXML`) works; with it,
  `est_xml.py --validate` also runs the plausibility check (`EricBearbeiteVorgang`).
- `/eric/send` and `otto_lib.py upload` are disabled unless `ERIC_ALLOW_SEND=1`;
  never through Wine. Otto rejects small files (3 MiB too small, the ottodemo
  uses at least 20 MiB); smaller receipts go inline as `Anhang/Dateiinhalt`.
  `otto_lib.py checksum <file>` signs locally and tests certificate + PIN.
- `eric_verschluesselungs_parameter_t` has version 3 in ERiC 44; check
  `eric_types.h` when switching releases.
