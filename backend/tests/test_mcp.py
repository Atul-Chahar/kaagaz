"""The MCP server exposes exactly the tool catalogue and runs it against the real graph."""

import json

import anyio
import pytest
from mcp.client.client import Client

from kaagaz import graph, memory
from kaagaz.mcp_server import AGENT_TOOLS, server
from kaagaz.tools import ARG_MODELS

pytestmark = pytest.mark.integration


def test_mcp_lists_the_catalogue_and_calls_tools():
    graph.seed_pack("in-ka-scholarships")
    sid = "test-mcp-student"
    memory.reset(sid)

    async def go():
        async with Client(server) as c:
            tools = await c.list_tools()
            names = sorted(t.name for t in tools.tools)
            assert names == sorted([*ARG_MODELS, *AGENT_TOOLS])
            r = await c.call_tool("explain", {"scheme_id": "ka-ssp-pms-obc", "doc_id": "caste-income-certificate-ka"})
            body = json.loads(r.content[0].text)
            assert body["outcome"] in ("answered_with_path", "no_official_time")
            r = await c.call_tool("plan", {"student_id": sid, "scheme_id": "no-such-scheme"})
            assert json.loads(r.content[0].text)["outcome"] == "unknown_name"
            r = await c.call_tool("remember_holding", {"student_id": sid, "doc_id": "aadhaar"})
            assert json.loads(r.content[0].text)["outcome"] == "answered_from_memory"
            memory.set_target(sid, "ka-ssp-pms-obc", None, "published_window", pack="in-ka-scholarships")
            r = await c.call_tool("review_case", {"student_id": sid})
            case = json.loads(r.content[0].text)
            assert [s["tool"] for s in case["steps"]][:2] == ["recall", "plan"] and case["decision"]["text"]
            r = await c.call_tool("watcher_findings", {})
            assert "findings" in json.loads(r.content[0].text)

    try:
        anyio.run(go)
    finally:
        memory.reset(sid)
