"""The same fixed tool catalogue over MCP (stdio). Add to Claude Code with:

    claude mcp add kaagaz -- uv --directory /path/to/kaagaz/backend run python -m kaagaz.mcp_server

FalkorDB must be running (docker compose up -d falkordb). Every call goes through Tools.call, so arguments are
validated, names are resolved against the graph first, and each result carries its outcome and trace.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import agents, caseworker
from .tools import DEFAULT_PACK, TOOL_DESCRIPTIONS, ToolError, Tools

# Agent tools on top of the catalogue. They read and write only through the same tools and named queries.
AGENT_TOOLS = ("review_case", "watcher_findings")

server = MCPServer(
    name="kaagaz",
    instructions=("Kaagaz plans the chain of documents a student needs for a scholarship, using a FalkorDB graph of "
                  "sourced rules. Resolve names first, then call plan or explain. Never invent documents: if a tool "
                  "says not_in_graph or unknown_name, say so."),
)
_tools: Tools | None = None


def _t() -> Tools:
    global _tools
    if _tools is None:
        _tools = Tools()
    return _tools


def _call(name: str, args: dict) -> dict:
    try:
        res = _t().call(name, {k: v for k, v in args.items() if v is not None})
    except ToolError as e:
        return {"outcome": "unknown_name", "error": str(e)}
    out = res.as_dict()
    data = out["data"]
    if name == "plan" and "verdict" in data:  # keep the MCP payload small: the parts an agent needs
        out["data"] = {k: data[k] for k in ("scheme", "depth", "max_depth", "today", "deadline", "days_left",
                                             "day_unit", "verdict", "critical_path", "needed", "held", "unknown",
                                             "start_today", "hidden_more")}
    return out


@server.tool(description=TOOL_DESCRIPTIONS["resolve"])
def resolve(name: str) -> dict:
    return _call("resolve", {"name": name})


@server.tool(description=TOOL_DESCRIPTIONS["prerequisites"])
def prerequisites(scheme_id: str, depth: int = 8) -> dict:
    return _call("prerequisites", {"scheme_id": scheme_id, "depth": depth})


@server.tool(description=TOOL_DESCRIPTIONS["plan"])
def plan(student_id: str, scheme_id: str, depth: int = 8) -> dict:
    return _call("plan", {"student_id": student_id, "scheme_id": scheme_id, "depth": depth})


@server.tool(description=TOOL_DESCRIPTIONS["explain"])
def explain(scheme_id: str, doc_id: str) -> dict:
    return _call("explain", {"scheme_id": scheme_id, "doc_id": doc_id})


@server.tool(description=TOOL_DESCRIPTIONS["alternatives"])
def alternatives(student_id: str, scheme_id: str) -> dict:
    return _call("alternatives", {"student_id": student_id, "scheme_id": scheme_id})


@server.tool(description=TOOL_DESCRIPTIONS["remember_holding"])
def remember_holding(student_id: str, doc_id: str, issued_on: str | None = None) -> dict:
    return _call("remember_holding", {"student_id": student_id, "doc_id": doc_id, "issued_on": issued_on})


@server.tool(description=TOOL_DESCRIPTIONS["recall"])
def recall(student_id: str) -> dict:
    return _call("recall", {"student_id": student_id})


@server.tool(description=("The caseworker agent reviews a student's case: it calls recall, plan, explain and "
                          "alternatives as needed, decides, and saves proposed actions in the student's graph. "
                          "Proposals are not carried out until the student approves them in the app."))
def review_case(student_id: str, scheme_id: str | None = None) -> dict:
    try:
        r = caseworker.review(_t(), student_id, scheme_id, narrate=False)
    except ToolError as e:
        return {"outcome": "not_in_graph", "error": str(e)}
    return {k: r[k] for k in ("case_id", "scheme", "today", "verdict", "decision", "since", "steps")} | {
        "proposals": [p for p in r["proposals"] if p["status"] == "pending"]}


@server.tool(description=("What the watcher agent found when it last re-checked the government sources: rules whose "
                          "proof sentence is no longer on the live page, with old and new text. Status open means a "
                          "person has not decided it yet; nothing in the rules changes before that."))
def watcher_findings(status: str | None = "open") -> dict:
    return {"findings": agents.findings(DEFAULT_PACK, status, 50), "runs": agents.runs("watcher", 3)}


if __name__ == "__main__":
    server.run("stdio")
