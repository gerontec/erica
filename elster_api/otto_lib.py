#!/usr/bin/env python3
"""ctypes binding for Otto (libotto.so, part of ERiC), stdlib only.

Otto uploads large attachments (e.g. receipts for a Belegnachreichung) to the
ELSTER OTTER server and returns an object id that the ERiC XML references
(Anhang/DateiReferenzId). It also downloads objects by id. Signatures follow
otto.h / otto_types.h of ERiC 44.3; the flow follows the shipped ottodemo:

  checksum over all data -> sign with certificate -> start upload with the
  signed checksum -> send blocks -> finish -> object id

  python3 otto_lib.py <eric_dir> version
  python3 otto_lib.py <eric_dir> checksum <file>          # local, signs only
  python3 otto_lib.py <eric_dir> upload <file>            # needs ERIC_ALLOW_SEND=1
  python3 otto_lib.py <eric_dir> download <objekt_id> <size> <out_file>

Certificate and PIN come from ERIC_CERT / ERIC_PIN, the manufacturer id from
ERIC_HERSTELLER_ID.
"""
import ctypes
import json
import os
import sys
import threading

OTTO_OK = 0
BLOCK = 1 << 20  # 1 MiB, as in ottodemo

HERSTELLER_ID = os.environ.get("ERIC_HERSTELLER_ID", "74931")


class OttoError(RuntimeError):
    def __init__(self, func, rc, text):
        super().__init__(f"{func} rc={rc}: {text}")
        self.rc = rc


def find_library(eric_dir):
    for libdir in (os.path.join(eric_dir, "lib"), eric_dir):
        path = os.path.join(libdir, "otto.dll" if os.name == "nt" else "libotto.so")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"no Otto library in {eric_dir}")


class Otto:
    """One Otto instance; calls are serialised (an instance is not thread safe)."""

    def __init__(self, eric_dir, log_dir=None):
        self.lib = lib = ctypes.CDLL(find_library(eric_dir))
        self.lock = threading.Lock()
        vp, cp, u32, u64, i = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32,
                               ctypes.c_uint64, ctypes.c_int)
        pvp = ctypes.POINTER(vp)
        for name, args in {
            "OttoInstanzErzeugen": [cp, vp, vp, pvp],
            "OttoInstanzFreigeben": [vp],
            "OttoZertifikatOeffnen": [vp, cp, cp, pvp],
            "OttoZertifikatSchliessen": [vp],
            "OttoRueckgabepufferErzeugen": [vp, pvp],
            "OttoRueckgabepufferFreigeben": [vp],
            "OttoPruefsummeErzeugen": [vp, pvp],
            "OttoPruefsummeAktualisieren": [vp, cp, u64],
            "OttoPruefsummeSignieren": [vp, vp, vp],
            "OttoPruefsummeFreigeben": [vp],
            "OttoVersandBeginnen": [vp, cp, cp, pvp],
            "OttoVersandFortsetzen": [vp, cp, u64],
            "OttoVersandAbschliessen": [vp, vp],
            "OttoVersandBeenden": [vp],
            "OttoDatenAbholen": [vp, cp, u32, cp, cp, cp, cp, vp],
            "OttoVersion": [vp],
        }.items():
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, i
        lib.OttoRueckgabepufferInhalt.argtypes = [vp]
        lib.OttoRueckgabepufferInhalt.restype = ctypes.POINTER(ctypes.c_char)
        lib.OttoRueckgabepufferGroesse.argtypes = [vp]
        lib.OttoRueckgabepufferGroesse.restype = u64
        lib.OttoHoleFehlertext.argtypes = [i]
        lib.OttoHoleFehlertext.restype = cp
        log_dir = log_dir or os.environ.get("ERIC_LOG_DIR") or os.path.join(
            os.path.expanduser("~"), ".cache", "eric")
        os.makedirs(log_dir, exist_ok=True)
        self.inst = vp()
        self._check("OttoInstanzErzeugen", lib.OttoInstanzErzeugen(
            log_dir.encode(), None, None, ctypes.byref(self.inst)))

    def close(self):
        if self.inst:
            self.lib.OttoInstanzFreigeben(self.inst)
            self.inst = ctypes.c_void_p()

    def error_text(self, rc):
        return (self.lib.OttoHoleFehlertext(rc) or b"").decode("utf-8", "replace")

    def _check(self, func, rc):
        if rc != OTTO_OK:
            raise OttoError(func, rc, self.error_text(rc))

    def _buf(self):
        b = ctypes.c_void_p()
        self._check("OttoRueckgabepufferErzeugen",
                    self.lib.OttoRueckgabepufferErzeugen(self.inst, ctypes.byref(b)))
        return b

    def _bytes(self, buf):
        n = self.lib.OttoRueckgabepufferGroesse(buf)
        return ctypes.string_at(self.lib.OttoRueckgabepufferInhalt(buf), n) if n else b""

    def version(self):
        with self.lock:
            b = self._buf()
            try:
                self._check("OttoVersion", self.lib.OttoVersion(b))
                return self._bytes(b).decode("utf-8", "replace")
            finally:
                self.lib.OttoRueckgabepufferFreigeben(b)

    def _open_cert(self, cert, pin):
        h = ctypes.c_void_p()
        self._check("OttoZertifikatOeffnen", self.lib.OttoZertifikatOeffnen(
            self.inst, cert.encode(), pin.encode(), ctypes.byref(h)))
        return h

    @staticmethod
    def _blocks(path):
        with open(path, "rb") as f:
            while True:
                block = f.read(BLOCK)
                if not block:
                    return
                yield block

    def _signed_checksum(self, path, cert_handle):
        """Checksum over the whole file, signed with the certificate."""
        ck, b = ctypes.c_void_p(), self._buf()
        try:
            self._check("OttoPruefsummeErzeugen",
                        self.lib.OttoPruefsummeErzeugen(self.inst, ctypes.byref(ck)))
            for block in self._blocks(path):
                self._check("OttoPruefsummeAktualisieren",
                            self.lib.OttoPruefsummeAktualisieren(ck, block, len(block)))
            self._check("OttoPruefsummeSignieren",
                        self.lib.OttoPruefsummeSignieren(ck, cert_handle, b))
            return self._bytes(b)
        finally:
            if ck:
                self.lib.OttoPruefsummeFreigeben(ck)
            self.lib.OttoRueckgabepufferFreigeben(b)

    def checksum(self, path, cert, pin):
        """Only build and sign the checksum (no network); tests certificate + PIN."""
        with self.lock:
            h = self._open_cert(cert, pin)
            try:
                return self._signed_checksum(path, h).decode("utf-8", "replace")
            finally:
                self.lib.OttoZertifikatSchliessen(h)

    def upload(self, path, cert, pin, hersteller_id=None):
        """Upload a file to OTTER, return the object id for Anhang/DateiReferenzId."""
        hersteller_id = (hersteller_id or HERSTELLER_ID).encode()
        with self.lock:
            h = self._open_cert(cert, pin)
            send, b = ctypes.c_void_p(), None
            try:
                signed = self._signed_checksum(path, h)
                self._check("OttoVersandBeginnen", self.lib.OttoVersandBeginnen(
                    self.inst, signed, hersteller_id, ctypes.byref(send)))
                for block in self._blocks(path):
                    self._check("OttoVersandFortsetzen",
                                self.lib.OttoVersandFortsetzen(send, block, len(block)))
                b = self._buf()
                self._check("OttoVersandAbschliessen", self.lib.OttoVersandAbschliessen(send, b))
                return self._bytes(b).decode("utf-8", "replace")
            finally:
                if send:
                    self.lib.OttoVersandBeenden(send)
                if b:
                    self.lib.OttoRueckgabepufferFreigeben(b)
                self.lib.OttoZertifikatSchliessen(h)

    def download(self, objekt_id, size, cert, pin, hersteller_id=None, abholzertifikat=None):
        """Fetch an object from OTTER by id (size in bytes as given by ELSTER)."""
        hersteller_id = (hersteller_id or HERSTELLER_ID).encode()
        with self.lock:
            b = self._buf()
            try:
                self._check("OttoDatenAbholen", self.lib.OttoDatenAbholen(
                    self.inst, objekt_id.encode(), size, cert.encode(), pin.encode(),
                    hersteller_id, abholzertifikat.encode() if abholzertifikat else None, b))
                return self._bytes(b)
            finally:
                self.lib.OttoRueckgabepufferFreigeben(b)


def _cert():
    cert, pin = os.environ.get("ERIC_CERT"), os.environ.get("ERIC_PIN")
    if not (cert and pin):
        raise SystemExit("ERIC_CERT and ERIC_PIN required")
    return cert, pin


def _main(argv):
    otto = Otto(argv[0])
    try:
        action = argv[1]
        if action == "version":
            print(otto.version())
        elif action == "checksum":
            print(otto.checksum(argv[2], *_cert()))
        elif action == "upload":
            if os.environ.get("ERIC_ALLOW_SEND") != "1":
                raise SystemExit("upload disabled (set ERIC_ALLOW_SEND=1)")
            print(json.dumps({"objekt_id": otto.upload(argv[2], *_cert())}))
        elif action == "download":
            data = otto.download(argv[2], int(argv[3]), *_cert())
            with open(argv[4], "wb") as f:
                f.write(data)
            print("written", argv[4], len(data), "bytes")
        else:
            raise SystemExit(f"unknown action {action}")
    finally:
        otto.close()


if __name__ == "__main__":
    _main(sys.argv[1:])
