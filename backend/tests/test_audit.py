"""The data audit must pass on the real data and fail on broken data."""

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def run_audit(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "scripts" / "audit_data.py")], capture_output=True, text=True)


def copy_repo(tmp: Path) -> Path:
    dst = tmp / "repo"
    (dst / "scripts").mkdir(parents=True)
    for f in ("audit_data.py", "textnorm.py"):
        shutil.copy(ROOT / "scripts" / f, dst / "scripts" / f)
    shutil.copytree(ROOT / "data" / "packs", dst / "data" / "packs")
    shutil.copytree(ROOT / "data" / "sources", dst / "data" / "sources")
    return dst


def test_audit_passes_on_real_data():
    r = run_audit(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "audit: OK" in r.stdout


def _mutate(tmp_path, fn):
    repo = copy_repo(tmp_path)
    p = next((repo / "data" / "packs").glob("*/pack.yaml"))
    pack = yaml.safe_load(p.read_text())
    fn(pack)
    p.write_text(yaml.safe_dump(pack, sort_keys=False, allow_unicode=True))
    return run_audit(repo)


def test_audit_fails_on_excerpt_not_in_source(tmp_path):
    def f(pack):
        pack["rules"][0]["cite"]["excerpt"] = "this sentence was never in any government source"
    r = _mutate(tmp_path, f)
    assert r.returncode == 1 and "excerpt not found" in r.stdout


def test_audit_fails_on_missing_field(tmp_path):
    def f(pack):
        del pack["rules"][0]["cite"]["retrieved_at"]
    r = _mutate(tmp_path, f)
    assert r.returncode == 1 and "missing retrieved_at" in r.stdout


def test_audit_fails_on_unindexed_url(tmp_path):
    def f(pack):
        pack["rules"][0]["cite"]["source_url"] = "https://example.org/not-saved"
    r = _mutate(tmp_path, f)
    assert r.returncode == 1 and "not in index" in r.stdout


def test_audit_fails_on_days_without_source(tmp_path):
    def f(pack):
        d = next(d for d in pack["documents"] if d.get("days") is None)
        d["days"] = 5
    r = _mutate(tmp_path, f)
    assert r.returncode == 1 and "/days: missing source" in r.stdout


def test_audit_fails_on_long_excerpt(tmp_path):
    def f(pack):
        pack["rules"][0]["cite"]["excerpt"] = " ".join(["word"] * 26)
    r = _mutate(tmp_path, f)
    assert r.returncode == 1 and "max 25" in r.stdout


def test_audit_fails_on_tampered_source_file(tmp_path):
    repo = copy_repo(tmp_path)
    raw = next(p for p in (repo / "data" / "sources" / "raw").iterdir() if p.suffix in (".html", ".pdf"))
    raw.write_bytes(raw.read_bytes() + b"tampered")
    r = run_audit(repo)
    assert r.returncode == 1 and "sha256 does not match" in r.stdout
