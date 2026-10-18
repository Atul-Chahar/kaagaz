"""Saved government sources (data/sources) and polite re-fetching for the watcher agent.

Fetching follows the same rules as scripts/fetch_source.py: robots.txt is respected, at most one request per
second per host (shared with that script through data/sources/.rate.json), and the same user agent.
A re-fetched copy is never written over the saved source; it goes to data/sources/checks/<run-id>/.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .graph import ROOT

SRC = ROOT / "data" / "sources"
INDEX = SRC / "index.json"
CHECKS = SRC / "checks"
RATE = SRC / ".rate.json"
LOCK = SRC / ".fetch.lock"
UA = "KaagazResearchBot/0.1 (hackathon research; polite, cached; contact via github.com/Atul-Chahar/kaagaz)"
LARGE = 5 * 1024 * 1024


def load_index() -> list[dict]:
    return json.loads(INDEX.read_text()) if INDEX.exists() else []


def save_index(rows: list[dict]) -> None:
    LOCK.touch()
    with LOCK.open("w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        rows = sorted(rows, key=lambda r: r["id"])
        INDEX.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


def saved_text(row: dict) -> str | None:
    p = SRC / row["text_file"]
    return p.read_text() if p.exists() else None


def html_to_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\n\s*\n+", "\n\n", soup.get_text("\n")).strip()


def pdf_to_text(path: Path) -> str | None:
    if shutil.which("pdftotext") is None:
        return None
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=False)
    return out.stdout.decode("utf-8", "replace")


@dataclass
class Fetched:
    status: str                 # ok | unreachable | http_error | robots_disallowed | no_text
    http: int | None = None
    sha256: str | None = None
    raw_path: Path | None = None
    text_path: Path | None = None
    text: str | None = None
    content_type: str | None = None
    size: int | None = None
    tls_verified: bool = True
    error: str | None = None


class Fetcher:
    """One polite HTTP client for a whole watcher run (robots.txt read once per host)."""

    def __init__(self, timeout: float = 45):
        self.client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=timeout)
        self.insecure = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=timeout,
                                     verify=False)
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def close(self) -> None:
        self.client.close()
        self.insecure.close()

    def _wait(self, host: str) -> None:
        LOCK.touch()
        with LOCK.open("w") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            data = json.loads(RATE.read_text()) if RATE.exists() else {}
            gap = time.time() - data.get(host, 0)
            if gap < 1.1:
                time.sleep(1.1 - gap)
            data[host] = time.time()
            RATE.write_text(json.dumps(data))

    def _get(self, url: str) -> tuple[httpx.Response, bool]:
        self._wait(urlparse(url).netloc)
        try:
            return self.client.get(url), True
        except httpx.ConnectError as e:
            # some government sites serve broken certificate chains; read-only public pages are fetched anyway
            # and the check records that TLS was not verified
            if "CERTIFICATE" not in str(e).upper() and "SSL" not in str(e).upper():
                raise
            self._wait(urlparse(url).netloc)
            return self.insecure.get(url), False

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        if p.netloc not in self.robots:
            rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                r, _ = self._get(f"{p.scheme}://{p.netloc}/robots.txt")
                if r.status_code >= 400:
                    rp = None
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None  # no robots.txt reachable: allowed by convention
            self.robots[p.netloc] = rp
        rp = self.robots[p.netloc]
        return True if rp is None else rp.can_fetch(UA, url)

    def fetch(self, url: str, dest: Path, name: str) -> Fetched:
        try:
            if not self.allowed(url):
                return Fetched("robots_disallowed")
            resp, verified = self._get(url)
        except httpx.HTTPError as e:
            return Fetched("unreachable", error=type(e).__name__)
        if resp.status_code >= 400:
            return Fetched("http_error", http=resp.status_code, tls_verified=verified)
        body = resp.content
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        is_pdf = ctype == "application/pdf" or body[:5] == b"%PDF-"
        dest.mkdir(parents=True, exist_ok=True)
        raw_path = dest / f"{name}.{'pdf' if is_pdf else 'html'}"
        raw_path.write_bytes(body)
        text = pdf_to_text(raw_path) if is_pdf else html_to_text(body)
        if text is None:
            return Fetched("no_text", http=resp.status_code, sha256=hashlib.sha256(body).hexdigest(),
                           raw_path=raw_path, size=len(body), tls_verified=verified,
                           error="pdftotext is not installed")
        text_path = dest / f"{name}.txt"
        text_path.write_text(text)
        return Fetched("ok", http=resp.status_code, sha256=hashlib.sha256(body).hexdigest(), raw_path=raw_path,
                       text_path=text_path, text=text, content_type="application/pdf" if is_pdf else ctype,
                       size=len(body), tls_verified=verified)
