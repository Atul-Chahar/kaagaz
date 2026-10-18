"""Watcher matching rules, without a database or the network."""

import importlib.util
from pathlib import Path

from kaagaz.textnorm import norm
from kaagaz.watcher import best_match, classify, dates_in

ROOT = Path(__file__).resolve().parents[2]


def test_backend_and_audit_normalise_text_the_same_way():
    spec = importlib.util.spec_from_file_location("audit_textnorm", ROOT / "scripts" / "textnorm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for s in ["Last date to apply: 31.10.2026", "“Quoted” – text here", "ಕೊನೆಯ ದಿನಾಂಕ: 31/10/2026"]:
        assert norm(s) == mod.norm(s)


def test_dates_in_reads_the_forms_government_pages_use():
    assert dates_in("Last date to apply: 31.10.2026") == ["2026-10-31"]
    assert dates_in("Open from : 01-06-2026 Student Application Open till : 31-10-2026") == ["2026-06-01",
                                                                                              "2026-10-31"]
    assert dates_in("ಕೊನೆಯ ದಿನಾಂಕ: 30/11/2026") == ["2026-11-30"]
    assert dates_in("closes on 15 November 2026") == ["2026-11-15"]
    assert dates_in("on 2026-12-31 or 31.02.2026") == ["2026-12-31"]  # an impossible date is ignored


PAGE = """Backward Classes Welfare Department
2026-27 Post Matric Scholarship
Applications are invited from eligible students.
Last date to apply: 15.11.2026
Contact the hostel warden for details."""

WINDOW = {"kind": "window", "excerpt": "Last date to apply: 31.10.2026", "value": "2026-10-31"}


def test_a_changed_last_date_is_found_with_the_new_date():
    res = classify(WINDOW, norm(PAGE), PAGE)
    assert res["kind"] == "date_changed" and res["new_value"] == "2026-11-15"
    assert res["new_excerpt"] == "Last date to apply: 15.11.2026"


def test_an_unchanged_sentence_raises_nothing():
    page = PAGE.replace("15.11.2026", "31.10.2026")
    assert classify(WINDOW, norm(page), page) is None


def test_a_reworded_rule_is_wording_changed_and_a_vanished_one_is_missing():
    rule = {"kind": "REQUIRES", "excerpt": "Applications are invited from all eligible students.", "value": None}
    res = classify(rule, norm(PAGE), PAGE)
    assert res["kind"] == "wording_changed" and norm(res["new_excerpt"]) in norm(PAGE)
    gone = {"kind": "REQUIRES", "excerpt": "Income certificate issued by the Tahsildar is mandatory", "value": None}
    assert classify(gone, norm(PAGE), PAGE)["kind"] == "excerpt_missing"


def test_a_changed_number_in_a_rule_is_value_changed():
    rule = {"kind": "days", "excerpt": "The certificate is issued within 21 days of the application.", "value": "21"}
    page = "The certificate is issued within 30 days of the application."
    assert classify(rule, norm(page), page)["kind"] == "value_changed"


def test_best_match_quotes_the_page_with_its_own_case_and_at_most_25_words():
    m = best_match("last date to apply: 31.10.2026", PAGE)
    assert m.excerpt == "Last date to apply: 15.11.2026" and m.score >= 0.8
    long = " ".join(f"w{i}" for i in range(40))
    assert len(best_match(long, long).excerpt.split()) <= 25
