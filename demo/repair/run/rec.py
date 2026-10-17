#!/usr/bin/env python3
"""rec.py TOOL 'JSON' — call one easycrypt_core tool, append {t,dur,tool,args,result} to trace.jsonl."""
import json, sys, time, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import easycrypt_core as ec
tool, args = sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
t = time.time()
fn = {"easycrypt_config": ec.config, "check_file": ec.check_file, "goals_at": ec.goals_at,
      "try_snippet": ec.try_snippet, "apply_snippet": ec.apply_snippet, "search_lib": ec.search_lib}[tool]
r = fn(**args)
r = r.to_dict() if hasattr(r, "to_dict") else r
dur = round(time.time() - t, 2)
with open(os.environ.get("TRACE", "trace.jsonl"), "a") as f:
    f.write(json.dumps({"t": t, "dur": dur, "tool": tool, "args": args, "result": r}) + "\n")
r.pop("raw_stderr", None) if isinstance(r, dict) and "OCaml" in str(r.get("raw_stderr")) else None
print(json.dumps(r, indent=1, ensure_ascii=False)[:6000]); print("dur", dur)
