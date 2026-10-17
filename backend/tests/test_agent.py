"""LLM sentence checker and LLM config, with fixed inputs and no network."""

from kaagaz import agent

RESULT = {
    "outcome": "answered_with_path",
    "message": "Post-matric OBC: 7 days short of the deadline.",
    "data": {"scheme": {"name": "PostMatric for OBC Students"}, "verdict": {"critical_days": 21, "margin": 7},
             "deadline": {"date": "2026-10-31"},
             "items": [{"name": "Caste and income certificate (Karnataka)", "days": 21}]},
}
NAMES = ["PostMatric for OBC Students", "Caste and income certificate (Karnataka)", "PAN card", "Aadhaar"]


def test_sentence_with_only_result_facts_passes():
    s = "You need the Caste and income certificate (Karnataka), which takes 21 days, so you are 7 days short."
    assert agent.check_sentence(s, RESULT, NAMES) == {"ok": True, "problems": []}


def test_dates_in_result_allow_their_numbers():
    s = "The deadline is 31 Oct 2026."
    assert agent.check_sentence(s, RESULT, NAMES)["ok"]


def test_invented_number_fails():
    r = agent.check_sentence("You are 12 days short.", RESULT, NAMES)
    assert not r["ok"] and "12" in r["problems"][0]


def test_invented_document_name_fails():
    r = agent.check_sentence("You also need a PAN card.", RESULT, NAMES)
    assert not r["ok"] and "PAN card" in r["problems"][0]


def test_em_dash_fails():
    assert not agent.check_sentence("You are 7 days short — apply today.", RESULT, NAMES)["ok"]


def test_empty_fails():
    assert not agent.check_sentence("  ", RESULT, NAMES)["ok"]


def test_llm_not_configured_without_env(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert agent.llm_configured() is False
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    assert agent.llm_configured() is False  # no key
    monkeypatch.setenv("LLM_API_KEY", "k")
    assert agent.llm_configured() is True
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    assert agent.llm_configured() is True  # local server without a key


def test_words_drop_stopwords():
    assert agent._words("Does Vidyasiri need a PAN card?") == ["vidyasiri", "pan", "card"]
