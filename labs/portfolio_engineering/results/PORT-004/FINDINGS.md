# PORT-004 — Overlay Extension to Sleeve-2 and the Combined Book: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Portfolio Engineering
Verdict:            INCONCLUSIVE overall (registry) -- a genuinely mixed result across 4 sub-tests,
                    see below; do not read "INCONCLUSIVE" as "nothing happened"
```

Artifacts: `port004_data.json`. Script: `labs/portfolio_engineering/protocols/run_port_004.py`.
Sleeve-2 rebuilt via `run_sector_cert_signal.py`'s own `rot(piv, 13, 2, 4)` — FROZEN_SPEC's exact
parameters, unchanged.

---

## Baselines (sanity check against FROZEN_SPEC)

| | CAGR | Sharpe | maxDD |
|---|---|---|---|
| Sleeve-2 alone (pre-lockbox) | +9.1% | +0.619 | −21.8% |
| Combined 80/20 book (pre-lockbox) | +11.2% | +1.027 | −38.7% |

Sleeve-2's standalone Sharpe (0.619) is in the same ballpark as `FROZEN_SPEC.md`'s own documented
0.56 — a reasonable match given this reconstruction uses `target_1w`-based returns directly rather
than the fully faithful certified pipeline, disclosed as an approximation in the pre-registration.

## Result — four sub-tests, genuinely mixed

| | Sharpe delta / maxDD improve | Verdict |
|---|---|---|
| Sleeve-2, vol-targeting | +0.064 (below +0.15 bar) | **REJECTED** |
| Sleeve-2, drawdown de-gross | +2.2pp maxDD for +1.7pp CAGR cost | **VALIDATED** (marginal) |
| Combined book, vol-targeting | +0.135 (below +0.15 bar, closer) | **REJECTED** |
| Combined book, drawdown de-gross | +9.2pp maxDD for only +0.4pp CAGR cost | **VALIDATED** (strong) |

**Vol-targeting does not generalize from Sleeve-1.** PORT-001 found a clear +0.179 Sharpe delta on
Sleeve-1 alone; here it lands at +0.064 (Sleeve-2) and +0.135 (combined) — real improvements in both
cases, directionally consistent, but **neither clears the pre-registered +0.15 bar**. The most likely
reason: Sleeve-2's own volatility dynamics differ from Sleeve-1's (lower baseline vol, 14.1% vs
Sleeve-1's target), and the combined book's diversification already dampens some of the tail-vol
clustering that made Sleeve-1's overlay valuable on its own. This is reported as REJECTED for these
two bases specifically — not as evidence against PORT-001's own Sleeve-1 finding, which stands.

**Drawdown de-gross generalizes well, and works especially well on the combined book.** Sleeve-2
alone gets a modest, marginally-favorable result (2.2pp maxDD improvement for 1.7pp CAGR cost —
barely clears the gate). The combined book result is the strongest drawdown result across all of
Portfolio Engineering's work this session: **9.2 percentage points of maxDD improvement for only 0.4
points of CAGR cost**, concentrated in the GFC window (−38.7% → not shown per-sub-window baseline,
overlay GFC drawdown −27.4%). This is intuitive: the combined book's larger, more persistent
drawdowns (from Sleeve-1 dominating at 80% weight) are exactly what a running-peak-triggered de-gross
rule is built to catch.

## Why this closes INCONCLUSIVE at the registry level, honestly

Per the pre-registration, each of the 4 sub-tests is closed on its own terms, not averaged. The
overall registry verdict (INCONCLUSIVE, since the four don't unanimously agree) is a **summary
label, not a finding** — the actual information content is in the four rows above. **The practical
takeaway for a future capital-allocation decision**: the drawdown de-gross overlay on the *combined*
book is the standout result in this whole overlay programme (PORT-001 through PORT-004) — 9.2pp of
tail protection at almost no return cost — and is the strongest candidate for actual consideration,
should this book ever move beyond paper trading. Vol-targeting remains validated only for Sleeve-1
alone; it should not be assumed to extend to the sector-rotation sleeve or the combined book without
further work (e.g., a Sleeve-2-specific target-vol calibration, not attempted here).
