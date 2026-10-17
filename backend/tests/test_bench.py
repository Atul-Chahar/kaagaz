"""Benchmark scoring with fixed inputs (no LLM, no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
import run_bench as rb

DOCS = [{"id": "caste-income-certificate-ka", "name": "Caste and income certificate (Karnataka; Form F)"},
        {"id": "aadhaar", "name": "Aadhaar number (UIDAI)"},
        {"id": "ration-card-ka", "name": "Ration card (Karnataka; new / BPL)"},
        {"id": "voter-id", "name": "Voter ID card"}]


def test_match_names_maps_free_text_to_ids_and_flags_unknowns():
    ids, un = rb.match_names(["Caste & Income Certificate", "Aadhaar card", "passport size photo"], DOCS)
    assert ids == ["caste-income-certificate-ka", "aadhaar"]
    assert un == ["passport size photo"]


def test_score_list_counts_any_of_once_and_invented():
    truth = {"required": ["aadhaar", "caste-income-certificate-ka"], "any_of": [["ration-card-ka", "voter-id"]]}
    assert rb.score_list({"aadhaar", "voter-id"}, 0, truth) == (2 / 3, 0)
    r, inv = rb.score_list({"aadhaar", "caste-income-certificate-ka", "ration-card-ka", "x"}, 2, truth)
    assert r == 1.0 and inv == 3


def test_score_aggregates_by_type():
    qs = [{"type": "list_documents", "truth": {"required": ["aadhaar"]}},
          {"type": "first_step", "truth": {"first_step": "aadhaar", "acceptable": ["voter-id"]}},
          {"type": "deadline", "truth": {"verdict": "no"}},
          {"type": "deadline", "truth": {"verdict": "yes"}}]
    ans = [{"doc_ids": ["aadhaar"]}, {"first_step": "voter-id"}, {"verdict": "no"}, {"verdict": "cannot_tell"}]
    s = rb.score("x", ans, qs)
    assert s["document_recall"] == 1.0 and s["invented_documents"] == 0
    assert s["first_step_accuracy"] == 1.0 and s["verdict_accuracy"] == 0.5
    assert s["n"] == {"list_documents": 1, "first_step": 1, "deadline": 2}


def test_parse_json_and_to_answer():
    raw = rb.parse_json('Sure. {"documents": [], "first_step": null, "verdict": "Cannot tell"}')
    assert rb.to_answer({"type": "deadline"}, raw, DOCS) == {"verdict": "cannot_tell"}
    assert rb.parse_json("no json here") == {}


def test_llm_benchmark_refuses_to_run_without_a_key(monkeypatch, capsys):
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    before = set((rb.BENCH / "results").glob("*.json")) if (rb.BENCH / "results").exists() else set()
    monkeypatch.setattr(sys, "argv", ["run_bench.py"])
    assert rb.main() == 2
    assert "Benchmark not run" in capsys.readouterr().out
    after = set((rb.BENCH / "results").glob("*.json"))
    assert after == before
