"""Tool argument validation (no database needed: validation fails before any query)."""

import pytest

from kaagaz.tools import ARG_MODELS, ToolError, Tools, catalogue


@pytest.fixture
def tools():
    return Tools("in-ka-scholarships")


@pytest.mark.parametrize("name,args", [
    ("prerequisites", {"scheme_id": "ka-ssp-pms-obc", "depth": 0}),
    ("prerequisites", {"scheme_id": "ka-ssp-pms-obc", "depth": 9}),
    ("prerequisites", {"scheme_id": "ka-ssp-pms-obc", "depth": "deep"}),
    ("prerequisites", {"scheme_id": "x' OR 1=1 //"}),
    ("plan", {"student_id": "AB", "scheme_id": "ka-ssp-pms-obc"}),
    ("plan", {"student_id": "kaagaz:rules:x", "scheme_id": "ka-ssp-pms-obc"}),
    ("explain", {"scheme_id": "ka-ssp-pms-obc"}),
    ("remember_holding", {"student_id": "student-1", "doc_id": "aadhaar", "issued_on": "2999-01-01"}),
    ("remember_holding", {"student_id": "student-1", "doc_id": "aadhaar", "issued_on": "not a date"}),
    ("resolve", {"name": ""}),
    ("resolve", {"name": "x" * 201}),
])
def test_bad_arguments_are_rejected_before_any_query(tools, name, args):
    with pytest.raises(ToolError):
        tools.call(name, args)


def test_unknown_tool_is_rejected(tools):
    with pytest.raises(ToolError):
        tools.call("run_cypher", {"query": "MATCH (n) RETURN n"})


def test_catalogue_is_exactly_the_seven_tools():
    names = [t["name"] for t in catalogue()]
    assert names == ["resolve", "prerequisites", "plan", "explain", "alternatives", "remember_holding", "recall"]
    assert set(names) == set(ARG_MODELS)
    for t in catalogue():
        assert t["parameters"]["type"] == "object"
