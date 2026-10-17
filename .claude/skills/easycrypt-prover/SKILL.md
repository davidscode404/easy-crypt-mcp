---
name: easycrypt-prover
description: Drive EasyCrypt proofs through the `easycrypt` MCP tools — check a .ec file, read the open goals, test a tactic without touching the file, apply accepted steps one commit at a time, and stop with a precise report when stuck. Use whenever a .ec/.eca file must be proved, completed, repaired, or inspected.
---

# EasyCrypt prover

You are driving EasyCrypt, the proof assistant for cryptographic game-hopping proofs, through six
MCP tools. The `.ec` file is the whole state: every tool call re-checks it from line 1 (≈ 5 s on a
small file), and git history of the file is the record of what you did.

## Ground rules

1. **Never edit a `.ec` file with your editor.** Text enters a proof file only through
   `apply_snippet`. The bytes written are exactly the bytes that were just checked, and every
   accepted step becomes one commit.
2. **Test, then apply.** `try_snippet` first; `apply_snippet` only with text that just passed.
3. **Close with `by`.** `trivial`, `auto`, `smt`, `done` on their own never fail — they leave the
   goal open and the error appears later at `qed.` as "cannot save an incomplete proof" with no
   useful location. Always write `by auto.`, `by smt().`, `by rewrite H.` so a failed attempt fails
   on its own line.
4. **Insert before `qed.`** (or before the first failing command). Appending at end of file also
   works — the server adds a stop marker to the temp copy — but mid-proof is what you normally want.
   Do not read other copies of the proof (e.g. `demo/elgamal.ec`); work only from the goals.
5. **One goal at a time.** The first failing lemma; inside it, the first open goal.
6. **Budget: 6 attempts per goal, 30 per lemma.** When it is spent, HANDOFF (below). Do not loop.

## The loop

0. Once per session: `easycrypt_config`. At least one of Alt-Ergo, Z3, CVC5 must be listed.
1. `check_file(path)`. `ok` → done. Otherwise take `diagnostics[0].line` (the first `critical`)
   and read `goals`.
2. `goals_at(path, line)` — the state *before* that line runs. Decide what kind of goal it is:
   an **ambient** formula (`forall`, `=>`, arithmetic, equalities) or a **program** judgment
   (`equiv`, `phoare`, `hoare`, or a `Pr[...]` statement).
3. Take the next rung of the ladder for that kind.
4. `try_snippet(path, "<tactic>.", line)`.
   - `ok` → `apply_snippet` with the same text and line → back to 1.
   - not `ok` → read `diagnostics[0].message` and the returned `goals`; next rung → 4.
5. Ladder exhausted → split the goal (`seq`, `conseq`, `case`) and recurse on the pieces.
   Still stuck → HANDOFF.

## Tactic ladder

### Ambient goals
1. `by smt().` Then `by smt(<lemma> <lemma>).` with one to three hints (see *Finding lemmas*).
2. `by auto.` · `by done.` · `by simplify.`
3. `by move=> ...; rewrite <lemma>.` · `by apply <lemma>.` · `by exact <lemma>.`
4. Rings and fields: `by ring.` · `by field.`
5. Case analysis: `case: (<bool>).` / `elim: <x>.`, then recurse.

### Program goals
- Turn a probability statement into a judgment: `byequiv=> //.` for `Pr[..] = Pr[..]`,
  `byphoare=> //.` for `Pr[..] = r`.
- Enter procedures: `proc.` Inline: `inline *.`
- Line the programs up: `swap{1} i j.` / `swap{2} [i..j] k.` move independent statements so that
  matching statements face each other.
- Discharge from the back: `auto.` (wp + rnd + skip, then tries to close), `wp.`, `sp.`, `skip.`
- Adversary calls: `call (_: true).` when nothing about the adversary's state matters; otherwise
  `call (_: <invariant>).`
- Samplings: `rnd.` when both sides draw the same; `rnd (fun z => <f z>) (fun z => <g z>).` with a
  bijection when they differ.
- Split / weaken: `seq n m : (<invariant>).` · `conseq (_: _ ==> <Q>).`
- Lossless side goals: `islossless.`, `by islossless; apply <A_ll>.`
- Identical programs: `sim.`
- Finish: `auto=> />.` and continue with the ambient ladder on what is left — e.g.
  `by auto=> /> sk _ y _ r b _; rewrite expM.`

## Finding lemmas

1. The file's `require import` lines name what is in scope. `try_snippet(path, "print <Theory>.",
   line)` lists every lemma in a theory with its statement.
2. `search_lib("<regex>")` greps the standard library source for declarations. It cannot see names
   produced by `clone … rename` (e.g. `dbool1E` is `dunifin1E` renamed) — those only show up via
   `print`.
3. `try_snippet(path, "print <name>.", line)` shows one statement with its fully qualified name.
4. Prefer `by smt(<name>).` with the lemma as a hint; fall back to an explicit `rewrite` chain
   when SMT times out. EasyCrypt's own `search` command prints nothing here — do not use it.

## Reading the output

- `goals`: hypotheses above the `------` line, conclusion below. `No active proof.` means the
  position is outside any `proof … qed` block.
- `diagnostics[0].message`: the error at the first failing command; continuation lines are
  included. `raw_stderr` is set only when nothing could be parsed.
- `note` on `try_snippet`/`apply_snippet` tells you which lines the snippet occupied.

## HANDOFF

When the budget is spent, stop and report — do not keep trying:

- Lemma name and line.
- The goal, pasted from `goals`.
- Every tactic tried, each with the one-line reason it failed.
- What you believe is missing: a lemma that may not exist, an invariant for `seq`/`call`, a
  bijection for `rnd`.

The file is left at the last accepted step; every accepted step is already committed.
