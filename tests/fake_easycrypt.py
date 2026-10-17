#!/usr/bin/env python3
"""Stand-in for `easycrypt` so the server can be tested without an install.
Rule: any line containing `admit` or `FAIL` is an error. Emits the documented llm output format.
`-upto L` is exclusive, like the real binary: lines before L run, line L does not."""
import sys

args = sys.argv[1:]
if args[:1] == ["config"]:
    print("Fake EasyCrypt\nprovers: Alt-Ergo@2.6.0 Z3@4.12.6")
    sys.exit(0)

file = args[-1]
upto = int(args[args.index("-upto") + 1].split(":")[0]) if "-upto" in args else None
lines = open(file).read().splitlines()
limit = (upto - 1) if upto else len(lines)

for i, l in enumerate(lines[:limit], 1):
    if "admit" in l or "FAIL" in l:
        # real errors carry a precise location: "file: line L (c-d)"
        print(f"[critical] [{file}: line {i} (1-5)] cannot apply tactic\n  (details on a continuation line)", file=sys.stderr)
        if "-lastgoals" in args:
            print("Current goal\n\n------------------------\nforall x, x = x")
        sys.exit(1)

if upto:
    print(f"Current goal (before line {upto})\n\n------------------------\ntrue")
sys.exit(0)