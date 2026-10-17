#!/usr/bin/env python3
"""Stand-in for `easycrypt` so the server can be tested without an install.

Mimics real EasyCrypt r2026.09 behaviour that the server depends on:
- each non-blank line is one command; a line containing `admit` or `FAIL` is an error;
  a line containing `close` closes the current goal;
- diagnostics use the real format `[critical] [File.ec: line N (C1-C2)] msg`;
- `-upto LINE` is EXCLUSIVE: stops before the first command starting at or after LINE,
  prints goals, exits 0. If no command comes after, it runs to the end and prints nothing.
"""
import sys

args = sys.argv[1:]
if args[:1] == ["config"]:
    print("known provers: Alt-Ergo@2.6.4, Z3@4.12.6")
    sys.exit(0)

file = args[-1]
upto = int(args[args.index("-upto") + 1].split(":")[0]) if "-upto" in args else None
goal = "false"


def goals():
    return "Current goal\n\nType variables: <none>\n\n" + "-" * 72 + "\n" + goal if goal else "No more goals"


for i, l in enumerate(open(file).read().splitlines(), 1):
    if not l.strip():
        continue
    if upto is not None and i >= upto:
        print(goals())
        sys.exit(0)
    if "admit" in l or "FAIL" in l:
        print(f"[critical] [{file}: line {i} (0-{len(l)})] cannot apply tactic\n  (details on a continuation line)",
              file=sys.stderr)
        if "-lastgoals" in args:
            print(goals())
        sys.exit(1)
    if "close" in l:
        goal = None

sys.exit(0)