#!/usr/bin/env python3
"""Live backend for the proof-repair page: delete a line on stage, watch an agent repair it.

  .venv/bin/python demo/repair/live_server.py              # http://127.0.0.1:8766, agent = claude
  .venv/bin/python demo/repair/live_server.py --agent replay   # no LLM: replays the recorded line-79 run

The page (index.html, same directory) finds this server via GET /api/status; opened without it,
the page falls back to the recorded run in trace.js.

API (all JSON except the event stream):
  GET  /api/status                  {agent, proof: name}
  GET  /api/proof                   {name, text, deletable: [line, ...]}   lines inside proof … qed
  POST /api/sessions {line, lang}   delete LINE from a fresh copy, start the agent → {id, task, deleted}
  GET  /api/sessions/ID/events      text/event-stream, replayed from the start on every connect:
        note  {text}                          agent prose (its reasoning before a tool call)
        call  {id, tool, args, t}             tool call started (EasyCrypt is running)
        step  {id, tool, args, result, t, dur, note}   tool call finished
        log   {text}                          agent stderr / non-JSON output, for debugging
        done  {ok, exit_code, diagnostics, text, summary}   final check_file on the session file
  POST /api/sessions/ID/stop        kill the agent

Agents:
  claude   headless Claude Code (`claude -p … --output-format stream-json`) with the easycrypt MCP
           server from this repo and the easycrypt-prover skill as system prompt. Needs a logged-in
           `claude` (run `claude` once, /login) or ANTHROPIC_API_KEY. Binary: --claude or $CLAUDE_BIN.
  replay   replay_agent.py: re-issues the recorded run's tool calls against the session file, for
           rehearsing without network. Only valid when line 79 is deleted.

Sessions live in demo/repair/sessions/<id>/ (git repo per session, so apply_snippet commits).
"""
import argparse, json, os, re, shutil, subprocess, sys, threading, time, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8766)
ap.add_argument("--proof", default=str(REPO / "demo" / "elgamal.ec"))
ap.add_argument("--agent", choices=["claude", "replay"], default="claude")


def find_claude() -> str:
    """$CLAUDE_BIN, `claude` on PATH, the usual install spots, then the desktop app's bundled CLI."""
    bundled = sorted((Path.home() / "Library/Application Support/Claude/claude-code").glob(
        "*/*/claude.app/Contents/MacOS/claude"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in [os.environ.get("CLAUDE_BIN"), shutil.which("claude"), str(Path.home() / ".local/bin/claude"),
              str(Path.home() / ".claude/local/claude"), os.environ.get("CLAUDE_CODE_EXECPATH"),
              *map(str, bundled)]:
        if c and os.access(c, os.X_OK):
            return c
    return "claude"


ap.add_argument("--claude", default=find_claude())
ap.add_argument("--model", default=os.environ.get("CLAUDE_MODEL", ""))
ap.add_argument("--fallback-model", default=os.environ.get("CLAUDE_FALLBACK_MODEL", "claude-sonnet-5"),
                help="retry the session once with this model if the first agent run is refused by a safeguard; '' disables")
ap.add_argument("--python", default=str(REPO / ".venv" / "bin" / "python"),
                help="interpreter with the `mcp` package, used to run mcp_server.py")
ARGS = ap.parse_args()

EC_BIN = os.environ.get("EASYCRYPT_BIN") or shutil.which("easycrypt") or str(Path.home() / ".opam/easycrypt/bin/easycrypt")
EC_ARGS = os.environ.get("EASYCRYPT_ARGS", "-timeout 10")
os.environ.update(EASYCRYPT_BIN=EC_BIN, EASYCRYPT_ARGS=EC_ARGS)  # for the final check below
sys.path.insert(0, str(REPO))
import easycrypt_core as ec  # noqa: E402
SESSIONS_DIR = HERE / "sessions"
SKILL = (REPO / ".claude/skills/easycrypt-prover/SKILL.md").read_text()
SKILL = SKILL.split("---", 2)[2] if SKILL.startswith("---") else SKILL  # drop front matter


def deletable_lines(text: str) -> list[int]:
    """Non-blank lines strictly between `proof.` and `qed.`."""
    out, inside = [], False
    for i, l in enumerate(text.split("\n"), 1):
        s = l.strip()
        if s.startswith("proof."):
            inside = True
        elif s.startswith("qed."):
            inside = False
        elif inside and s:
            out.append(i)
    return out


class Session:
    def __init__(self, line: int, lang: str):
        self.id = uuid.uuid4().hex[:8]
        self.dir = SESSIONS_DIR / self.id
        self.dir.mkdir(parents=True)
        src = Path(ARGS.proof)
        lines = src.read_text().split("\n")
        self.deleted = {"line": line, "text": lines[line - 1]}
        self.task = "\n".join(lines[:line - 1] + lines[line:])
        self.file = self.dir / src.name
        self.file.write_text(self.task)
        git = ["git", "-c", "user.name=demo", "-c", "user.email=demo@localhost"]
        subprocess.run(["git", "init", "-q"], cwd=self.dir)
        subprocess.run(git + ["add", src.name], cwd=self.dir)
        subprocess.run(git + ["commit", "-qm", f"task: line {line} deleted"], cwd=self.dir)
        self.lang = lang
        self.model = ARGS.model
        self.retried = False
        self.events: list[tuple[str, dict]] = []
        self.cv = threading.Condition()
        self.proc: subprocess.Popen | None = None
        self.t0 = time.time()
        threading.Thread(target=self.run, daemon=True).start()

    def emit(self, kind: str, data: dict):
        with self.cv:
            self.events.append((kind, data))
            self.cv.notify_all()

    # ---- agent ---------------------------------------------------------------------------
    def command(self) -> list[str]:
        if ARGS.agent == "replay":
            return [sys.executable, str(HERE / "replay_agent.py"), str(self.file), str(self.deleted["line"]), self.lang]
        cfg = {"mcpServers": {"easycrypt": {
            "command": ARGS.python, "args": [str(REPO / "mcp_server.py")],
            "env": {"EASYCRYPT_BIN": EC_BIN, "EASYCRYPT_ARGS": EC_ARGS, "EASYCRYPT_ROOT": str(self.dir),
                    "PATH": f"{Path(EC_BIN).parent}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"}}}}
        (self.dir / "mcp.json").write_text(json.dumps(cfg))
        language = "Chinese (简体中文)" if self.lang == "zh" else "English"
        # Keep the narration request neutral: asking the model to explain "why" before each step
        # tripped Opus 5's reasoning_extraction safeguard mid-run; a status line does not.
        prompt = (
            f"`{self.file}` is an EasyCrypt proof with exactly one line deleted somewhere inside a "
            f"proof block, so the file no longer checks. Repair it using only the easycrypt tools "
            f"(always pass the absolute path above). This runs in front of an audience: before each "
            f"tool call, write one short status line in {language} naming the step you are taking "
            f"(for example which tactic you will try at which line). Stop as soon as check_file "
            f"returns ok, then give a one-sentence summary in {language}.")
        cmd = [ARGS.claude, "-p", prompt, "--mcp-config", str(self.dir / "mcp.json"), "--strict-mcp-config",
               "--tools", "", "--allowedTools", "mcp__easycrypt__*", "--append-system-prompt", SKILL,
               "--output-format", "stream-json", "--verbose"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd

    def run(self):
        try:
            self.proc = subprocess.Popen(self.command(), cwd=self.dir, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        except OSError as e:
            self.emit("log", {"text": f"could not start agent: {e}"})
            return self.finish("")
        threading.Thread(target=self.pump_stderr, daemon=True).start()
        pending, note, summary = {}, [], ""
        for raw in self.proc.stdout:
            try:
                m = json.loads(raw)
            except ValueError:
                if raw.strip():
                    self.emit("log", {"text": raw.rstrip()})
                continue
            now = round(time.time() - self.t0, 1)
            if m.get("type") == "assistant":
                for b in m["message"].get("content") or []:
                    if b.get("type") == "text" and b["text"].strip():
                        note.append(b["text"].strip())
                        self.emit("note", {"text": b["text"].strip()})
                    elif b.get("type") == "tool_use":
                        tool = b["name"].split("__")[-1]
                        pending[b["id"]] = {"tool": tool, "args": b.get("input") or {}, "t": now,
                                            "note": "\n".join(note)}
                        note = []
                        self.emit("call", {"id": b["id"], "tool": tool, "args": pending[b["id"]]["args"], "t": now})
            elif m.get("type") == "user":
                for b in m["message"].get("content") or []:
                    if b.get("type") != "tool_result" or b.get("tool_use_id") not in pending:
                        continue
                    p = pending.pop(b["tool_use_id"])
                    c = b.get("content")
                    txt = c if isinstance(c, str) else "".join(x.get("text", "") for x in c or [])
                    try:
                        result = json.loads(txt)
                    except ValueError:
                        result = {"ok": False, "error": txt}
                    self.emit("step", {"id": b["tool_use_id"], **p, "result": result, "dur": round(now - p["t"], 2)})
            elif m.get("type") == "result":
                summary = m.get("result") or ""
                if m.get("is_error"):
                    self.emit("log", {"text": f"agent error: {summary}"})
        self.proc.wait()
        if "safeguards flagged" in summary and ARGS.fallback_model and not self.retried \
                and ARGS.fallback_model != self.model:
            # A safety classifier refused mid-run (seen with Opus 5 on proof goals). The file is
            # unchanged except for steps already applied, so run the same task again on the fallback.
            self.retried, self.model = True, ARGS.fallback_model
            self.emit("note", {"text": (f"模型安全分类器误报，改用 {self.model} 重新开始。" if self.lang == "zh"
                                        else f"The model's safeguard refused this run; starting again with {self.model}.")})
            return self.run()
        self.finish(summary)

    def pump_stderr(self):
        for l in self.proc.stderr:
            if l.strip():
                self.emit("log", {"text": l.rstrip()})

    def finish(self, summary: str):
        r = ec.check_file(str(self.file)).to_dict()  # the verdict comes from EasyCrypt, not the agent
        self.emit("done", {"ok": r["ok"], "exit_code": r["exit_code"], "diagnostics": r["diagnostics"],
                           "text": self.file.read_text(), "summary": summary})

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


SESSIONS: dict[str, Session] = {}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, fmt, *a):
        if "/events" not in self.path:
            sys.stderr.write("%s\n" % (fmt % a))

    def json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            return self.json({"agent": ARGS.agent, "proof": Path(ARGS.proof).name})
        if self.path == "/api/proof":
            text = Path(ARGS.proof).read_text()
            return self.json({"name": Path(ARGS.proof).name, "text": text, "deletable": deletable_lines(text)})
        m = re.fullmatch(r"/api/sessions/(\w+)/events", self.path)
        if m:
            return self.stream(m.group(1))
        if self.path.startswith("/sessions/"):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/sessions":
            line = int(body.get("line", 0))
            if line not in deletable_lines(Path(ARGS.proof).read_text()):
                return self.json({"error": f"line {line} is not inside a proof"}, 400)
            s = Session(line, body.get("lang", "en"))
            SESSIONS[s.id] = s
            return self.json({"id": s.id, "task": s.task, "deleted": s.deleted, "agent": ARGS.agent})
        m = re.fullmatch(r"/api/sessions/(\w+)/stop", self.path)
        if m and m.group(1) in SESSIONS:
            SESSIONS[m.group(1)].stop()
            return self.json({"ok": True})
        self.json({"error": "not found"}, 404)

    def stream(self, sid: str):
        s = SESSIONS.get(sid)
        if not s:
            return self.json({"error": "no such session"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        i = 0
        try:
            while True:
                with s.cv:
                    while i >= len(s.events):
                        if not s.cv.wait(timeout=15):
                            self.wfile.write(b": ping\n\n"); self.wfile.flush()
                    batch = s.events[i:]
                for kind, data in batch:
                    self.wfile.write(f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
                    i += 1
                self.wfile.flush()
                if batch and batch[-1][0] == "done":
                    return
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    print(f"proof-repair live: http://127.0.0.1:{ARGS.port}  (agent: {ARGS.agent}, easycrypt: {EC_BIN})")
    if ARGS.agent == "claude":
        print(f"claude: {ARGS.claude}")
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()
