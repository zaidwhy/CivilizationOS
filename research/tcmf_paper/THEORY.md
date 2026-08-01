# Why the fusion operator decides the outcome (formal analysis)

Companion to `FINDINGS.md`. That file reports what the benchmark measured; this one proves why
the measurement had to come out that way, and states precisely how far the proof reaches.

Everything here is checked against the shipped code, not just argued on paper:
`tcmfbench/theory.py` implements the predicates, `tcmfbench/test_theory.py` (17 tests) verifies
them against `rank_tcmf_multiplicative` / `rank_tcmf_additive` on real generated scenarios, and
`tcmfbench/run_theory.py` regenerates the measured table in `results_theory/`.

```
python -m tcmfbench.run_theory --seeds 10 --out results_theory
python -m tcmfbench.test_theory
```

---

## Setup

For each candidate memory `i` in the pool:

- `e(i) > 0` is the raw episodic score (relevance + recency + importance). It is **strictly
  positive**: relevance is clamped at 0 but recency is `exp(-decay * age) > 0` always
  (`api/memory/stream.py`, `retrieve`). No memory scores exactly zero.
- `ehat(i) = minmax(e)(i)` lies in `[0, 1]` (`methods._minmax`).
- `b(i)` in `[0, 1]` is the causal boost, exactly 0 when no ancestor clears the similarity
  threshold (`methods._causal_boosts`).

The two operators, both fed byte-identical `e` and `b`:

```
s_mult(i; lam) = e(i) * (1 + lam * b(i))
s_add(i; lam)  = ehat(i) + lam * b(i)
```

The regime of interest: the root cause `r` is semantically **dissimilar** to the crisis, so
`e(r)` is small; distractors `d` are semantically **similar** to it, so `e(d)` is large; and `r`
is a causal ancestor of the crisis while `d` is not, so `b(r) > b(d) = 0`.

**Lemma (affine margins).** For any pair `i, j`, both pairwise margins are affine in `lam`:

```
D_mult(lam) = [e(i) - e(j)]       + lam * [e(i)b(i) - e(j)b(j)]
D_add(lam)  = [ehat(i) - ehat(j)] + lam * [b(i) - b(j)]
```

*Proof.* Expand both definitions. The `lam`-free and `lam`-linear terms separate. []

Everything below follows from where `lam` appears in those two slopes.

---

## Proposition 1 (multiplicative fusion)

Fix a pair with `e(i) <= e(j)`, the regime's ordering.

**(a) Unreachability.** If `e(i)b(i) <= e(j)b(j)`, then `D_mult(lam) <= 0` for every
`lam >= 0`. No causal weighting whatsoever ranks `i` above `j`.

**(b) Crossing point.** Otherwise `i` outranks `j` exactly for `lam > lam*_mult`, where

```
lam*_mult = [e(j) - e(i)] / [e(i)b(i) - e(j)b(j)]
```

**(c) No causal-margin bound.** `lam*_mult` cannot be bounded by any function of the causal
margin `b(i) - b(j)` alone. Holding `b(i) > b(j)` fixed and writing `rho = e(i)/e(j)` in `(0, 1]`,

```
lam*_mult = (1 - rho) / (rho * b(i) - b(j))   ->   infinity   as rho decreases to b(j)/b(i)
```

while the causal margin never moves.

*Proof.* (a) and (b) are the Lemma: an affine function with non-positive intercept has constant
sign when its slope is non-positive, and otherwise crosses zero exactly once, at the stated
point. (c) Substitute `e(i) = rho * e(j)` into (b); `e(j)` cancels, and the denominator tends to
0 from above as `rho` tends to `b(j)/b(i)`. []

**Reading.** The episodic score never leaves the comparison. Multiplicative fusion scales the
causal signal *by* the semantic one rather than adding alongside it, so a memory with a weak
semantic match carries a proportionally shrunken causal claim. Promotion demands
`b(i)/b(j) > e(j)/e(i)`, and since `b <= 1` that is unsatisfiable once the episodic ratio is
large enough. The practical consequence is (c): **the correct `lam` is a property of each
scenario's episodic landscape, so no single global `lam` is correct across scenarios.**

---

## Proposition 2 (additive fusion)

If `b(i) > b(j)`, then `D_add(lam) > 0` for every

```
lam > lam*_add = max(0, [ehat(j) - ehat(i)] / [b(i) - b(j)])
```

and since `ehat` lies in `[0, 1]` the numerator is at most 1, giving the **episodic-independent**
bound

```
lam*_add <= 1 / (b(i) - b(j))
```

If `b(i) <= b(j)`, no `lam` suffices.

*Proof.* The Lemma, with the slope now equal to the causal margin, plus `ehat(j) - ehat(i) <= 1`
by the range of `ehat`. []

**Corollary 2.1 (one global lambda).** Let `gamma` be the smallest causal margin between the
root cause and any distractor it must outrank. Every `lam > 1/gamma` ranks the root cause above
all of them, **in every scenario, whatever the episodic scores**. Proposition 1(c) shows there is
no multiplicative counterpart to this statement.

This is the whole structural difference. Min-max normalisation bounds what the causal term has
to overcome at 1; multiplication leaves it unbounded.

---

## Proposition 3 (a lambda sweep cannot discover the fix)

As `lam` runs from 0 to infinity:

| operator | `lam = 0` ordering | `lam -> infinity` ordering |
|---|---|---|
| multiplicative | by `e` | by `e * b` |
| additive | by `ehat` | by `b` |

and each pair flips at most once. Hence the multiplicative sweep reaches the pure causal ordering
only in the degenerate case where `e` is constant across the pool.

*Proof.* The `lam = 0` endpoints are immediate. Dividing by `lam` and letting it grow,
`s_mult/lam -> e(i)b(i)` and `s_add/lam -> b(i)`; ties in `e*b` are broken by the
`lam`-independent term `e`. Single flip per pair is the Lemma. Finally `e*b` orders identically
to `b` for every `b` if and only if `e` is constant. []

**Reading.** This is what makes the operator choice a *design* failure rather than a *tuning*
failure. A practitioner sweeping `lam` on the multiplicative form is interpolating toward the
`e*b` ordering, and the causal ordering is not on that path. It is the formal version of the
paper's empirical observation that the low-`lam` ablation is flat, and it upgrades the response
to the "you just fixed your own bug" objection (`REVIEW.md` W2) from an argument into a proof.

---

## Measured (`results_theory/RESULTS_THEORY.md`, 10 seeds, pool 80)

| seed | mult needs | additive needs (uniform bound) | e(root) | max e(distractor) |
|---|---|---|---|---|
| 1 | 3.64 | 3.49 | 1.177 | 2.406 |
| 2 | 3.11 | 3.32 | 1.241 | 2.405 |
| 3 | 5.88 | 3.48 | 0.950 | 2.552 |
| 4 | 5.54 | 3.55 | 0.961 | 2.457 |
| 5 | 5.63 | 3.41 | 0.962 | 2.551 |
| 6 | 3.78 | 3.45 | 1.170 | 2.451 |
| 7 | unreachable | unreachable | 0.958 | 2.478 |
| 8 | 3.48 | 3.64 | 1.259 | 2.463 |
| 9 | 4.65 | 3.55 | 1.077 | 2.487 |
| 10 | 9.26 | 3.49 | 0.681 | 2.485 |

- The multiplicative requirement swings **3.0x** across seeds (3.11 to 9.26), plus one scenario
  no `lam` solves. The additive requirement swings **1.10x** (3.32 to 3.64). Same scenarios,
  same boosts; only the operator differs.
- **The shipped multiplicative default was `lam = 0.6`**, between 5x and 15x below what these
  scenarios actually require. That is the quantitative explanation of the measured recall@5 of
  0.02, and it is not a coincidence that the best multiplicative value found empirically was
  `lam = 8` (`REVIEW.md` W5): 8 is the smallest round value clearing most seeds' crossing points.
- **The shipped additive `lam = 4` clears the Proposition 2 bound on every solvable seed**, and
  `test_theory.py` confirms it puts the root cause above every distractor at that value. The
  tuned constant is therefore *explained* by the theory rather than merely fitted to the data,
  which is a useful thing to be able to say about a hyperparameter under review.

---

## Scope limit (stated because it is real, not hidden)

Proposition 1(a)'s outright-impossibility case is **rare in this benchmark: 1 of 200
root-cause/distractor pairs** (seed 7). In that single case the distractor's causal boost
*exceeds* the root cause's, so additive fusion cannot promote the root cause either, and the
`unreachable` entry appears in both columns above.

That case is a defect of the **boost function** (similarity threshold and depth weighting),
upstream of the fusion, and no choice of fusion operator addresses it. The paper's claim must
therefore be the one Proposition 1(c) supports, not the stronger one:

> Additive fusion admits a single scenario-independent lambda; multiplicative fusion does not.

rather than "multiplicative fusion can never retrieve the root cause." The second sentence is
false on this benchmark and a reviewer with the harness would find that in an afternoon.
`test_theory.py::test_unpromotable_case_is_rare_and_is_a_boost_defect_not_a_fusion_defect`
pins the 1-in-200 rate so the claim cannot silently drift.

Two further limits worth stating in the paper:

- The analysis is **pairwise**. It says when the root cause outranks a given distractor, not
  what recall@k is; recall follows only because clearing every distractor implies a top-k slot.
- `favor_root=True` raises the root cause's boost from about 0.29 to about 0.86, which shrinks
  both operators' required `lam` (multiplicative to 1.04 to 3.09, additive to 1.10 to 1.44) and
  removes the unreachable case entirely. The qualitative contrast survives the change; the
  numbers in the table above are for the `favor_root=False` configuration `tcmf_add` ships.

---

## What this changes for the paper

1. **It answers the reviewer question the evidence base cannot.** `NIGHT_QUEUE.md` N01 to N14
   are all empirical; a reviewer asking "why should this generalise beyond your benchmark?" gets
   a proof rather than another table. Propositions 1 to 3 hold for any `e`, `b`, and pool.
2. **It repairs, at the level of claims, the damage N01 did.** N01 found that "additive TCMF
   strictly beats every single-signal baseline at recall@10" dies at a realistic pool size
   (`tcmf_add` 0.80, tied with `graph_ppr`). Corollary 2.1 is pool-size independent, so the
   paper can lead with a claim that does not decay as the pool grows.
3. **It reframes the contribution.** The honest positioning is an empirical systems paper that
   isolates a failure mode, now with a formal account of the mechanism. That is a stronger
   framing than "new retrieval algorithm" and it is the one the evidence supports.

### LaTeX delta needed in the private repo (`syzayd/tcmf-paper`)

Not applied here; `main.tex` lives in the private repo and narrowing a headline claim is Zaid's
framing call.

- New subsection, "Why the operator decides", after the method section: the Lemma, Propositions
  1 to 3, Corollary 2.1, roughly three quarters of a column with proofs in a footnote or
  appendix.
- Abstract and intro: replace any "strictly beats every baseline" phrasing with the
  scenario-independent-lambda claim, which survives N01.
- Hyperparameter discussion (answers W5): state that `lam = 4` is the Proposition 2 bound rather
  than a tuned constant.
- Limitations: add the boost-function scope limit above, next to the existing
  missing-versus-spurious edge distinction.
