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


def test_direction_of_the_verdict_is_checked():
    late = {"data": {"verdict": {"kind": "late", "margin": 7, "critical_days": 21}}}
    assert not agent.check_sentence("You have 7 days spare.", late, [])["ok"]
    assert agent.check_sentence("You are 7 days short.", late, [])["ok"]


def test_dotenv_loader_never_overrides_what_is_set(tmp_path, monkeypatch):
    import kaagaz
    f = tmp_path / ".env"
    f.write_text("# comment\nKAAGAZ_T1=from-file\nKAAGAZ_T2='quoted'\nKAAGAZ_T3=from-file\n")
    monkeypatch.delenv("KAAGAZ_T1", raising=False)
    monkeypatch.delenv("KAAGAZ_T2", raising=False)
    monkeypatch.setenv("KAAGAZ_T3", "")  # set on purpose (even empty) wins
    kaagaz._load_dotenv(f)
    import os
    assert os.environ["KAAGAZ_T1"] == "from-file" and os.environ["KAAGAZ_T2"] == "quoted"
    assert os.environ["KAAGAZ_T3"] == ""
    for k in ("KAAGAZ_T1", "KAAGAZ_T2"):
        monkeypatch.delenv(k)


def test_thinking_blocks_are_stripped_from_model_text():
    assert agent._strip_thinking("<think>let me see\n...</think>\nYou are 7 days short.") == "You are 7 days short."
    assert agent._strip_thinking("reasoning...</think> On time.") == "On time."
    assert agent._strip_thinking("Plain answer.") == "Plain answer."


def test_openai_requests_leave_room_for_reasoning(monkeypatch):
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    c = {"model": "m"}
    body = agent._openai_body(c, {"max_tokens": 120, "messages": []})
    assert body["max_tokens"] == 120 + agent.REASONING_HEADROOM and body["model"] == "m"
    assert "reasoning_effort" not in body
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    assert agent._openai_body(c, {"max_tokens": 1})["reasoning_effort"] == "low"
    monkeypatch.setenv("LLM_REASONING_EFFORT", "nonsense")
    assert "reasoning_effort" not in agent._openai_body(c, {"max_tokens": 1})


def test_numbers_inside_names_and_date_months_are_facts():
    result = {"outcome": "answered_from_memory", "message": "saved",
              "data": {"doc": {"name": "Caste and income certificate (Form F: other than Category-1)",
                               "added_at": "2026-10-17T10:00:00+00:00"}}}
    ok = agent.check_sentence("You hold a caste and income certificate (Form F, other than Category 1), saved 2026-10-17.",
                              result,
                              [])
    assert ok["ok"], ok
    # a category number that is not in the result is still caught
    bad = agent.check_sentence("You hold the certificate for Category 2.", result, [])
    assert not bad["ok"]
    # a month that is not the result's month is still caught
    assert not agent.check_sentence("It was saved on 2026-11-17.", result, [])["ok"]


def test_a_reply_without_choices_is_an_llm_error(monkeypatch):
    import pytest

    monkeypatch.setattr(agent, "_post", lambda *a, **k: {"error": "busy"})
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "k")
    with pytest.raises(agent.LLMError):
        agent.complete("s", "u")
    with pytest.raises(agent.LLMError):
        agent.choose_tool("q", "c")
