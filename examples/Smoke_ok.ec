(* Known-good file: `easycrypt llm -lastgoals Smoke_ok.ec` should exit 0. *)
require import AllCore.

lemma add0 (x : int) : x + 0 = x.
proof. by ring. qed.
