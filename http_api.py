"""Optional REST wrapper for humans and debugging (curl, browser /docs). Same core as the MCP server.

  uvicorn http_api:app --port 8000      # then open http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import easycrypt_core as ec

app = FastAPI(title="EasyCrypt API")


class GoalsReq(BaseModel):
    path: str
    line: int
    col: int | None = None


class SnippetReq(BaseModel):
    path: str
    snippet: str
    line: int | None = None


def _call(fn, *a):
    try:
        r = fn(*a)
        return r if isinstance(r, dict) else r.to_dict()
    except ec.ECError as e:
        raise HTTPException(400, str(e))


@app.get("/config")
def config():
    return _call(ec.config)


@app.get("/check")
def check(path: str):
    return _call(ec.check_file, path)


@app.post("/goals")
def goals(req: GoalsReq):
    return _call(ec.goals_at, req.path, req.line, req.col)


@app.post("/try")
def try_(req: SnippetReq):
    return _call(ec.try_snippet, req.path, req.snippet, req.line)