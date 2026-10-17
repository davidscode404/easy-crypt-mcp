"""MCP server (what Claude actually talks to).

  claude mcp add easycrypt -e EASYCRYPT_BIN=easycrypt -- python /abs/path/mcp_server.py
"""
try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

import easycrypt_core as ec

mcp = _Server("easycrypt")


def _wrap(fn, *a, **kw) -> dict:
    try:
        return fn(*a, **kw).to_dict()
    except ec.ECError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def easycrypt_config() -> dict:
    """Check the EasyCrypt install and list detected SMT solvers. Call once at the start;
    if no solvers are listed, `smt` tactics will fail."""
    try:
        return ec.config()
    except ec.ECError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def check_file(path: str) -> dict:
    """Check an entire .ec file. Returns ok, diagnostics [{severity,file,line,col,message}],
    and the remaining proof goals if it failed. Use after editing to confirm the file is accepted."""
    return _wrap(ec.check_file, path)


@mcp.tool()
def goals_at(path: str, line: int, col: int | None = None) -> dict:
    """Show the proof state (open goals) after checking the file up to `line` (1-based),
    optionally `col`. Use this to see what you need to prove before choosing a tactic."""
    return _wrap(ec.goals_at, path, line, col)


@mcp.tool()
def try_snippet(path: str, snippet: str, line: int | None = None) -> dict:
    """Test one or more tactics WITHOUT modifying the file. `snippet` is inserted before
    `line` (1-based; omit to append at the end) in a temporary copy, which is checked up to the
    end of the snippet. Returns ok, diagnostics, and the goals after the snippet. If ok, apply the
    same edit to the real file with your editor, then call check_file."""
    return _wrap(ec.try_snippet, path, snippet, line)


@mcp.tool()
def apply_snippet(path: str, snippet: str, line: int | None = None, commit: bool = True) -> dict:
    """Like try_snippet, but if the tactics are accepted, WRITE them into the real file (before
    `line`, or at the end) and git-commit that file as `agent: <first line>`. Returns the same
    fields plus `commit` (short sha, "" if not committed — `note` says why). On failure nothing
    is written. Prefer this over editing the file yourself: one accepted step = one commit."""
    return _wrap(ec.apply_snippet, path, snippet, line, commit)


@mcp.tool()
def search_lib(pattern: str, limit: int = 40) -> dict:
    """Grep EasyCrypt's standard library source for a case-insensitive regex — a name fragment
    like `dbool` or a statement shape like `mu1 .* dunifin`. Declarations come first. Then see a
    hit's full statement with try_snippet(path, "print <name>."). Textual only: names created by
    `clone … rename` (e.g. `dbool1E`) are not declared anywhere — list a theory instead with
    try_snippet(path, "print <Theory>."). (EasyCrypt's own `search` prints nothing in batch mode.)"""
    try:
        return ec.search_lib(pattern, limit)
    except ec.ECError as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()