#!/usr/bin/env python3
"""Stand-in agent for rehearsals: re-issues the recorded run's tool calls (run/trace.jsonl) against
a live session file, with real EasyCrypt, and prints them in Claude Code's stream-json shape so
live_server.py treats it exactly like the real agent. Only meaningful when line 79 was deleted.

  replay_agent.py FILE DELETED_LINE [en|zh]
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import easycrypt_core as ec  # noqa: E402
from build_trace import NOTES, DELETED_LINE  # noqa: E402

path, line, lang = sys.argv[1], int(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "en")
out = lambda m: print(json.dumps(m, ensure_ascii=False), flush=True)
say = lambda text: out({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
if line != DELETED_LINE:
    say(f"(replay agent) The recording only covers line {DELETED_LINE}; start live_server.py with the claude agent for other lines.")
    out({"type": "result", "is_error": True, "result": "replay agent: unsupported line"}); sys.exit(0)

fns = {"easycrypt_config": ec.config, "check_file": ec.check_file, "goals_at": ec.goals_at,
       "try_snippet": ec.try_snippet, "apply_snippet": ec.apply_snippet, "search_lib": ec.search_lib}
rows = [json.loads(l) for l in open(os.path.join(HERE, "run", "trace.jsonl")) if l.strip()]
for i, (r, note) in enumerate(zip(rows, NOTES)):
    args = {k: (path if k == "path" else v) for k, v in r["args"].items()}
    say(note[0 if lang == "en" else 1])
    time.sleep(1.2)  # reading time; EasyCrypt itself runs at full speed below
    tid = f"replay_{i}"
    out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "mcp__easycrypt__" + r["tool"], "input": args}]}})
    res = fns[r["tool"]](**args)
    res = res.to_dict() if hasattr(res, "to_dict") else res
    out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                                  "content": [{"type": "text", "text": json.dumps(res)}]}]}})
say("Done." if lang == "en" else "完成。")
out({"type": "result", "is_error": False, "result": "replayed recorded run"})
