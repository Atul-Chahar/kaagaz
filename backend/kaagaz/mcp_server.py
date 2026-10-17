"""The same fixed tool catalogue over MCP (stdio). Add to Claude Code with:

    claude mcp add kaagaz -- uv --directory /path/to/kaagaz/backend run python -m kaagaz.mcp_server

FalkorDB must be running (docker compose up -d falkordb). Every call goes through Tools.call, so arguments are
validated, names are resolved against the graph first, and each result carries its outcome and trace.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .tools import TOOL_DESCRIPTIONS, ToolError, Tools

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


if __name__ == "__main__":
    server.run("stdio")
