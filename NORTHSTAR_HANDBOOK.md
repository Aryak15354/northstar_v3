# The Northstar Handbook

**Volume II. Operational manual only — no research narrative here (see `MONOGRAPH.md` for that).**
Everything below is either already frozen, certified, and running, or newly recovered and validated in
this session. If a rule isn't in this document, it isn't part of the operating strategy — do not infer
or extrapolate beyond what's written here.

---

## 1. The Frozen Portfolio

**Two-sleeve book, frozen 2026-07-18, unchanged since** (`results/FROZEN_SPEC.md`, the single source of
truth — this handbook summarizes it, does not supersede it). **80% Sleeve-1 (stock momentum, Config-4) +
20% Sleeve-2 (sector rotation)**, half-size (Verdict-B) on the paper NAV.

### Sleeve 1 — Stock Momentum (Config-4), 80% of book capital
- **Signal:** equal-weight composite of 4 per-sector z-scored momentum features (`res_mom_52w_ex4w`,
  `ret_52w_ex4w`, `sharpe_mom_26w`, `consistency_mom_26w`), clipped ±3.
- **Universe:** close ≥₹20, 13-week median traded value ≥₹1cr, listed ≥26 weeks, PIT.
- **Long leg:** sector-balanced top-40% (composite ≥ sector's 60th percentile to enter, ≥40th to stay —
  hysteresis halves turnover vs. full rebalance). ~198 names currently.
- **Short leg:** bottom-quintile ∩ F&O-eligible (top-190 by 13w ADV), 0.5× long gross, ~27 names. Net
  book beta ≈0.37. **This is risk control, not alpha** — per Gen-5 F02/F08, its value is covariance
  reduction with the long book (corr=−0.88), not standalone return. Do not evaluate it on its own P&L.
- **G-05 crash overlay:** ON. Regime=CRASH (trailing 13wk universe return <−8%, PIT) rotates the long leg
  to low-beta names for that rebalance. Marginally additive, never hurts (Gen-5 F05).
- **Rebalance:** MONTHLY (4th Friday). **Weekly rebalance is forbidden** — destroys the edge via turnover.
- **Pre-lockbox profile:** CAGR 11.9%, Sharpe 0.94, maxDD −48%, turnover 116%/yr, capacity ~₹500cr
  (F&O short-leg liquidity is the binding constraint).

### Sleeve 2 — Sector Rotation, 20% of book capital
- **Signal:** 13-week trailing sector return, 7 GICS sectors, PIT.
- **Book:** long top-2 / short bottom-2 sectors, monthly rebalance.
- **Role:** drawdown reduction, not return — standalone Sharpe 0.56, deliberately small allocation.
  **Do not over-allocate to this sleeve based on any single good period.**

### Combination
80/20 by capital (held-out-optimal). Combined held-out (2020–2025) Sharpe ~0.89. Evaluate QUARTERLY,
track sleeves separately. **Kill/de-size triggers** (pre-registered, not discretionary): rolling 8wk
live long-book IC <0 for 2 consecutive quarters → pause; drawdown breaches pre-lockbox maxDD by >10%
absolute → cut sizing; Sleeve-2 live Sharpe <0 over a full year → drop it.

---

## 2. The Delivery Overlay (newly recovered, 2026-07-25)

**Status: recovered, validated, NOT YET integrated into the frozen book above** — this is the one open
item before the overlay can be formally added to Section 1's spec. See
`results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md` for the full dossier; this section is the operating
summary.

- **What it is:** `ADD_nonfno_tail` construction — the existing momentum long book PLUS a small,
  additive tail of high-delivery non-F&O names. Long-only, no shorting infrastructure required.
- **Correctness gate:** reproduces the original 2026 certification exactly (net Sharpe @20bps: 0.698
  control, 0.767 with overlay).
- **Capacity:** deployable ₹5 lakh through ₹100 crore+. **Peak risk-adjusted efficiency ₹2–25 crore**
  (net Sharpe ~0.79) — NOT at the smallest capital tested, and NOT degrading to a cliff even at ₹500cr
  (still 0.66). Use the real per-trade cost model (`src/pnl/indian_cost_model.py`), not a flat-bps
  assumption, when sizing this overlay at any specific AUM.
- **Turnover:** low (0.20–0.21 weekly), does not materially add to the book's turnover burden.
- **Correlation to momentum:** **0.14 is SIGNAL orthogonality (ranking vs ranking), NOT sleeve-return
  correlation.** The realised correlation of the two long-only sleeves' *returns* is **+0.842** — two
  long-only Indian equity books share market beta whatever their signals do. **Do not quote 0.14 as a
  diversification argument.** [G10 2026-07-31]
- **~~Open item before formal integration~~ — CLOSED 2026-07-31. DO NOT INTEGRATE.** Both architectures
  have now been tested and neither promotes:
  - as an **overlay** on the certified book — G8-09: +0.066 Sharpe, t = 0.60, and establishing it would
    need 59 years of delivery data. Do-not-integrate.
  - as an **independently-sized sleeve** — Gen-10 T1-06: at Sleeve B's own CI lower bound the optimal
    weight is **zero at every capital band**; on the point estimate it falls to zero by ₹25cr. The
    blend's case rests on a Sharpe advantage of +0.335 that is **not significant** (t = +1.60).
  Delivery remains a validated, capacity-bound *signal*. What is closed is the claim that adding it to
  the book helps. See `results/gen10/T1-06/`.

---

## 3. Risk Architecture

| Component | Role | Evidence |
|---|---|---|
| Short leg (0.5× long gross, F&O-eligible bottom-quintile) | Risk control via covariance reduction with the long book, NOT alpha | Gen-5 F02, F08 (corr=−0.88 with momentum) |
| G-05 crash overlay | Bottom-of-drawdown protection, near-zero cost | Gen-5 F05 (+0.037 Sharpe, ~0 return cost) |
| Sector rotation (Sleeve 2) | Drawdown reduction across the combined book | `FROZEN_SPEC.md` |
| Trade-band hysteresis | Turnover control (halves turnover vs. full rebalance) | `FROZEN_SPEC.md` |
| Kill/de-size triggers | Pre-registered, non-discretionary risk circuit-breakers | `FROZEN_SPEC.md` Section "Kill / de-size criteria" |

**What is explicitly NOT part of the risk architecture** (tested, not adopted): dynamic short-budget
timing, dynamic gross-exposure timing, dynamic sleeve reallocation — all three TERMINATED_BY_GATE in
Gen-5 (F10–F12), insufficient realizable skill after honest degradation. Do not reintroduce any of these
without new, specific evidence per the burden-of-proof principle.

---

## 4. Capacity Curves

| Book component | Capacity ceiling | Binding constraint | Source |
|---|---|---|---|
| Config-4 (Sleeve 1, momentum) | Not binding below ~₹5,000–10,000cr; 50%-of-ceiling break bracketed ₹5,000–10,000cr | Market-impact slippage, not statutory fees, dominates at scale (58.5%→84.1% of cost, ₹100cr→₹2,500cr) | Gen-5 F19/F20/F22 (G5-07A, G5-D01) |
| Delivery overlay | Peak efficiency ₹2–25cr; usable ₹5L–₹100cr+; degrades gracefully to ₹500cr | Real per-trade cost (`IndianEquityCostModel`) — brokerage-cap benefit vs. market-impact tradeoff | `results/ARP_DELIVERY/` |
| Liquidity itself | Time-varying — Indian market liquidity has grown ~7× since the GFC (median ADV ₹9.6cr 2008 → ₹68.2cr 2024–25) | N/A — recalibrate capacity assumptions against CURRENT liquidity, never a historical average | Gen-5 F20 (A6) |

**Combined book capacity is not simply the sum of the two components' individual ceilings** — no
portfolio-level combined capacity test has been run (open item, not yet a number to operate against).

---

## 5. Execution Rules

- **Cost model:** `src/pnl/indian_cost_model.IndianEquityCostModel` — brokerage (0.03%, capped ₹20/trade)
  + STT (0.1% both sides) + stamp duty (0.015%, buy only) + GST (18% on brokerage/exchange/SEBI) +
  slippage (5bps floor + √-impact vs. ADV). This is the ONLY cost model to use for any capacity or
  P&L-net-of-cost estimate in this programme — do not substitute a flat-bps assumption for anything
  beyond a first-pass sanity check.
- **Participation:** cap at 5% of ADV per trade (Sleeve-1 convention, `FROZEN_SPEC.md`). Above this,
  slippage estimates from the sqrt-impact model become unreliable.
- **Slippage dominates statutory cost at scale** — cost-reduction effort belongs in execution quality
  (better fills, smarter scheduling), not fee negotiation (Gen-5 F22).
- **Execution delay is largely tolerable** for the frozen book's low-turnover construction — 0–3 week
  delay showed no material Sharpe effect (Gen-5 F23). This does NOT extend to the Delivery overlay or any
  future higher-turnover addition without its own test.
- **What was tested and found NOT to help:** memory-conditional rebalance cadence (AEP Paper C,
  Sub-studies 2+3) — a clean null, essentially zero Sharpe difference vs. fixed weekly/monthly cadence.
  Do not build adaptive rebalancing logic on the current evidence base.
- **What was tested and shows a real but unvalidated lead:** liquidity-regime-conditional position sizing
  (AEP Paper C, Q3 — Sharpe 0.692→0.727, vol −23%). **Flagged, not adopted** — has not passed the same
  sensitivity/definition-robustness testing that correctly killed the analogous volatility-sizing idea
  (Paper B). Do not operate this rule until it clears that bar.

---

## 6. Rebalancing

**MONTHLY, 4th Friday, both sleeves.** This is binding, not a default — weekly rebalance is explicitly
forbidden for Sleeve 1 (destroys the edge via turnover). No adaptive/conditional rebalance-frequency
logic is currently validated (Section 5) — the fixed monthly cadence is the entire rule.

---

## 7. Maintenance Schedule

| Cadence | Action |
|---|---|
| Monthly | Execute the 4th-Friday rebalance for both sleeves, per `FROZEN_SPEC.md`. |
| Quarterly | Review sleeve-level attribution separately (momentum vs. sector rotation). Check kill/de-size triggers. |
| Annually | Re-check Sleeve-2's live Sharpe against the <0 kill trigger. Re-verify capacity assumptions against current liquidity (Section 4's 7× growth note — do not use a stale ADV baseline). |
| On any drawdown breach | Compare against the pre-lockbox maxDD +10% absolute trigger; cut sizing if breached — do not wait for the next scheduled review. |
| Before any parameter change | **Full re-certification + a fresh lockbox is required.** Per `FROZEN_SPEC.md`: "No discretionary overrides. No parameter tuning. Live results + fresh lockbox are the only inputs that may change this spec." |

---

## 8. Operating Procedures — what to do when...

- **...a sleeve underperforms for a quarter:** do nothing outside the pre-registered kill/de-size
  triggers (Section 3). The evaluation cadence is quarterly by design specifically to prevent reacting to
  single bad months.
- **...someone proposes a new dynamic-timing overlay:** check `MONOGRAPH.md` Part III and
  `PROGRAMME_VALIDATION.md` Section 2 first — three dynamic-timing levers (short budget, gross exposure,
  sleeve reallocation) were already tested and TERMINATED_BY_GATE. A new proposal needs a specific,
  evidenced reason it differs (state/action/horizon), not just a new implementation of the same idea.
- **...someone wants to add the Delivery overlay to the live book:** **don't.** The open item is
  closed as of 2026-07-31 — both the overlay (G8-09) and the independently-sized sleeve (Gen-10 T1-06)
  were tested and neither promotes. A new proposal needs a genuinely different construction, not a
  re-run. And note the 0.14 correlation often cited in its favour is signal orthogonality; the sleeves'
  returns correlate at 0.84.
- **...someone wants to deploy an AEP engineering rule (sizing, filtering, timing):** don't. Per
  `PROGRAMME_VALIDATION.md` Section 4, zero AEP engineering rules cleared the validation bar. **The
  liquidity-sizing lead is no longer even a lead** — Gen-10 T0-02 supplied the significance test AEP
  never ran: paired **t = +0.50**, 0.18x its own detection floor, costing 3.26 %/yr of return; it keys
  off regime labels rather than any liquidity measurement, and it is Gen-5 G5-05A rediscovered.
  See `archive_addenda/GEN10_ADDENDUM_002.md`.
- **...new capital needs to be deployed:** check Section 4's capacity curves against current AUM plans,
  and recalibrate against CURRENT market liquidity, not the historical baseline used in Gen-5's original
  capacity study.
- **...someone wants "just one more experiment":** read `PROGRAMME_VALIDATION.md`'s recommendation
  section before proceeding. The research programme is frozen; new work needs new evidence or a
  genuinely new question, not incremental iteration on the existing architecture.

---
**Frozen 2026-07-25, alongside `MONOGRAPH.md` (Volume I) and `PROGRAMME_VALIDATION.md`.**
