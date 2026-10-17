"""Fetch one source politely and record it in data/sources/index.json.

Usage (from repo root):
    backend/.venv/bin/python scripts/fetch_source.py URL --title "Official page title" [--id my-id]

Rules this script enforces (spec section 4):
- respects robots.txt for the host
- at most 1 request per second per host (shared across processes through a lock file)
- caches: a URL already in the index is not fetched again unless --refresh is given
- saves the raw bytes in data/sources/raw/ and the extracted text in data/sources/text/
- records url, title, retrieved_at, sha256, file, text_file, size in index.json
- files over 5 MB are listed in data/sources/raw/.large (added to .gitignore by the caller)

It prints the source id and the path of the text file so the caller can grep excerpts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources"
RAW = SRC / "raw"
TEXT = SRC / "text"
INDEX = SRC / "index.json"
LOCK = SRC / ".fetch.lock"
RATE = SRC / ".rate.json"
UA = "KaagazResearchBot/0.1 (hackathon research; polite, cached; contact via github.com/Atul-Chahar/kaagaz)"
LARGE = 5 * 1024 * 1024


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "source"


def load_index() -> list[dict]:
    if INDEX.exists():
        return json.loads(INDEX.read_text())
    return []


def save_index(rows: list[dict]) -> None:
    rows.sort(key=lambda r: r["id"])
    INDEX.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


def robots_ok(url: str, client: httpx.Client) -> bool:
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = client.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=20)
    except httpx.HTTPError:
        return True  # no robots.txt reachable: allowed by convention
    if r.status_code >= 400:
        return True
    rp.parse(r.text.splitlines())
    return rp.can_fetch(UA, url)


def wait_rate(host: str) -> None:
    """Block until at least 1.1 s has passed since the last request to this host."""
    data = json.loads(RATE.read_text()) if RATE.exists() else {}
    last = data.get(host, 0)
    gap = time.time() - last
    if gap < 1.1:
        time.sleep(1.1 - gap)
    data[host] = time.time()
    RATE.write_text(json.dumps(data))


def html_to_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def pdf_to_text(path: Path) -> str:
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=False)
    return out.stdout.decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--title", required=True)
    ap.add_argument("--id")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (some gov sites have broken chains)")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    LOCK.touch()
    with LOCK.open("w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        rows = load_index()
        existing = next((r for r in rows if r["url"] == args.url), None)
        if existing and not args.refresh:
            print(f"CACHED {existing['id']} {SRC / existing['text_file']}")
            return 0

        host = urlparse(args.url).netloc
        with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, verify=not args.insecure,
                          timeout=60) as client:
            wait_rate(host)
            if not robots_ok(args.url, client):
                print(f"ROBOTS_DISALLOWED {args.url}", file=sys.stderr)
                return 3
            wait_rate(host)
            try:
                resp = client.get(args.url)
            except httpx.HTTPError as e:
                print(f"FETCH_ERROR {args.url} {e!r}", file=sys.stderr)
                return 4
        if resp.status_code >= 400:
            print(f"HTTP_{resp.status_code} {args.url}", file=sys.stderr)
            return 5

        body = resp.content
        sha = hashlib.sha256(body).hexdigest()
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        is_pdf = ctype == "application/pdf" or body[:5] == b"%PDF-"
        ext = "pdf" if is_pdf else "html"
        sid = args.id or (existing["id"] if existing else f"{slug(host)}-{slug(args.title)}")
        raw_name = f"{sid}.{ext}"
        raw_path = RAW / raw_name
        raw_path.write_bytes(body)
        text = pdf_to_text(raw_path) if is_pdf else html_to_text(body)
        text_name = f"{sid}.txt"
        (TEXT / text_name).write_text(text)
        large = len(body) > LARGE
        if large:
            with (RAW / ".large").open("a") as f:
                f.write(raw_name + "\n")
            gi = ROOT / ".gitignore"
            line = f"data/sources/raw/{raw_name}"
            if line not in gi.read_text().splitlines():
                with gi.open("a") as f:
                    f.write(line + "\n")

        row = {
            "id": sid,
            "url": args.url,
            "final_url": str(resp.url),
            "title": args.title,
            "retrieved_at": dt.date.today().isoformat(),
            "sha256": sha,
            "file": f"raw/{raw_name}",
            "text_file": f"text/{text_name}",
            "content_type": "application/pdf" if is_pdf else (ctype or "text/html"),
            "size": len(body),
            "large_not_in_git": large,
            "text_chars": len(text),
        }
        rows = [r for r in rows if r["id"] != sid and r["url"] != args.url] + [row]
        save_index(rows)
        print(f"SAVED {sid} {TEXT / text_name} chars={len(text)} sha256={sha[:12]}")
        if len(text.strip()) < 200:
            print("WARNING: very little text extracted (scanned PDF or JS page?)", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
