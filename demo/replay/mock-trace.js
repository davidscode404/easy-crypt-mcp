// Generated mock data for the replay page. Replace with real traces from mcp_server.py.
window.REPLAY_DATA = {
 "file": {
  "name": "elgamal.ec",
  "start": [
   "(* -------------------------------------------------------------------- *)",
   "require import AllCore Int Real Distr DBool.",
   "require (*--*) DiffieHellman PKE_CPA.",
   "",
   "(* ---------------- Sane Default Behaviours --------------------------- *)",
   "pragma +implicits.",
   "",
   "(* ---------------------- Let's Get Started --------------------------- *)",
   "(** Assumption: set DDH *)",
   "(*** WARNING: DiffieHellman is really out of date ***)",
   "clone DiffieHellman as DH.",
   "import DH.DDH DH.G DH.GP DH.FD DH.GP.ZModE.",
   "",
   "clone DH.GP.ZModE.ZModpField as ZPF.",
   "",
   "(** Construction: a PKE **)",
   "type pkey = group.",
   "type skey = exp.",
   "type ptxt = group.",
   "type ctxt = group * group.",
   "",
   "clone import PKE_CPA as PKE with",
   "  type pkey <- pkey,",
   "  type skey <- skey,",
   "  type ptxt <- ptxt,",
   "  type ctxt <- ctxt.",
   "",
   "(** Concrete Construction: Hashed ElGammal **)",
   "",
   "module ElGamal : Scheme = {",
   "  proc kg(): pkey * skey = {",
   "    var sk;",
   "",
   "    sk <$ dt;",
   "    return (g ^ sk, sk);",
   "  }",
   "",
   "  proc enc(pk:pkey, m:ptxt): ctxt = {",
   "    var y;",
   "",
   "    y <$ dt;",
   "    return (g ^ y, pk ^ y * m);",
   "  }",
   "",
   "  proc dec(sk:skey, c:ctxt): ptxt option = {",
   "    var gy, gm;",
   "",
   "    (gy, gm) <- c;",
   "    return Some (gm * gy ^ (-sk));",
   "  }",
   "}.",
   "",
   "(** Reduction: from a PKE adversary, construct a DDH adversary *)",
   "module DDHAdv (A:Adversary) = {",
   "  proc guess (gx, gy, gz) : bool = {",
   "    var m0, m1, b, b';",
   "",
   "    (m0, m1) <@ A.choose(gx);",
   "    b        <$ {0,1};",
   "    b'       <@ A.guess(gy, gz * (b?m1:m0));",
   "    return b' = b;",
   "  }",
   "}.",
   "",
   "(** We now prove that, for all adversary A, we have:",
   "      `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r |",
   "      = `| Pr[DDH0(DDHAdv(A)).main() @ &m : res]",
   "           - Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.        **)",
   "section Security.",
   "  declare module A <: Adversary.",
   "  declare axiom Ac_ll: islossless A.choose.",
   "  declare axiom Ag_ll: islossless A.guess.",
   "",
   "  local lemma cpa_ddh0 &m:",
   "      Pr[CPA(ElGamal,A).main() @ &m : res] =",
   "      Pr[DDH0(DDHAdv(A)).main() @ &m : res].",
   "  proof.",
   "  byequiv=> //; proc; inline *.",
   "  swap{1} 7 -5.",
   "  auto; call (_:true).",
   "  auto; call (_:true).",
   "  by auto=> /> sk _ y _ r b _; rewrite expM.",
   "  qed.",
   "",
   "  local module Gb = {",
   "    proc main () : bool = {",
   "      var x, y, z, m0, m1, b, b';",
   "",
   "      x       <$ dt;",
   "      y       <$ dt;",
   "      (m0,m1) <@ A.choose(g ^ x);",
   "      z       <$ dt;",
   "      b'      <@ A.guess(g ^ y, g ^ z);",
   "      b       <$ {0,1};",
   "      return b' = b;",
   "    }",
   "  }.",
   "",
   "  local lemma ddh1_gb &m:",
   "      Pr[DDH1(DDHAdv(A)).main() @ &m : res] =",
   "      Pr[Gb.main() @ &m : res].",
   "  proof.",
   "",
   "",
   "",
   "",
   "",
   "",
   "",
   "",
   "",
   "",
   "  qed.",
   "",
   "  local lemma Gb_half &m:",
   "     Pr[Gb.main()@ &m : res] = 1%r/2%r.",
   "  proof.",
   "  byphoare=> //; proc.",
   "  rnd  (pred1 b')=> //=.",
   "  conseq (: _ ==> true).",
   "  + by move=> /> b; rewrite dbool1E pred1E.",
   "  islossless;[ apply Ag_ll | apply Ac_ll].",
   "  qed.",
   "",
   "  lemma conclusion &m :",
   "    `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r | =",
   "    `| Pr[DDH0(DDHAdv(A)).main() @ &m : res] -",
   "         Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.",
   "  proof.",
   "  by rewrite (cpa_ddh0 &m) (ddh1_gb &m) (Gb_half &m).",
   "  qed.",
   "end section Security.",
   "",
   "print conclusion."
  ],
  "final": [
   "(* -------------------------------------------------------------------- *)",
   "require import AllCore Int Real Distr DBool.",
   "require (*--*) DiffieHellman PKE_CPA.",
   "",
   "(* ---------------- Sane Default Behaviours --------------------------- *)",
   "pragma +implicits.",
   "",
   "(* ---------------------- Let's Get Started --------------------------- *)",
   "(** Assumption: set DDH *)",
   "(*** WARNING: DiffieHellman is really out of date ***)",
   "clone DiffieHellman as DH.",
   "import DH.DDH DH.G DH.GP DH.FD DH.GP.ZModE.",
   "",
   "clone DH.GP.ZModE.ZModpField as ZPF.",
   "",
   "(** Construction: a PKE **)",
   "type pkey = group.",
   "type skey = exp.",
   "type ptxt = group.",
   "type ctxt = group * group.",
   "",
   "clone import PKE_CPA as PKE with",
   "  type pkey <- pkey,",
   "  type skey <- skey,",
   "  type ptxt <- ptxt,",
   "  type ctxt <- ctxt.",
   "",
   "(** Concrete Construction: Hashed ElGammal **)",
   "",
   "module ElGamal : Scheme = {",
   "  proc kg(): pkey * skey = {",
   "    var sk;",
   "",
   "    sk <$ dt;",
   "    return (g ^ sk, sk);",
   "  }",
   "",
   "  proc enc(pk:pkey, m:ptxt): ctxt = {",
   "    var y;",
   "",
   "    y <$ dt;",
   "    return (g ^ y, pk ^ y * m);",
   "  }",
   "",
   "  proc dec(sk:skey, c:ctxt): ptxt option = {",
   "    var gy, gm;",
   "",
   "    (gy, gm) <- c;",
   "    return Some (gm * gy ^ (-sk));",
   "  }",
   "}.",
   "",
   "(** Reduction: from a PKE adversary, construct a DDH adversary *)",
   "module DDHAdv (A:Adversary) = {",
   "  proc guess (gx, gy, gz) : bool = {",
   "    var m0, m1, b, b';",
   "",
   "    (m0, m1) <@ A.choose(gx);",
   "    b        <$ {0,1};",
   "    b'       <@ A.guess(gy, gz * (b?m1:m0));",
   "    return b' = b;",
   "  }",
   "}.",
   "",
   "(** We now prove that, for all adversary A, we have:",
   "      `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r |",
   "      = `| Pr[DDH0(DDHAdv(A)).main() @ &m : res]",
   "           - Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.        **)",
   "section Security.",
   "  declare module A <: Adversary.",
   "  declare axiom Ac_ll: islossless A.choose.",
   "  declare axiom Ag_ll: islossless A.guess.",
   "",
   "  local lemma cpa_ddh0 &m:",
   "      Pr[CPA(ElGamal,A).main() @ &m : res] =",
   "      Pr[DDH0(DDHAdv(A)).main() @ &m : res].",
   "  proof.",
   "  byequiv=> //; proc; inline *.",
   "  swap{1} 7 -5.",
   "  auto; call (_:true).",
   "  auto; call (_:true).",
   "  by auto=> /> sk _ y _ r b _; rewrite expM.",
   "  qed.",
   "",
   "  local module Gb = {",
   "    proc main () : bool = {",
   "      var x, y, z, m0, m1, b, b';",
   "",
   "      x       <$ dt;",
   "      y       <$ dt;",
   "      (m0,m1) <@ A.choose(g ^ x);",
   "      z       <$ dt;",
   "      b'      <@ A.guess(g ^ y, g ^ z);",
   "      b       <$ {0,1};",
   "      return b' = b;",
   "    }",
   "  }.",
   "",
   "  local lemma ddh1_gb &m:",
   "      Pr[DDH1(DDHAdv(A)).main() @ &m : res] =",
   "      Pr[Gb.main() @ &m : res].",
   "  proof.",
   "  byequiv=> //; proc; inline *.",
   "  swap{1} 3 2; swap{1} [5..6] 2; swap{2} 6 -2.",
   "  auto; call (_:true); wp.",
   "  rnd (fun z, z + loge (if b then m1 else m0){2})",
   "      (fun z, z - loge (if b then m1 else m0){2}).",
   "  auto; call (_:true).",
   "  auto; progress.",
   "  - by rewrite ZPF.addrAC -ZPF.addrA ZPF.subrr ZPF.addr0.",
   "  - by rewrite  -ZPF.addrA ZPF.subrr ZPF.addr0.",
   "  - by rewrite expD expgK.",
   "  qed.",
   "",
   "  local lemma Gb_half &m:",
   "     Pr[Gb.main()@ &m : res] = 1%r/2%r.",
   "  proof.",
   "  byphoare=> //; proc.",
   "  rnd  (pred1 b')=> //=.",
   "  conseq (: _ ==> true).",
   "  + by move=> /> b; rewrite dbool1E pred1E.",
   "  islossless;[ apply Ag_ll | apply Ac_ll].",
   "  qed.",
   "",
   "  lemma conclusion &m :",
   "    `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r | =",
   "    `| Pr[DDH0(DDHAdv(A)).main() @ &m : res] -",
   "         Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.",
   "  proof.",
   "  by rewrite (cpa_ddh0 &m) (ddh1_gb &m) (Gb_half &m).",
   "  qed.",
   "end section Security.",
   "",
   "print conclusion."
  ],
  "hole": [
   103,
   112
  ],
  "task": "Fill in the missing proof of lemma ddh1_gb (lines 103-112)"
 },
 "lanes": {
  "with": {
   "title": "With MCP",
   "events": [
    {
     "t": 0,
     "tool": "easycrypt_config",
     "args": {},
     "result": {
      "ok": true,
      "output": "Provers: Alt-Ergo@2.6.0, Z3@4.12.6"
     }
    },
    {
     "t": 4,
     "tool": "check_file",
     "args": {
      "path": "demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "diagnostics": [
       {
        "severity": "critical",
        "file": "elgamal.ec",
        "line": 113,
        "col": 2,
        "message": "cannot save an incomplete proof"
       }
      ],
      "goals": "Current goal (remaining: 1)\n\nType variables: <none>\n\n&m: {}\n------------------------------------------------------------------------\nPr[DDH1(DDHAdv(A)).main() @ &m : res] = Pr[Gb.main() @ &m : res]"
     }
    },
    {
     "t": 9,
     "tool": "goals_at",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 103
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\nType variables: <none>\n\n&m: {}\n------------------------------------------------------------------------\nPr[DDH1(DDHAdv(A)).main() @ &m : res] = Pr[Gb.main() @ &m : res]"
     }
    },
    {
     "t": 15,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 103,
      "snippet": "byequiv=> //; proc; inline *."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  z <$ dt\n(4)  (m0, m1) <@ A.choose(g ^ x)\n(5)  b <$ {0,1}\n(6)  b' <@ A.guess(g ^ y, g ^ z * (b ? m1 : m0))\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  z <$ dt\n(5)  b' <@ A.guess(g ^ y, g ^ z)\n(6)  b <$ {0,1}\n\npost = b'{1} = b{1} <=> b'{2} = b{2}"
     }
    },
    {
     "t": 19,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 103,
      "snippet": "  byequiv=> //; proc; inline *."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 25,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 104,
      "snippet": "auto; call (_:true)."
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "diagnostics": [
       {
        "severity": "critical",
        "file": "elgamal.ec",
        "line": 104,
        "col": 2,
        "message": "the two programs are not in sync: cannot match random samplings `z <$ dt` and `(m0, m1) <@ A.choose(...)`"
       }
      ],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  z <$ dt\n(4)  (m0, m1) <@ A.choose(g ^ x)\n(5)  b <$ {0,1}\n(6)  b' <@ A.guess(g ^ y, g ^ z * (b ? m1 : m0))\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  z <$ dt\n(5)  b' <@ A.guess(g ^ y, g ^ z)\n(6)  b <$ {0,1}\n\npost = b'{1} = b{1} <=> b'{2} = b{2}"
     }
    },
    {
     "t": 31,
     "tool": "goals_at",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 104
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  z <$ dt\n(4)  (m0, m1) <@ A.choose(g ^ x)\n(5)  b <$ {0,1}\n(6)  b' <@ A.guess(g ^ y, g ^ z * (b ? m1 : m0))\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  z <$ dt\n(5)  b' <@ A.guess(g ^ y, g ^ z)\n(6)  b <$ {0,1}\n\npost = b'{1} = b{1} <=> b'{2} = b{2}"
     }
    },
    {
     "t": 39,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 104,
      "snippet": "swap{1} 3 2; swap{1} [5..6] 2; swap{2} 6 -2."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n(6)  b' <@ A.guess(g ^ y, g ^ z * (b ? m1 : m0))\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n(6)  b' <@ A.guess(g ^ y, g ^ z)\n\npost = b'{1} = b{1} <=> b'{2} = b{2}"
     }
    },
    {
     "t": 43,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 104,
      "snippet": "  swap{1} 3 2; swap{1} [5..6] 2; swap{2} 6 -2."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 49,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 105,
      "snippet": "auto; call (_:true); wp."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n\npost = g ^ z{1} * (b{1} ? m1{1} : m0{1}) = g ^ z{2} /\\ ..."
     }
    },
    {
     "t": 53,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 105,
      "snippet": "  auto; call (_:true); wp."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 59,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 106,
      "snippet": "rnd."
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "diagnostics": [
       {
        "severity": "critical",
        "file": "elgamal.ec",
        "line": 106,
        "col": 2,
        "message": "cannot prove the postcondition: `g ^ z{1} * (b ? m1 : m0)` and `g ^ z{2}` are different samples"
       }
      ],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n(5)  z <$ dt\n\npost = g ^ z{1} * (b{1} ? m1{1} : m0{1}) = g ^ z{2} /\\ ..."
     }
    },
    {
     "t": 71,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 106,
      "snippet": "rnd (fun z, z + loge (if b then m1 else m0){2})\n(fun z, z - loge (if b then m1 else m0){2})."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n\npost = forall z, z + loge (b ? m1 : m0) - loge (b ? m1 : m0) = z /\\ ..."
     }
    },
    {
     "t": 75,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 106,
      "snippet": "  rnd (fun z, z + loge (if b then m1 else m0){2})\n      (fun z, z - loge (if b then m1 else m0){2})."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 81,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 108,
      "snippet": "auto; call (_:true)."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n\n(1)  x <$ dt\n(2)  y <$ dt\n(3)  (m0, m1) <@ A.choose(g ^ x)\n(4)  b <$ {0,1}\n\npost = forall z, z + loge (b ? m1 : m0) - loge (b ? m1 : m0) = z /\\ ..."
     }
    },
    {
     "t": 84,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 108,
      "snippet": "  auto; call (_:true)."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 90,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 109,
      "snippet": "auto; progress."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 3)\n\n------------------------------------------------------------------------\nzR - loge (if bL then m1L else m0L) + loge (if bL then m1L else m0L) = zR"
     }
    },
    {
     "t": 93,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 109,
      "snippet": "  auto; progress."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 99,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 110,
      "snippet": "- by rewrite ZPF.addrAC -ZPF.addrA ZPF.subrr ZPF.addr0."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 2)\n\n------------------------------------------------------------------------\nzL + loge (if bL then m1L else m0L) - loge (if bL then m1L else m0L) = zL"
     }
    },
    {
     "t": 102,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 110,
      "snippet": "  - by rewrite ZPF.addrAC -ZPF.addrA ZPF.subrr ZPF.addr0."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 108,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 111,
      "snippet": "- by smt()."
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "diagnostics": [
       {
        "severity": "critical",
        "file": "elgamal.ec",
        "line": 111,
        "col": 2,
        "message": "SMT solvers could not prove the goal (timeout)"
       }
      ],
      "goals": "Current goal (remaining: 2)\n\n------------------------------------------------------------------------\nzL + loge (if bL then m1L else m0L) - loge (if bL then m1L else m0L) = zL"
     }
    },
    {
     "t": 118,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 111,
      "snippet": "- by rewrite  -ZPF.addrA ZPF.subrr ZPF.addr0."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "Current goal (remaining: 1)\n\n------------------------------------------------------------------------\ng ^ (zL + loge (if bL then m1L else m0L)) = g ^ zL * (if bL then m1L else m0L)"
     }
    },
    {
     "t": 121,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 111,
      "snippet": "  - by rewrite  -ZPF.addrA ZPF.subrr ZPF.addr0."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 127,
     "tool": "try_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 112,
      "snippet": "- by rewrite expD expgK."
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": "No more goals"
     }
    },
    {
     "t": 130,
     "tool": "apply_snippet",
     "args": {
      "path": "demo/elgamal.ec",
      "line": 112,
      "snippet": "  - by rewrite expD expgK."
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 136,
     "tool": "check_file",
     "args": {
      "path": "demo/elgamal.ec"
     },
     "result": {
      "ok": true,
      "exit_code": 0,
      "diagnostics": [],
      "goals": ""
     }
    }
   ]
  },
  "without": {
   "title": "Without MCP",
   "events": [
    {
     "t": 0,
     "tool": "edit",
     "args": {
      "path": "demo/elgamal.ec",
      "start": 103,
      "end": 112,
      "text": "  byequiv=> //; proc; inline *.\n  auto; call (_:true).\n  rnd.\n  auto; progress.\n  by smt().\n\n\n\n\n"
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 14,
     "tool": "bash",
     "args": {
      "command": "easycrypt compile demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "[info] [elgamal.ec:1] loading theory AllCore\n[info] [elgamal.ec:2] loading theory DiffieHellman\n[info] [elgamal.ec:3] loading theory PKE_CPA\n[warning] [elgamal.ec: line 10 (0-48)] DiffieHellman is really out of date\n[critical] [elgamal.ec: line 104 (2-40)] cannot apply `call`: the programs are not in sync\n\nCurrent goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n...(120 more lines)..."
     }
    },
    {
     "t": 40,
     "tool": "edit",
     "args": {
      "path": "demo/elgamal.ec",
      "start": 103,
      "end": 112,
      "text": "  byequiv=> //; proc; inline *.\n  swap{1} 3 2.\n  auto; call (_:true).\n  rnd.\n  auto; progress; smt().\n\n\n\n\n"
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 55,
     "tool": "bash",
     "args": {
      "command": "easycrypt compile demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "[info] [elgamal.ec:1] loading theory AllCore\n[info] [elgamal.ec:2] loading theory DiffieHellman\n[info] [elgamal.ec:3] loading theory PKE_CPA\n[warning] [elgamal.ec: line 10 (0-48)] DiffieHellman is really out of date\n[critical] [elgamal.ec: line 104 (2-40)] invalid swap: position 2 out of bounds\n\nCurrent goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n...(120 more lines)..."
     }
    },
    {
     "t": 84,
     "tool": "edit",
     "args": {
      "path": "demo/elgamal.ec",
      "start": 103,
      "end": 112,
      "text": "  byequiv=> //; proc; inline *.\n  swap{1} 3 2; swap{2} 6 -2.\n  auto; call (_:true); wp.\n  rnd.\n  auto; call (_:true).\n  auto; progress; smt().\n\n\n\n"
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 99,
     "tool": "bash",
     "args": {
      "command": "easycrypt compile demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "[info] [elgamal.ec:1] loading theory AllCore\n[info] [elgamal.ec:2] loading theory DiffieHellman\n[info] [elgamal.ec:3] loading theory PKE_CPA\n[warning] [elgamal.ec: line 10 (0-48)] DiffieHellman is really out of date\n[critical] [elgamal.ec: line 106 (2-40)] cannot prove the postcondition of `rnd`\n\nCurrent goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n...(120 more lines)..."
     }
    },
    {
     "t": 128,
     "tool": "edit",
     "args": {
      "path": "demo/elgamal.ec",
      "start": 103,
      "end": 112,
      "text": "  byequiv=> //; proc; inline *.\n  swap{1} 3 2; swap{1} [5..6] 2; swap{2} 6 -2.\n  auto; call (_:true); wp.\n  rnd (fun z, z + loge m1) (fun z, z - loge m1).\n  auto; call (_:true).\n  auto; progress; smt().\n\n\n\n"
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 143,
     "tool": "bash",
     "args": {
      "command": "easycrypt compile demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "[info] [elgamal.ec:1] loading theory AllCore\n[info] [elgamal.ec:2] loading theory DiffieHellman\n[info] [elgamal.ec:3] loading theory PKE_CPA\n[warning] [elgamal.ec: line 10 (0-48)] DiffieHellman is really out of date\n[critical] [elgamal.ec: line 106 (2-40)] cannot prove the postcondition of `rnd`\n\nCurrent goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n...(120 more lines)..."
     }
    },
    {
     "t": 172,
     "tool": "edit",
     "args": {
      "path": "demo/elgamal.ec",
      "start": 103,
      "end": 112,
      "text": "  byequiv=> //; proc; inline *.\n  swap{1} 3 2; swap{1} [5..6] 2; swap{2} 6 -2.\n  auto; call (_:true); wp.\n  rnd (fun z, z + loge (if b then m1 else m0){2})\n      (fun z, z - loge (if b then m1 else m0){2}).\n  auto; call (_:true).\n  auto; progress; smt().\n\n\n"
     },
     "result": {
      "ok": true
     }
    },
    {
     "t": 260,
     "tool": "bash",
     "args": {
      "command": "easycrypt compile demo/elgamal.ec"
     },
     "result": {
      "ok": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "[info] [elgamal.ec:1] loading theory AllCore\n[info] [elgamal.ec:2] loading theory DiffieHellman\n[info] [elgamal.ec:3] loading theory PKE_CPA\n[warning] [elgamal.ec: line 10 (0-48)] DiffieHellman is really out of date\n[critical] [elgamal.ec: line 109 (2-40)] SMT solvers could not prove the goal (timeout after 60s)\n\nCurrent goal (remaining: 1)\n\n&1 (left ) : {DDH1(DDHAdv(A)).main}\n&2 (right) : {Gb.main}\n\npre = true\n...(120 more lines)..."
     }
    },
    {
     "t": 300,
     "tool": "stop",
     "args": {
      "reason": "budget"
     },
     "result": {
      "ok": false,
      "note": "Gave up after 5 attempts"
     }
    }
   ]
  }
 },
 "mock": true
};
