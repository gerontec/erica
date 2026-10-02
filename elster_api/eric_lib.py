#!/usr/bin/env python3
"""ctypes binding for ELSTER ERiC (singlethread API), stdlib only.

Signatures follow the ERiC 44 headers (ericapi.h, eric_types.h). Works natively
on Linux (ERiC-<ver>-Linux-x86_64.jar, unpacked: lib/libericapi.so with
lib/plugins) and on Windows / under Wine (ericapi.dll). For Linux without an
own ERiC download, WineEric runs this file under a Windows Python in Wine as a
bridge:

  wine python.exe eric_lib.py <eric_dir> version
  wine python.exe eric_lib.py <eric_dir> validate <xml_file> <datenart>

The bridge prints one JSON object {"rc", "result", "server"} to stdout.
"""
import ctypes
import json
import os
import subprocess
import sys
import threading

ERIC_OK = 0
ERIC_VALIDIERE = 1 << 1
ERIC_SENDE = 1 << 2
ERIC_PRUEFE_HINWEISE = 1 << 7

WINDOWS = os.name == "nt"
# own manufacturer id from the ELSTER developer area; 74931 is the public test id
# (blocked for plausibility checks since ERiC 43)
HERSTELLER_ID = os.environ.get("ERIC_HERSTELLER_ID", "74931")


class CryptParams(ctypes.Structure):
    # eric_verschluesselungs_parameter_t (eric_types.h); version must be 3 in ERiC 44
    _fields_ = [("version", ctypes.c_uint32),
                ("zertifikatHandle", ctypes.c_uint32),
                ("pin", ctypes.c_char_p)]


def find_library(eric_dir):
    """Return (library file, plugin dir) for an ERiC directory.

    Linux download: <dir>/lib/libericapi.so with lib/plugins.
    Windows / WISO: <dir>/ericapi.dll with plugins next to it.
    """
    for libdir in (os.path.join(eric_dir, "lib"), eric_dir):
        name = "ericapi.dll" if WINDOWS else "libericapi.so"
        path = os.path.join(libdir, name)
        if os.path.exists(path):
            return path, libdir
    raise FileNotFoundError(f"no ERiC library in {eric_dir}")


class Eric:
    """Singlethread ERiC API; every call is serialised through one lock."""

    def __init__(self, eric_dir, log_dir=None):
        libfile, libdir = find_library(eric_dir)
        if WINDOWS:
            os.add_dll_directory(libdir)
        else:
            # load the helper libs globally so libericapi finds them without LD_LIBRARY_PATH
            for name in sorted(os.listdir(libdir)):
                if name.endswith(".so") and name != "libericapi.so":
                    try:
                        ctypes.CDLL(os.path.join(libdir, name), mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass
        self.lib = lib = ctypes.CDLL(libfile)
        self.lock = threading.Lock()
        vp, cp, u32, i = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_int
        lib.EricInitialisiere.argtypes = [cp, cp]
        lib.EricRueckgabepufferErzeugen.restype = vp
        lib.EricRueckgabepufferInhalt.argtypes = [vp]
        lib.EricRueckgabepufferInhalt.restype = cp
        lib.EricRueckgabepufferFreigeben.argtypes = [vp]
        lib.EricHoleFehlerText.argtypes = [i, vp]
        lib.EricVersion.argtypes = [vp]
        lib.EricBearbeiteVorgang.argtypes = [cp, cp, u32, vp,
                                             ctypes.POINTER(CryptParams), vp, vp]
        lib.EricGetHandleToCertificate.argtypes = [ctypes.POINTER(u32),
                                                   ctypes.POINTER(u32), cp]
        lib.EricCloseHandleToCertificate.argtypes = [u32]
        lib.EricCreateTH.argtypes = [cp, cp, cp, cp, cp, cp, cp, cp, cp, vp]
        lib.EricMakeElsterStnr.argtypes = [cp, cp, cp, vp]
        lib.EricHoleFinanzaemter.argtypes = [cp, vp]
        lib.EricCheckXML.argtypes = [cp, cp, vp]
        lib.EricGetAuswahlListen.argtypes = [cp, cp, vp]
        log_dir = log_dir or os.environ.get("ERIC_LOG_DIR") or os.path.join(
            os.path.expanduser("~"), ".cache", "eric")
        os.makedirs(log_dir, exist_ok=True)
        rc = lib.EricInitialisiere(libdir.encode(), log_dir.encode())
        if rc != ERIC_OK:
            raise RuntimeError(f"EricInitialisiere failed: {rc}")

    def _buf(self):
        return self.lib.EricRueckgabepufferErzeugen()

    def _text(self, buf):
        raw = self.lib.EricRueckgabepufferInhalt(buf) or b""
        return raw.decode("utf-8", "replace")

    def _free(self, *bufs):
        for b in bufs:
            self.lib.EricRueckgabepufferFreigeben(b)

    def error_text(self, rc):
        b = self._buf()
        try:
            self.lib.EricHoleFehlerText(rc, b)
            return self._text(b)
        finally:
            self._free(b)

    def version(self):
        with self.lock:
            b = self._buf()
            try:
                rc = self.lib.EricVersion(b)
                return rc, self._text(b)
            finally:
                self._free(b)

    def _call_buf(self, fn, *args):
        """Call an ERiC function whose last argument is a return buffer."""
        with self.lock:
            b = self._buf()
            try:
                rc = fn(*args, b)
                out = self._text(b)
                if rc != ERIC_OK and not out:
                    out = self.error_text(rc)
                return rc, out
            finally:
                self._free(b)

    def create_th(self, xml, datenart="ESt", verfahren="ElsterErklaerung", vorgang="send-Auth",
                  testmerker="700000004", hersteller_id=None,
                  daten_lieferant="Softwaretester ERiC", version_client="1"):
        """Let ERiC wrap <DatenTeil> with a <TransferHeader> (returns the full XML)."""
        hersteller_id = hersteller_id or HERSTELLER_ID
        enc = [v.encode() for v in (xml, verfahren, datenart, vorgang, testmerker,
                                    hersteller_id, daten_lieferant, version_client)]
        return self._call_buf(self.lib.EricCreateTH, *enc, None)

    def make_elster_stnr(self, stnr, land, bufa):
        """Tax number as printed on the notice -> 13 digit ELSTER format."""
        return self._call_buf(self.lib.EricMakeElsterStnr, stnr.encode(), land.encode(),
                              bufa.encode())

    def tax_offices(self, land):
        return self._call_buf(self.lib.EricHoleFinanzaemter, land.encode())

    def choice_list(self, datenart, field):
        """Allowed values of an enumerated field (e.g. religion codes)."""
        return self._call_buf(self.lib.EricGetAuswahlListen, datenart.encode(), field.encode())

    def check_xml(self, xml, datenart):
        """Schema check only (no transfer header / manufacturer id check)."""
        return self._call_buf(self.lib.EricCheckXML, xml.encode("utf-8"), datenart.encode())

    def process(self, xml, datenart, send=False, cert=None, pin=None):
        flags = ERIC_VALIDIERE | ERIC_PRUEFE_HINWEISE | (ERIC_SENDE if send else 0)
        with self.lock:
            ret, srv = self._buf(), self._buf()
            handle = ctypes.c_uint32(0)
            crypt = None
            try:
                if send:
                    pin_support = ctypes.c_uint32(0)
                    rc = self.lib.EricGetHandleToCertificate(
                        ctypes.byref(handle), ctypes.byref(pin_support), cert.encode())
                    if rc != ERIC_OK:
                        return rc, self.error_text(rc), ""
                    crypt = CryptParams(int(os.environ.get("ERIC_CRYPT_VER", "3")),
                                        handle.value, pin.encode())
                rc = self.lib.EricBearbeiteVorgang(
                    xml.encode("utf-8"), datenart.encode(), flags, None,
                    ctypes.byref(crypt) if crypt else None, ret, srv)
                out = self._text(ret)
                if rc != ERIC_OK and not out:
                    out = self.error_text(rc)
                return rc, out, self._text(srv)
            finally:
                if handle.value:
                    self.lib.EricCloseHandleToCertificate(handle.value)
                self._free(ret, srv)


def _wine_path(path):
    return "Z:" + os.path.abspath(path).replace("/", "\\")


class WineEric:
    """Same interface as Eric, but runs the Windows ericapi.dll through Wine.

    Validation only: one Wine process per call (ERiC init takes a few seconds).
    """

    def __init__(self, eric_dir, python_exe, prefix=None, timeout=120):
        self.eric_dir, self.python_exe, self.timeout = eric_dir, python_exe, timeout
        self.env = dict(os.environ, WINEPREFIX=prefix or os.path.expanduser("~/.wine-eric"),
                        WINEDEBUG="-all")
        self.lock = threading.Lock()
        rc, _ = self.version()
        if rc != ERIC_OK:
            raise RuntimeError(f"ERiC under Wine not usable: rc={rc}")

    def _run(self, *args):
        cmd = ["wine", self.python_exe, _wine_path(__file__), _wine_path(self.eric_dir), *args]
        with self.lock:
            p = subprocess.run(cmd, env=self.env, stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=self.timeout)
        try:
            return json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1])
        except (IndexError, ValueError):
            raise RuntimeError(f"wine bridge failed: {p.stderr.decode(errors='replace')[-500:]}")

    def batch(self, calls):
        """Run several Eric method calls in one Wine process.

        calls: [[method, *args], ...]; returns a list of results (lists).
        """
        if any(c[0] == "process" and len(c) > 3 and c[3] for c in calls):
            raise RuntimeError("sending is not supported through the Wine bridge")
        tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"eric_{os.getpid()}.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(calls, f)
        try:
            return self._run("batch", _wine_path(tmp))["results"]
        finally:
            os.unlink(tmp)

    def version(self):
        r = self._run("version")
        return r["rc"], r["result"]

    def process(self, xml, datenart, send=False, cert=None, pin=None):
        if send:
            raise RuntimeError("sending is not supported through the Wine bridge")
        return tuple(self.batch([["process", xml, datenart]])[0])

    def create_th(self, xml, **kw):
        return tuple(self.batch([["create_th", xml, kw]])[0])

    def make_elster_stnr(self, stnr, land, bufa):
        return tuple(self.batch([["make_elster_stnr", stnr, land, bufa]])[0])

    def tax_offices(self, land):
        return tuple(self.batch([["tax_offices", land]])[0])

    def check_xml(self, xml, datenart):
        return tuple(self.batch([["check_xml", xml, datenart]])[0])


def _bridge(argv):
    eric_dir, action = argv[0], argv[1]
    e = Eric(eric_dir)
    if action == "version":
        rc, out = e.version()
        srv = ""
    elif action == "batch":
        with open(argv[2], encoding="utf-8") as f:
            calls = json.load(f)
        results = []
        for name, *args in calls:
            kw = args.pop() if args and isinstance(args[-1], dict) else {}
            if name not in ("process", "create_th", "make_elster_stnr", "tax_offices", "version", "check_xml", "choice_list"):
                raise SystemExit(f"method not allowed: {name}")
            results.append(list(getattr(e, name)(*args, **kw)))
        sys.stdout.write(json.dumps({"rc": 0, "results": results}) + "\n")
        return
    elif action == "validate":
        with open(argv[2], encoding="utf-8") as f:
            rc, out, srv = e.process(f.read(), argv[3])
    else:
        raise SystemExit(f"unknown action {action}")
    sys.stdout.write(json.dumps({"rc": rc, "result": out, "server": srv}) + "\n")


if __name__ == "__main__":
    _bridge(sys.argv[1:])
