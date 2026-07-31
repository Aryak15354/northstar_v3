# T1-16 — Mop-up: G2-B03b and the Rates Channel. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T0-02 (which logged G2-B03b), results/gen10/T1-10 (rates channel)
Artifacts:    t1_16_data.json. Script: scripts/gen10/t1_16_mopup_g2b03b_and_rates.py
```

**Outcome: both close negative — and the rates channel closes for a completely different reason
than T1-10 recorded.** T1-10 said US 10Y was untestable because of short history. It is untestable
because its pre-registered receiver sector has **ten stocks**. Fixed and run, it is null.

---

## 1. G2-B03b — order-win announcements → revenue visibility: REJECTED

The one "research-incomplete" registry row the remediation plan missed. Archived INCONCLUSIVE with
**no t-statistic recorded at all**.

| spec | non-null | weeks | pooled IC | pooled t | **corrected IC** | **corrected t** | composition share |
|---|---|---|---|---|---|---|---|
| `order_win_flag_30d` | 44,093 | 130 | — | — | — | — | binary, only 2 values — not testable |
| `order_win_flag_30d_cs_z` | 83,642 | 222 | −0.0121 | −1.68 | **−0.0049** | **−0.77** | **+59%** |
| `order_win_count_90d_cs_z` | 83,642 | 222 | −0.0052 | −0.71 | **−0.0028** | **−0.41** | **+46%** |

0 of 2 clear BY at q=0.05. Best corrected |t| = 0.77.

Two things worth noting beyond the null. **The sign is negative** — order wins associate with *lower*
forward returns, the opposite of the "revenue visibility" hypothesis. And **46–59% of even that weak
pooled IC is the universe-composition artifact** from T0-03; the signal's coverage straddles both
universes, exactly the profile that predicts exposure. **REJECTED.**

## 2. The rates channel — T1-10's diagnosis was wrong

T1-10 recorded: *"US 10Y was untestable (440 weeks of history against the others' 1,067), so the
duration/discount-rate channel needs longer rates history rather than a better design."*

**That is not why it failed.** Re-running the exposure window at 104w/52w, 52w/26w and 26w/13w gives
`^TNX` **n = 0 usable dates at every setting** — history length is not the binding constraint. The
actual constraint is the receiver:

```
median names per date, 2018+ (the ^TNX era)
  Real Estate               10       <- the pre-registered channel receiver
  Industrials               11
  Energy                    32
  Materials                 41
  Information Technology    91
  Consumer Goods           103

weeks where Real Estate has >= 30 names:  0 / 1123
weeks where Real Estate has >= 15 names:  0 / 1123
```

**Real Estate never reaches even 15 names.** A cross-sectional regression inside it was never going to
run at any history length. Longer `^TNX` data would not have helped.

### The declared amendment, and the result

Widening the receiver to **Real Estate + Industrials** (both duration-sensitive, 13 names median) and
lowering the minimum from 30 to 15 makes it testable. **This is a post-hoc design change and is
labelled as one** — it weakens channel specificity, which was the point of T1-10's design, so the
complement arm is reported alongside:

| arm | lag 1 | lag 2 | lag 4 |
|---|---|---|---|
| channel (RE + Industrials), n=314 | t = +0.41 | t = −1.45 | t = −0.42 |
| complement, n=414 | t = −0.72 | t = +0.08 | t = −1.02 |

**Null.** Best |t| = 1.45, nothing near the pre-registered r = 0.11 floor, no channel/complement
separation. The duration/discount-rate channel is now **covered**, not formally open.

### A second, incidental finding: DXY lag-2 was a window artifact

T1-10 flagged `DX-Y.NYB` at lag 2 as its one "channel-specific candidate" (t = −2.51, not BY-clean).
Across exposure windows it is unstable:

```
104w/52w   t = -3.07   (p = 0.0023)
 52w/26w   t = -0.80
 26w/13w   t = -0.51
```

A result that moves from −3.07 to −0.51 on a nuisance parameter is not an effect. **T1-10's single
candidate is retired**, which makes its null cleaner rather than weaker.

## 3. Findings

**G10-F47 — G2-B03b is rejected.** Corrected |t| ≤ 0.77 across both testable specs, 0/2 BY-clean,
wrong-signed against its own hypothesis, and 46–59% of the pooled IC is composition artifact. The last
un-tested row in ARP's research-incomplete bucket is now closed.

**G10-F48 — T1-10's rates channel was blocked by receiver size, not history length.** `Real Estate`
has a median of 10 names per date and never reaches 15. This corrects T1-10 §6's stated threat to
validity, which recommended acquiring longer rates history — that would not have helped.

**G10-F49 — with the receiver widened, the rates channel is null, and T1-10's one surviving candidate
was a window artifact.** Best channel |t| = 1.45 with no complement separation; DXY lag-2 swings
−3.07 → −0.51 across exposure windows. **Gen-7's transmission question is now closed with no
uncovered channel and no outstanding candidate.**

## 4. Threats to validity

- **The receiver widening is post-hoc.** Real Estate + Industrials is defensible on duration-sensitivity
  grounds, but it was not pre-registered and it dilutes the channel-specificity test the original
  contract was built around. It is reported as an amendment, not as the original design.
- 13 names per date is thin for a cross-sectional slope even at `min_names = 15`; per-date estimates
  are noisy and the NW interval is correspondingly wide. This is a genuine "cannot resolve a small
  effect" limit, distinct from the "cannot run at all" limit it replaces.
- `order_win_flag_30d` is binary with 2,106 non-zero rows and was not testable as a cross-sectional
  rank signal. Its z-scored and count variants were.
