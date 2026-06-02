# Northstar V3 Formula And Calculation Audit

Date: 2026-03-21

## 1. Scope And Audit Method

This audit was built in two layers:

1. Canonical runtime tracing.
   The live path was traced from the trading-day/orchestrator scripts into the canonical state sync and then into the state, governor, scoring, risk, valuation, execution, options, and PnL modules.
2. Exhaustive calculation inventory.
   A repo-wide AST scan was run across `src`, `scripts`, `run.py`, `run_daily_v3.py`, and `run_complete_v3_system.py` to identify calculation-bearing functions and modules.

Coverage numbers from the machine inventory:

- Files scanned: `1288`
- Calculation-bearing functions detected: `9423`
- Highest-volume categories: `scripts=2612`, `validation=1205`, `intelligence=848`, `dashboard=739`, `research=430`, `options=385`, `cohesion=331`, `volatility=296`, `operation=288`, `core=273`
- Highest-volume stages: `orchestration=2632`, `reporting_validation=2075`, `allocation_runtime=1266`, `risk_execution_options=758`, `state_control=661`, `scoring_research=472`, `feature_engineering=323`, `ingestion=231`, `valuation=116`

Machine appendices created alongside this report:

- `audit/formula_inventory_2026-03-21.json`
- `audit/formula_inventory_summary_2026-03-21.json`
- `audit/formula_inventory_2026-03-21.csv`

This report is the human-readable audit. The JSON/CSV appendices are the exhaustive index.

## 2. Canonical Execution Order

The calculation stack is not flat. The important runtime order is:

1. `scripts/run_trading_day_orchestrator.py`
   Runs the intraday loops and end-of-day/full-stack refresh.
2. `scripts/run_complete_v3_system.py::sync_canonical_state`
   Builds or refreshes the canonical `UnifiedState`.
3. Ingestion health and lineage checks
   Decide whether upstream data is fresh enough to trust.
4. Sentiment state computation
   Produces sentiment regime, trend, z-score, momentum, freshness.
5. Alternative-data pipeline
   Produces GST/power/credit/smart-money/promoter-risk state plus a composite economic activity regime.
6. Market state spine
   Produces macro score, market health, stress, risk-on probability, allowed exposure, sentiment/brain overlays.
7. PnL and options runtime snapshots
   Load drawdown, NAV, options Greeks, options risk utilization.
8. Portfolio governor
   Converts regime state and risk state into top-level equity/options/cash fractions.
9. Scoring and overlays
   Produces ticker rankings and live score modifications.
10. Allocation and runtime risk enforcement
   Kelly weights, hard-cap budget checks, emergency brakes, convexity vetoes.
11. Execution realism and ledger accounting
   Impact model, transaction-cost model, mark-to-market, and PnL persistence.
12. Valuation and forensic subsystems
   Fundamental fair value, owner earnings, DCF, accrual/quality scoring, posterior valuation gap.

If you want to debug “what affects what,” the most important dependency chain is:

`ingestion freshness -> sentiment/alternative state -> market state -> governor capital structure -> scoring/allocation -> risk budgets/execution -> ledger/PnL`

There is also a valuation side-chain:

`financial statements + alternative credit/pledge data -> owner earnings + DCF + forensic quality -> valuation posterior gap -> Kelly allocator`

## 3. Stage-By-Stage Formula Audit

## 3.1 State Sync, Health, Runtime Snapshots

Primary file: `scripts/run_complete_v3_system.py`

### 3.1.1 System health snapshot

Source: `scripts/run_complete_v3_system.py`

Formulas:

- `fresh_ratio = fresh / total`
- `availability_ratio = available / total`
- `overall_health_score = 0.7 * fresh_ratio + 0.3 * availability_ratio`
- Health labels:
  - `overall_health_score >= 0.85 -> healthy`
  - `overall_health_score >= 0.55 -> degraded`
  - else `critical`

Why it matters:

- This is the first quality gate on whether later calculations are operating on trustworthy data.
- It affects health narratives and operator visibility.

### 3.1.2 Ratio normalization and exposure normalization

Source: `scripts/run_complete_v3_system.py`

Rule:

- `_normalize_ratio` divides by `100` when a ratio-like value is greater than `1.0`, then clips into `[0, 1]`

Why it matters:

- This is one of the points where percentage-point fields and decimal-ratio fields get mixed.
- It directly affects how exposure-like fields land in unified state.

### 3.1.3 Strategy-weight entropy

Source: `scripts/run_complete_v3_system.py`

Formula:

- Convert absolute weights into probabilities `p_i`
- Compute Shannon entropy: `entropy = -sum(p_i * log(p_i))`

Why it matters:

- This is used as a concentration/diversity summary of strategy allocation.

### 3.1.4 Options runtime snapshot

Source: `scripts/run_complete_v3_system.py:618-684`

Formulas:

- Position Greek aggregation:
  - `net_delta = sum(delta * quantity)`
  - `net_gamma = sum(gamma * quantity)`
  - `net_vega = sum(vega * quantity)`
  - `net_theta = sum(theta * quantity)`
- Premium at risk:
  - `options_premium_at_risk = max(risk_cap_value - risk_remaining, 0.0)`
- Margin utilization:
  - `options_margin_utilization = 1.0 - (risk_remaining / risk_cap_value)` when `risk_cap_value > 0`

Downstream impact:

- These feed unified risk state and later runtime risk checks.

### 3.1.5 Processed risk materialization

Source: `scripts/run_complete_v3_system.py:699-725`

Mappings:

- `volatility <- state.market.market_stress`
- `correlation <- state.market.correlation`
- `var <- state.risk.overall_risk_level`
- `exposure_multiplier <- state.risk.exposure_multiplier`
- `options_margin_utilization <- state.risk.options_margin_utilization`

Why it matters:

- This is the bridge from canonical unified state into legacy risk-state consumers.

## 3.2 Sentiment State

Primary files:

- `src/sentiment/sentiment_state.py`
- `src/sentiment/sentiment_regime.py`

### 3.2.1 Freshness gating

Source: `src/sentiment/sentiment_state.py:109-149`, `256-288`

Rules:

- If `registry.sentiment.is_sentiment_fresh(as_of_date)` is false, sentiment state becomes unavailable.
- Final “overall fresh” condition requires all of the following:
  - market sentiment fresh
  - market sentiment lag `<= 3` days
  - company sentiment available
  - companies covered `> 0`
  - company sentiment lag `<= 7` days

Downstream impact:

- If this gate fails, the governor and market-state sentiment adjustments degrade to unavailable/neutral behavior.

### 3.2.2 Regime classification

Source: `src/sentiment/sentiment_regime.py:66-232`

Transform:

- Smooth the sentiment series using:
  - `smoothed = sentiment_series.ewm(span=smoothing_days, adjust=False).mean()`
- Treat the latest smoothed value as the classifier input.

Thresholds:

- `< -2.0 -> PANIC`
- `< -0.5 -> FEAR`
- `< 0.5 -> NEUTRAL`
- `< 2.0 -> OPTIMISM`
- else `EUPHORIA`

Hysteresis:

- Transition requires clearing the target threshold by `0.25` buffer.

Confidence:

- Confidence rises with distance from the nearest regime boundary.

Trend:

- `ema_7d - ema_30d`
- `> trend_threshold -> IMPROVING`
- `< -trend_threshold -> DETERIORATING`
- else `STABLE`

Downstream impact:

- Feeds sentiment regime, crisis flag, and caution score in the governor.

### 3.2.3 Z-score, momentum, and volatility

Source: `src/sentiment/sentiment_state.py:183-221`

Formulas:

- Z-score:
  - `mean = rolling_252_mean`
  - `std = rolling_252_std`
  - `zscore = (latest - mean) / std`
- 1-week momentum:
  - `momentum_1w = rolling_7_mean - rolling_30_mean`
- 1-month momentum:
  - `momentum_1m = rolling_30_mean - rolling_90_mean`
- Sentiment volatility:
  - `volatility = rolling_30_std`
- Crisis signal:
  - true when regime is `PANIC` or `EUPHORIA`
- Price/sentiment divergence:
  - if price direction and sentiment direction disagree:
  - `divergence = abs(zscore) * 0.5`

Downstream impact:

- The z-score and momentum describe the intensity and direction of narrative pressure.
- The crisis flag and regime feed the governor.

## 3.3 Alternative Data State

Primary files:

- `src/alternative_data/alternative_feature_block.py`
- `src/alternative_data/alternative_pipeline_runner.py`

### 3.3.1 Freshness thresholds

Source: `src/alternative_data/alternative_pipeline_runner.py`

Thresholds:

- GST: `1.5` months
- Power: `3` days
- Credit ratings: `7` days
- Bulk deals: `2` days
- Promoter pledges: `100` days

Why it matters:

- Even correct formulas are ignored or downweighted if source freshness fails.

### 3.3.2 GST features

Source: `src/alternative_data/alternative_feature_block.py:121-166`

Formulas:

- Trend acceleration:
  - `trend_accel = recent_mom[-1] - recent_mom[0]`
- Robust z-score:
  - `z = (value - median) / (1.4826 * MAD)`
  - clipped to `[-3, 3]`
- Regime numeric:
  - `yoy > 0.10 and deviation > 0.5 -> 2`
  - `yoy > 0.05 and deviation > 0 -> 1`
  - `yoy < -0.05 and deviation < -0.5 -> -2`
  - `yoy < 0 or deviation < -0.25 -> -1`
  - else `0`

Pipeline mapping:

- Numeric regime mapped into `CONTRACTION/SLOWING/NEUTRAL/RECOVERING/EXPANSION`
- Trend direction:
  - `trend_accel > 0.5 -> ACCELERATING`
  - `trend_accel < -0.5 -> DECELERATING`
  - else `STABLE`

Downstream impact:

- GST state feeds the composite economic activity regime used by the governor.

### 3.3.3 Power features

Source: `src/alternative_data/alternative_feature_block.py`, `src/alternative_data/alternative_pipeline_runner.py:440-465`

Formulas:

- Latest momentum change:
  - `mom_change = pct_change(power_consumption)`
- Industrial proxy:
  - `0.5 * clip(yoy_growth * 10, -1, 1)`
  - `+ 0.3 * clip(deviation, -1, 1)`
  - `+ 0.2 * clip(mom_change * 20, -1, 1)`
  - final result clipped to `[-1, 1]`
- Regime mapping from industrial proxy:
  - `< -1 -> CONTRACTION`
  - `< -0.5 -> SLOWING`
  - `< 0.5 -> NEUTRAL`
  - `< 1 -> RECOVERING`
  - else `EXPANSION`
- Power score on 0-100 scale:
  - `industrial_proxy_score = industrial_proxy * 50 + 50`

Downstream impact:

- Power state is the second half of the composite economic activity regime.

### 3.3.4 Credit-market features

Source: `src/alternative_data/alternative_feature_block.py:254-315`

Formulas:

- `upgrade_ratio = upgrades / (upgrades + downgrades)` else `0.5`
- `net_momentum = (upgrades - downgrades) / max(total_actions, 1)`
- `stress_flag = 1.0 if upgrade_ratio < 0.4 else 0.0`

Additional state enrichments:

- Distressed company count from low-quality/distress ratings
- Recent downgrade count over trailing `30` days

Downstream impact:

- Should feed the unified alternative-data credit state and downstream valuation/risk bridges.

### 3.3.5 Bulk-deal / smart-money features

Source: `src/alternative_data/alternative_feature_block.py:317-377`

Formulas:

- `net_flow_normalized = total_net_flow / max(total_volume, 1)`
- `breadth = positive_count / len(bulk_df)`
- Signal numeric:
  - `net_flow > 0.3 and breadth > 0.6 -> 2`
  - `net_flow > 0.1 and breadth > 0.5 -> 1`
  - `net_flow < -0.3 and breadth < 0.4 -> -2`
  - `net_flow < -0.1 and breadth < 0.5 -> -1`
  - else `0`

Intended downstream impact:

- This should become `STRONG/MILD accumulation` or `STRONG/MILD distribution` in smart-money state.

### 3.3.6 Promoter-pledge features

Source: `src/alternative_data/alternative_feature_block.py`

Formulas:

- Market pledge average:
  - mean latest `PledgePct`
- Trend:
  - `(market_avg - old_avg) / max(old_avg, 1)`
- Systemic risk:
  - true if high-pledge ratio `> 0.25`
- Company-level pledge risk:
  - `level_risk = clip(current / 100, 0, 1)`
  - `trend_risk = clip((qoq + yoy) / 50, 0, 1)`
  - `risk_score = 0.6 * level_risk + 0.4 * trend_risk`, clipped to `[0, 1]`

Downstream impact:

- Used in alternative-data state and valuation distress bridge.

### 3.3.7 Composite economic activity regime

Source: `src/alternative_data/alternative_pipeline_runner.py:329-396`

Formulas:

- Regime-to-score mapping:
  - `CONTRACTION=0`
  - `SLOWING=1`
  - `NEUTRAL=2`
  - `RECOVERING=3`
  - `EXPANSION=4`
  - `UNAVAILABLE=2`
- Composite:
  - `composite_score = (gst_regime_score + power_regime_score) / 2`
- Final regime:
  - `<= 0.5 -> CONTRACTION`
  - `<= 1.5 -> SLOWING`
  - `<= 2.5 -> NEUTRAL`
  - `<= 3.5 -> RECOVERING`
  - else `EXPANSION`

Downstream impact:

- This is the alternative-data input used by the portfolio governor caution score.

## 3.4 Market State Spine

Primary file: `src/state/market_state.py`

### 3.4.1 Macro state

Source: `src/state/market_state.py:223-268`

Formulas:

- `macro_momentum = macro_score - macro_20d_avg`
- Confidence:
  - base confidence from source quality
  - freshness penalty `= min(0.5, data_age / 30.0)`
  - `confidence = max(0.3, base_confidence - freshness_penalty)`

Downstream impact:

- Feeds risk-on probability and allowed exposure.

### 3.4.2 Market health

Source: `src/state/market_state.py:270-396`

Formulas:

- `breadth_pct = positive_sectors / total_sectors * 100`
- `participation = mean(abs(sector_changes))`
- `participation_score = clamp(participation * 10, 5, 100)`
- `correlation = 1 - std(sector_changes) / (mean(abs(sector_changes)) + 1e-6)`, clipped to `[0, 1]`
- `health_score = 0.4 * (breadth_pct / 100) + 0.3 * (participation_score / 100) + 0.3 * (1 - correlation)`

Downstream impact:

- Health score is a core input into risk-on probability and allowed exposure.

### 3.4.3 Volatility state

Source: `src/state/market_state.py:398-433`

Rules:

- If realized vol is below `1.0`, multiply by `100` to interpret it as percentage points.
- Regimes:
  - `> 30 -> extreme`
  - `> 25 -> high`
  - `> 20 -> elevated`
  - `> 15 -> normal`
  - else `low`
- Continuous stress:
  - `stress_level = clip((realized_vol - 10.0) / 25.0, 0.05, 0.95)`

Downstream impact:

- Stress is a major brake in the exposure formula and later risk overlays.

### 3.4.4 Opportunity density

Source: `src/state/market_state.py:435-467`

Formula:

- Compute the 75th percentile of `mispricing` and `confirmation`
- Count high-conviction names where both metrics exceed their 75th percentile
- `opportunity_density = high_conviction / total_universe`

Downstream impact:

- Opportunity density modestly increases or decreases allowed exposure.

### 3.4.5 Liquidity state

Source: `src/state/market_state.py:469-483`

Rules:

- `macro_score > 0.5 and breadth_pct > 60 -> risk-on`
- `macro_score < -0.5 or breadth_pct < 30 -> risk-off`
- else `neutral`

### 3.4.6 Risk-on probability

Source: `src/state/market_state.py:485-499`

Formula:

- `macro_factor = clip((macro_score + 2) / 4, 0, 1)`
- `health_factor = health_score`
- `vol_factor = 1 - stress_level`
- `risk_on_probability = 0.4 * macro_factor + 0.4 * health_factor + 0.2 * vol_factor`

Downstream impact:

- This is one of the central top-down portfolio signals.

### 3.4.7 Allowed exposure

Source: `src/state/market_state.py:500-537`

Base regime exposure table:

- `boom -> 90`
- `expansion -> 70`
- `late expansion -> 55`
- `neutral -> 40`
- `slowdown -> 25`
- `crisis -> 10`

Adjustment chain:

- `risk_on_adj = clip(0.70 + risk_on_prob * 0.60, 0.65, 1.20)`
- `momentum_adj = clip(1 + macro_momentum * 0.08, 0.80, 1.15)`
- `health_adj = clip(0.65 + health_score * 0.55, 0.65, 1.20)`
- `vol_adj = clip(1 - stress_level * 0.45, 0.60, 1.05)`
- `opp_signal = clip(opportunity_density / 0.18, 0, 1)`
- `opp_adj = clip(0.85 + opp_signal * 0.25, 0.85, 1.10)`

Final formula:

- `allowed_exposure = base_exposure * risk_on_adj * momentum_adj * health_adj * vol_adj * opp_adj`
- Hard-clipped to `5 .. 95`

Downstream impact:

- This is the most important top-down portfolio exposure cap before later brakes and capital-structure logic.

### 3.4.8 Sentiment integration into market state

Source: `src/state/market_state.py:539-662`

Derived signal:

- If `news_signal` is missing, it is inferred from a weighted mix of deltas/counts.

Headwind build:

- Add capped contributions from:
  - event shock
  - negative polarity
  - uncertainty
  - narrative conflict
  - news signal
  - negative company count
  - event count
  - alert level

Transform:

- `sentiment_headwind = 0.75 * tanh(headwind / 0.75)`
- `risk_multiplier = clip(1 - 0.85 * headwind, 0.40, 1.10)`
- `exposure_multiplier = clip(1 - 0.70 * headwind, 0.45, 1.10)`

Tailwind:

- Small positive adjustment only when:
  - `event_shock < 0.25`
  - polarity positive
  - uncertainty low
  - conflict low

Final adjusted fields:

- `adjusted_risk_on = clip(base_risk_on * risk_multiplier, 0, 1)`
- `adjusted_exposure = clip(base_exposure * exposure_multiplier, 5, 95)`
- `confidence_penalty = min(0.18, event_shock * 0.12 + uncertainty * 0.08 + conflict * 0.05)` with extra penalty for `high/critical` alerts

Downstream impact:

- This is the first overlay that can materially pull down exposure even when macro/market-health remain constructive.

### 3.4.9 Market Brain integration

Source: `src/state/market_state.py:726-890`

Fallback formulas when brain outputs are missing:

- `dynamic_fallback_multiplier = clip(1 - 0.35 * stress + 0.20 * (risk_on - 0.5), 0.30, 1.10)`
- `blended_fallback_multiplier = clip(0.6 * base_sentiment_multiplier + 0.4 * dynamic_fallback_multiplier, 0.30, 1.10)`
- `fallback_regime_similarity = clip(0.25 + 0.60 * risk_on - 0.25 * stress, 0.05, 0.95)`
- `fallback_causal_stability = clip(0.90 - 0.35 * stress - 0.20 * sentiment_uncertainty - 0.15 * sentiment_conflict, 0.20, 0.95)`

Brain adjustments:

- `brain_adjusted_exposure = original_exposure * exposure_multiplier`
- Final allowed exposure:
  - `max(5, min(original_exposure, brain_adjusted_exposure))`
- If `pulse_intensity > 1.5 and regime_similarity < 0.3`:
  - multiply `risk_on_probability` by `0.8`
- If `causal_stability < 0.5`:
  - multiply confidence by `0.9`
- If `survival_mode in {emergency, shutdown}`:
  - `stress_level = max(stress_level, 0.8)`
- If `survival_mode == stress`:
  - `stress_level = max(stress_level, 0.6)`

Downstream impact:

- This is the last top-down contextual edit before market state is finalized and saved.

### 3.4.10 Consistency and coherence score

Source: `src/state/market_state.py:892-955`

Rules:

- Warnings are created for contradictions such as:
  - strong macro with weak health
  - high risk-on with narrow breadth
  - high allowed exposure with high stress
- `coherence_score = max(0, 1 - 0.15 * warning_count)`

Downstream impact:

- This does not directly size the portfolio, but it is a useful meta-diagnostic for questionable state combinations.

## 3.5 Portfolio Governor And Capital Structure

Primary files:

- `src/portfolio/governor.py`
- `src/portfolio/capital_structure.py`
- `config/portfolio_governor_config.yaml`

### 3.5.1 Caution score

Source: `src/portfolio/governor.py:280-346`

Weighted components:

- Market regime weight `0.30`
- Volatility regime weight `0.15`
- Macro regime weight `0.20`
- Sentiment regime weight `0.15`
- Economic activity regime weight `0.10`
- Crisis probability weight `0.10`

Score maps:

- Market:
  - `BULL=0.0`, `SIDEWAYS=0.2`, `VOLATILE=0.5`, `BEAR=0.7`, `CRISIS=1.0`
- Volatility:
  - `LOW_VOL=0.0`, `NORMAL_VOL=0.1`, `ELEVATED_VOL=0.4`, `HIGH_VOL=0.7`, `EXTREME_VOL=1.0`
- Macro:
  - `EXPANSION=0.0`, `RECOVERY=0.1`, `NEUTRAL=0.2`, `SLOWING=0.5`, `CONTRACTION=0.8`
- Sentiment:
  - `EUPHORIA=0.2`, `OPTIMISM=0.0`, `NEUTRAL=0.1`, `FEAR=0.6`, `PANIC=1.0`, `UNAVAILABLE=0.2`
- Economic activity:
  - `EXPANSION=0.0`, `RECOVERING=0.1`, `NEUTRAL=0.2`, `SLOWING=0.5`, `CONTRACTION=0.8`, `UNAVAILABLE=0.2`

Final formula:

- `caution_score = weighted_sum + 0.10 * min(crisis_probability, 1.0)`

Regime thresholds:

- `< 0.15 -> FULL_DEPLOYMENT`
- `< 0.30 -> STANDARD`
- `< 0.50 -> CAUTIOUS`
- `< 0.70 -> DEFENSIVE`
- else `CAPITAL_PRESERVATION`

### 3.5.2 Base capital structures

Source: `src/portfolio/capital_structure.py:42-77`, config overrides in `config/portfolio_governor_config.yaml:15-44`

Default code table:

- `FULL_DEPLOYMENT = 90% equity / 8% options / 2% cash`
- `STANDARD = 75% / 15% / 10%`
- `CAUTIOUS = 75% / 15% / 10%`
- `DEFENSIVE = 45% / 10% / 45%`
- `CAPITAL_PRESERVATION = 10% / 5% / 85%`

Config table:

- `CAUTIOUS = 60% / 20% / 20%`
- `DEFENSIVE = 40% / 20% / 40%`
- `CAPITAL_PRESERVATION = 15% / 10% / 75%`

Why it matters:

- Behavior differs depending on whether the caller loaded config or fell back to code defaults.

### 3.5.3 Drawdown modifier

Source: `src/portfolio/governor.py:357-375`

Rules:

- Trigger when `current_drawdown_pct < -8.0`
- `excess_drawdown = abs(current_drawdown_pct - trigger)`
- `reduction = min(excess_drawdown * 0.03, 0.25)`
- `equity_frac -= reduction`
- `cash_frac += reduction`

### 3.5.4 Recovery restoration modifier

Source: `src/portfolio/governor.py:377-396`

Rules:

- Activation when `current_drawdown_pct >= -3.0`
- `restoration = min(recovery_days_elapsed * 0.01, 0.02)`
- `equity_frac += restoration`
- `cash_frac -= restoration`

Important dependency:

- This depends on `persistent_state["recovery_days_elapsed"]`, which currently appears never to be incremented anywhere else in the codebase.

### 3.5.5 Crisis override

Source: `src/portfolio/governor.py:398-433`

Rules:

- `crisis_probability > 0.40 -> CAPITAL_PRESERVATION`
- `> 0.25 -> DEFENSIVE`
- `> 0.15 -> CAUTIOUS`
- Only applies if the override is more conservative than the current regime.

### 3.5.6 NAV size protection

Source: `src/portfolio/governor.py:435-456`

Formulas:

- `nav_multiple = current_nav / starting_capital`
- Activate when `nav_multiple > 1.20`
- `additional_cash = min((excess_multiple / 0.1) * 0.02, 0.10)`
- `equity_frac -= additional_cash`
- `cash_frac += additional_cash`

### 3.5.7 Hard limits, normalization, and budgets

Source: `src/portfolio/governor.py:458-518`, `160-254`

Rules:

- Equity clipped to `[min_equity_fraction, max_equity_fraction]`
- Options clipped to `[min_options_fraction, max_options_fraction]`
- Cash floored at `min_cash_fraction`
- If total exceeds `1.0`, excess is removed from cash
- Fractions are renormalized to sum exactly to `1.0`

Budget formulas:

- `total_capital = current_nav if > 0 else starting_capital`
- `equity_budget_inr = max(equity_frac * total_capital - options_deployed, 0.0)`
- `options_budget_inr = options_frac * total_capital`
- `cash_reserve_inr = cash_frac * total_capital`

Governance confidence:

- `0.9` for very low or very high caution
- `0.7` for moderately clear caution
- `0.5` otherwise
- minus `0.05 * number_of_modifiers`
- clipped to `[0.1, 1.0]`

Downstream impact:

- This is the hard top-level capital budget for equities, options, and undeployed cash.

## 3.6 Scoring, Ranking, And Overlays

Primary files:

- `src/scoring/northstar_model.py`
- `src/scoring/daily_scorer.py`
- `src/signals/sentiment_overlay.py`
- `src/signals/feature_builder.py`
- `src/factors/piotroski_factor.py`
- `src/factors/amihud_factor.py`

### 3.6.1 Northstar quality score

Source: `src/scoring/northstar_model.py:248-314`

Metrics:

- `ROE = net_income / equity`
- `ROA = net_income / total_assets`
- `FCF margin = free_cash_flow / revenue`
- `debt_to_equity = total_debt / equity`
- `EBITDA margin = ebitda / revenue`
- `debt_to_equity_inv = 1 / (1 + debt_to_equity)`

Normalization:

- Most quality metrics are clipped to their 1st and 99th percentiles.
- If enough usable features exist, PCA first component becomes quality score.
- Otherwise simple average is used.
- Final quality score is scaled to `0-100`.

### 3.6.2 Value score

Source: `src/scoring/northstar_model.py:316-353`

Formulas:

- `pe_inv = 1 / (1 + pe_ratio / 20)`
- `pb_inv = 1 / (1 + pb_ratio / 3)`
- `ev_ebitda_inv = 1 / (1 + ev_ebitda / 15)`
- Value score = mean of available value metrics times `100`

### 3.6.3 Momentum score

Source: `src/scoring/northstar_model.py:355-399`

Transformations:

- `rsi_norm = RSI`
- `macd_norm = min-max scaled MACD on 0-100`
- `trend_norm = trend_regime * 100`
- `breakout_norm = breakout_strength * 100`
- `price_perf_norm = ((price_performance_1m + 0.2) / 0.4 * 100).clip(0, 100)`
- Momentum score = mean of available normalized momentum metrics

### 3.6.4 Growth and profitability scores

Source: `src/scoring/northstar_model.py:401-471`

Growth:

- `revenue_growth_norm = ((revenue_growth + 0.1) / 0.3 * 100).clip(0, 100)`
- `earnings_growth_norm = ((earnings_growth + 0.1) / 0.3 * 100).clip(0, 100)`
- `bv_growth_norm = ((book_value_growth + 0.05) / 0.25 * 100).clip(0, 100)`
- Growth score = mean of available growth metrics

Profitability:

- `gross_margin_norm = gross_margin * 100`
- `op_margin_norm = operating_margin * 100`
- `net_margin_norm = net_margin * 100`
- `roe_norm = ((roe + 0.05) / 0.3 * 100).clip(0, 100)`
- Profitability score = mean of available profitability metrics

### 3.6.5 Risk penalty and final Northstar score

Source: `src/scoring/northstar_model.py:473-650`

Risk penalty pieces:

- Volatility penalty:
  - `(atr / Close * 100).clip(0, 10)`
- Debt penalty:
  - `(debt_to_equity / 2).clip(0, 5)`
- Liquidity penalty:
  - `2` points for bottom 10% dollar volume
- Size penalty:
  - `3` points for bottom 5% market cap
- Aggregate risk penalty:
  - sum of active penalties

Sector neutralization:

- Within each `Industry`:
  - `sector_z = (score - sector_mean) / sector_std`
  - then min-max rescaled to `0-100`

Final score:

- Default factor weights:
  - `quality = 0.30`
  - `value = 0.25`
  - `momentum = 0.20`
  - `growth = 0.15`
  - `profitability = 0.10`
- `raw_score = sum(weighted factor scores)`
- If risk penalty missing or constant, rebuild from:
  - realized vol deviation
  - market-cap deviation
  - debt-to-equity deviation
- `northstar_score = raw_score - risk_penalty * EFFECTIVE_RISK_WEIGHT`
- clip to `0-100`
- If final score dispersion is too low:
  - rank-normalize raw score to percentile and multiply by `100`

### 3.6.6 Turnover constraint

Source: `src/scoring/daily_scorer.py:25-114`

Rules:

- Keep prior holdings if current rank `<= 35`
- Portfolio target size defaults to `20`
- Max turnover defaults to `30%`
- If turnover exceeds cap, force extra prior holdings back into the book

Downstream impact:

- Ranking does not directly become the portfolio; this turnover rule adds persistence.

### 3.6.7 Sentiment and macro overlays

Source: `src/signals/sentiment_overlay.py:257-397`

Ticker-level sentiment overlay:

- If `sentiment_polarity < -0.2`:
  - `sentiment_multiplier = 0.6`
- If `sentiment_polarity < -0.5 and conviction > 0.7`:
  - `sentiment_multiplier = 0.0`
  - `sentiment_override = True`
  - reason = `strong_negative_sentiment`
- If market sentiment polarity `< -0.4`:
  - multiply the existing ticker multiplier by `0.7`
- `adjusted_score = model_score * sentiment_multiplier`

Macro overlay:

- Macro regime scalar:
  - `contraction -> 0.8`
  - `expansion -> 1.1`
- Sector macro tilt:
  - `sector_activity_zscore < -1.5 -> x0.7`
  - `sector_activity_zscore > 1.5 -> x1.15`
- Final multiplier clipped to `[0.0, 1.5]`

### 3.6.8 Cross-sectional feature normalization

Source: `src/signals/feature_builder.py:60-107`

Formulas:

- Group z-score:
  - `z = (value - group_mean) / group_std`
  - clipped to `[-6, 6]`
- Centered percentile rank:
  - `pct_rank - 0.5`

These are used to standardize alternative features across the cross section.

### 3.6.9 Piotroski and Amihud factors

Sources:

- `src/factors/piotroski_factor.py`
- `src/factors/amihud_factor.py`

Piotroski:

- Standard nine binary tests across profitability, leverage/liquidity, and operating efficiency
- Final score `0-9`
- Requires at least `6` valid tests

Amihud:

- `daily_returns = log(close).diff()`
- `rupee_volume = close * volume`
- `ILLIQ = mean(abs(daily_returns) / rupee_volume)`
- Output transform:
  - `log(1 + ILLIQ * 1_000_000)`

## 3.7 Allocation, Risk Budgets, And Runtime Sizing

Primary files:

- `src/intelligence/bayesian_kelly_allocator.py`
- `src/runtime/risk_budget.py`
- `src/cohesion/bounded_exposure_calculator.py`

### 3.7.1 Bayesian Kelly base weights

Source: `src/intelligence/bayesian_kelly_allocator.py:204-236`, `361-404`

Formulas:

- `confidence = max(model_confidence, min_confidence)`
- `dd_modifier = exp(-drawdown_lambda * current_drawdown)`
- Valuation bridge:
  - `gap = clip(gap, -valuation_gap_clip, valuation_gap_clip)`
  - `beta_scaled = beta_base * (1 - 0.50 * crisis_prob) * (1 - 0.35 * bubble_probability)`
  - `beta = clip(beta_scaled, valuation_beta_min, valuation_beta_max)`
  - `gamma = beta ** 2`
- Per-strategy mean:
  - `mu_total = posterior_mean + beta * valuation_gap * alignment * macro_compression`
- Effective variance:
  - `sigma_eff_sq = volatility^2 + posterior_variance + gamma * valuation_variance`
- Kelly fraction:
  - `kelly = mu_total / sigma_eff_sq`
- Final pre-cap weight:
  - `kelly * regime_multiplier * dd_modifier * confidence * credibility * penalty`

Regime multipliers:

- Strategy-type-specific mappings over regime probabilities
- Examples:
  - `short_vol` likes `LOW_VOL`, hates `CRISIS`
  - `long_vol` likes `CRISIS`

### 3.7.2 Hard caps and soft constraints

Source: `src/intelligence/bayesian_kelly_allocator.py:258-359`

Hard caps:

- Gross exposure cap:
  - if `gross > gross_cap`, scale all weights by `gross_cap / gross`
- Net exposure cap:
  - if `abs(net) > net_cap`, subtract proportional correction from each weight

Soft metrics:

- `vol_proxy = sqrt(sum((w * sigma_eff)^2))`
- `cvar_proxy += abs(w) * sigma_eff * 2.33`
- `liquidity_penalty += abs(w) * liquidity_score`
- `convexity_proxy += abs(w) * convexity_score`
- `mean_return += w * mu_total`
- `drawdown_probability_proxy = clip(0.5 + (cvar_proxy - max(mean_return, -0.5)) * 0.5, 0, 1)`

If soft limits are violated, the allocator:

1. shrinks weights
2. relaxes penalties
3. widens soft bounds
4. drops low-priority soft constraints
5. falls back to a heuristic top-strategy allocator

### 3.7.3 Bounded exposure calculator

Source: `src/cohesion/bounded_exposure_calculator.py`

Formulas:

- Allowed exposure:
  - `raw_exposure = risk_on * (1 - stress_score) * regime_multiplier`
- Risk-scaled exposure:
  - `raw_exposure = target_volatility / portfolio_volatility`
- Combined:
  - `min(allowed_exposure, risk_scaled_exposure)`

Bounds:

- NaN -> `0`
- `+inf -> 1`
- `-inf -> 0`
- other values clipped to `[0, 1]`

### 3.7.4 Risk budget manager

Source: `src/runtime/risk_budget.py:58-140`

Formulas:

- `projected_gross_ratio = (gross + approved_notional) / equity`
- `projected_net_ratio = abs(net + sign * approved_notional) / equity`
- `projected_vol_adjusted_ratio = projected_gross_ratio * max(1.0, vol_multiplier)`
- `strategy_ratio = current_strategy_ratio + approved_notional / equity`
- `origin_ratio = current_origin_ratio + approved_notional / equity`
- `sector_ratio = current_sector_ratio + approved_notional / equity`

Denial triggers:

- gross cap breach
- net cap breach
- vol-adjusted cap breach
- strategy cap breach
- origin cap breach
- sector cap breach
- worst-case stress-loss breach

Downstream impact:

- This is the hard post-allocation gate before trades are allowed through.

## 3.8 Risk, Volatility, Options, And Execution Realism

Primary files:

- `src/risk/portfolio_risk_controller.py`
- `src/risk/emergency_brake.py`
- `src/volatility/volatility_processor.py`
- `src/volatility/greeks_aggregator.py`
- `src/execution/market_impact_model.py`
- `src/execution/enhanced_transaction_cost_model.py`

### 3.8.1 Portfolio risk controller

Source: `src/risk/portfolio_risk_controller.py`

EWMA volatility:

- `alpha = 1 - exp(-log(2) / halflife)`
- recursive EWMA variance
- annualized vol `= sqrt(variance * 252)`

Risk-adjusted exposure:

- `vol_scalar = min(vol_target / realized_vol, 2.0)`
- If current drawdown exceeds target:
  - `dd_scalar = max((max_drawdown - current_dd) / (max_drawdown - target_drawdown), 0.1)`
- Recent Sharpe over last `20` days:
  - `(mean(recent_returns) * 252) / (std(recent_returns) * sqrt(252))`
  - `> 1.0 -> perf_scalar = 1.1`
  - `< -0.5 -> perf_scalar = 0.7`
  - else `1.0`
- `risk_adjusted_exposure = 0.8 * vol_scalar * dd_scalar * perf_scalar`
- Final clip to configured min/max exposure and regime-specific max exposure

Convexity/tail budget:

- `convexity_component = |gamma_exposure| * underlying_vol`
- `vega_component = |vega_exposure| * vol_of_vol`
- `liquidity_adjusted_vega = vega_component * (1 + liquidity_spread_pct * 5)`
- `convexity_score = (convexity_component + liquidity_adjusted_vega) / portfolio_value`
- `tail_convexity_score = 0.65 * convexity_score + 0.25 * |delta| / pv + 0.10 * gap_risk_score`
- Veto when `tail_convexity_score > max_drawdown_limit`

### 3.8.2 Emergency brake

Source: `src/risk/emergency_brake.py`

Signals:

- Drawdown:
  - `drawdown = equity / peak_equity - 1`
  - breach if `< -10%`
- Volatility:
  - `rolling_vol = rolling_20_std(returns)`
  - breach if `> 3% daily`
- Consecutive losses:
  - `(returns < 0).rolling(5).sum() >= 5`
- Extreme single-day loss:
  - `return < -5%`
- Volatility spike:
  - `rolling_vol > 2 * rolling_60_mean_vol`
- Market stress:
  - `stress_level > 0.7`

Master emergency:

- `Emergency = OR(all signal breaches)`

Risk level:

- `0.3 * drawdown_breach`
- `+ 0.25 * vol_breach`
- `+ 0.2 * consecutive_losses`
- `+ 0.15 * extreme_loss`
- `+ 0.1 * market_stress`

Caps:

- `drawdown_cap = clip(1 + drawdown * 2, 0.1, 1.0)`
- `vol_cap = 0.5` on volatility breach
- `vol_cap = 0.2` on volatility spike
- `emergency_override = 0.1` if emergency active
- Final cap = elementwise minimum of all caps

Downstream impact:

- This can override market-state allowed exposure after the market-state spine has already been computed.

### 3.8.3 Volatility utilities

Source: `src/volatility/volatility_processor.py`

Formulas:

- Realized volatility:
  - `std(returns.tail(window)) * sqrt(annualization_factor)`
- ATR:
  - `mean(high - low)` over the ATR window
- Volatility percentile:
  - fraction of historical volatility observations below the current vol
- Regime:
  - percentile `< 0.33 -> Low`
  - `< 0.66 -> Normal`
  - else `High`
- Implied/realized spread:
  - `implied_vol - realized_vol`
- VRP:
  - `(implied_vol - realized_vol) / implied_vol`

### 3.8.4 Greeks aggregation

Source: `src/volatility/greeks_aggregator.py:259-337`

Black-Scholes terms:

- `d1 = (ln(S / K) + (r + 0.5 * sigma^2) * T) / (sigma * sqrt(T))`
- `d2 = d1 - sigma * sqrt(T)`

Greeks:

- Call delta: `N(d1)`
- Put delta: `-N(-d1)`
- `gamma = n(d1) / (S * sigma * sqrt(T))`
- `vega = S * n(d1) * sqrt(T) / 100`
- Theta per day:
  - call and put formulas divided by `365`
- `rho = K * T * exp(-rT) * N(d2) / 100`
- `vanna = -n(d1) * d2 / sigma`
- `volga = S * n(d1) * sqrt(T) * d1 * d2 / sigma`
- `charm = -n(d1) * (2rT - d2 * sigma * sqrt(T)) / (2 * T * sigma * sqrt(T)) / 365`
- `vomma = volga`

Portfolio aggregation:

- Sum each Greek after multiplying by position quantity.

### 3.8.5 Market impact model

Source: `src/execution/market_impact_model.py`

Formulas:

- Dynamic `k`:
  - `k = base_k * (1 + 2 * max(volatility - 0.20, 0) + market_stress)`
  - crisis-like regimes multiply by `crisis_multiplier`
- Square-root impact:
  - `impact = k * sigma * sqrt(order_size / ADV)`
- Large-order penalty:
  - when participation exceeds threshold:
  - multiply by `1 + overflow * large_order_penalty`
- Fill price:
  - `buy_fill = mid * (1 + impact)`
  - `sell_fill = mid * (1 - impact)`

### 3.8.6 Enhanced transaction cost model

Source: `src/execution/enhanced_transaction_cost_model.py`

Base costs:

- Brokerage, STT, stamp duty, GST, SEBI charges, exchange charges, DP charges
- `total_base_cost = sum(all base costs)`
- `total_base_cost_bps = total_base_cost / trade_value * 10000`

Regime detection:

- volatility, VIX, market stress, and liquidity determine:
  - `normal`
  - `stress`
  - `crisis`
  - `extreme_crisis`

Market impact:

- `adv_percentage = trade_value / ADV`
- `liquidity_impact = base_impact * adv_percentage ^ liquidity_exponent`
- `volatility_adjustment = (volatility / 0.15) ^ volatility_multiplier`
- `large_trade_penalty = excess_adv_percentage * large_trade_penalty`
- `total_market_impact = liquidity_impact * volatility_adjustment + large_trade_penalty`

Funding:

- Longs:
  - `trade_value * margin_requirement * daily_funding_rate * holding_period_days`
- Shorts:
  - `borrow_cost + haircut_cost`

Total:

- `total_transaction_cost = crisis_adjusted_base_cost + market_impact + funding_cost`
- `total_cost_bps = total_transaction_cost / trade_value * 10000`
- `performance_drag_annual = total_cost_bps * 252 / 10000`
- `breakeven_return_required = total_cost_bps / 10000 * 2`

## 3.9 Valuation, Forensics, And PnL Accounting

Primary files:

- `src/valuation/intrinsic_value/owner_earnings.py`
- `src/valuation/intrinsic_value/dcf_engine.py`
- `src/valuation/forensic/earnings_quality.py`
- `src/valuation/aggregation/valuation_aggregator.py`
- `src/pnl/ledger.py`

### 3.9.1 Owner earnings

Source: `src/valuation/intrinsic_value/owner_earnings.py`

Maintenance capex:

- Sector base ratios:
  - utilities `1.0`
  - industrials `0.90`
  - materials `0.85`
  - energy `0.90`
  - technology `0.60`
  - healthcare `0.65`
  - consumer `0.75`
  - financials `0.50`
- Growth adjustment:
  - `revenue_growth > 20% -> 0.85`
  - `> 10% -> 0.90`
  - else `1.0`
- `maintenance_capex = min(total_capex, depreciation * adjusted_ratio)`

Working capital:

- `wc_increase = current_wc - prior_wc`
- `expected_wc_increase = prior_wc * revenue_growth`
- Penalize only excess:
  - `max(0, wc_increase - expected_wc_increase)`

One-time items:

- `restructuring + impairment - gain_on_sale + 0.5 * abs(other_income)`

Owner earnings:

- `net_income + depreciation + amortization - maintenance_capex - wc_increase - one_time_items`

Quality score:

- average of:
  - owner-earnings-to-net-income ratio
  - capex efficiency
  - working-capital efficiency

### 3.9.2 DCF engine

Source: `src/valuation/intrinsic_value/dcf_engine.py`

Discount rate:

- `required_return = risk_free_rate + beta * ERP + size_premium - quality_adjustment + credit_adjustment`
- hard floor at `8%`

Sustainable growth:

- `min(historical_growth, roic * reinvestment_rate, gdp_growth_cap, industry_growth * 1.5)`
- floored at `0`

Terminal value:

- Gordon growth:
  - `terminal_cf * (1 + g) / (r - g)`
- But first cap `g` so that `g <= r - 0.02`
- Extra ROIC-based caps:
  - low ROIC -> lower terminal growth ceiling
- Fallback:
  - `terminal_value = terminal_cf * 15` if `discount_rate <= terminal_growth`

Two-stage DCF:

- For each year `t`:
  - `cf_t = current_owner_earnings * (1 + growth_rate) ^ t`
  - `pv_t = cf_t / (1 + discount_rate) ^ t`
- `intrinsic_value = stage1_pv + terminal_pv`
- `intrinsic_value_per_share = intrinsic_value / shares_outstanding`
- Margin of safety:
  - `intrinsic_value_per_share - current_price`
- MOS percent:
  - `margin_of_safety / intrinsic_value_per_share`
- Grades:
  - `>= 40% -> A`
  - `>= 30% -> B`
  - `>= 20% -> C`
  - `>= 0 -> D`
  - else `F`

Buffett-style wrapper:

- `growth_stage1 = min(0.15, revenue_growth_5y * 0.7)`
- Growth years:
  - `quality >= 80 -> 10`
  - `quality >= 60 -> 7`
  - else `5`
- Terminal growth:
  - `ROIC >= 20% -> 5%`
  - `ROIC >= 15% -> 4%`
  - else `3%`
- `reinvestment_rate = growth_stage1 / ROIC` if ROIC positive else `0.5`
- Distress bridge:
  - `EXCLUDE -> intrinsic value = 0`
  - `HAIRCUT -> haircut = distress_score * 0.3`

### 3.9.3 Earnings quality / forensic accounting

Source: `src/valuation/forensic/earnings_quality.py`

Accrual ratio:

- `(net_income - operating_cash_flow) / total_assets`

Cash conversion:

- current:
  - `operating_cash_flow / net_income`
- consistency:
  - `1 / (1 + std(conversion_history))`

Earnings stability:

- coefficient of variation:
  - `std(earnings) / mean(earnings)`
- linear trend:
  - slope from `polyfit`
- margin stability:
  - `1 / (1 + std(margins))`

Beneish components:

- DSRI, GMI, AQI, SGI, DEPI standard ratios

Red flags:

- accrual magnitude `> 10%`
- cash conversion `< 0.7`
- DSRI `> 1.03`
- GMI `> 1.04`
- AQI `> 1.04`
- SGI `> 1.50`
- earnings volatility `> 0.5`

Quality score:

- `accrual_score = max(0, 100 - abs(accrual_ratio) * 500)`
- `conversion_score = min(100, cash_conversion * 100)`
- `stability_score = earnings_stability * 100`
- `raw_score = 0.35 * accrual + 0.35 * conversion + 0.30 * stability`
- `final_score = max(0, raw_score - 10 * red_flag_count)`

### 3.9.4 Bayesian valuation aggregator

Source: `src/valuation/aggregation/valuation_aggregator.py`

Regime inference:

- `crisis = clamp(0.08 + 0.0075 * avg_stress + 0.8 * avg_default, 0.03, 0.90)`
- `low_vol = clamp(0.40 - 0.0045 * avg_stress, 0.05, 0.80)`
- `normal = clamp(1 - crisis - low_vol, 0.05, 0.90)`
- normalize all three to sum to `1`

Per-family precision:

- `effective_variance = variance / confidence`
- `precision = 1 / effective_variance`
- multiply by regime modifier

Posterior:

- `dispersion = var(gaps)`
- `shrink = 1 / (1 + kappa * dispersion)`
- `weighted_gap = sum(precision * gap) / sum(precision)`
- `posterior_gap = clamp(shrink * weighted_gap * macro_compression, -2, 2)`
- `posterior_variance = 1 / sum(precision)`
- `agreement = 1 / (1 + dispersion)`
- `posterior_confidence = clamp(agreement * mean_confidence, 0.05, 0.99)`
- `posterior_value = reference_value * (1 + posterior_gap)` when reference value is positive

Downstream impact:

- Posterior gap and variance flow directly into the Kelly allocator’s valuation bridge.

### 3.9.5 Valuation feature block

Source: `src/valuation/valuation_feature_block.py`

Key transforms:

- Discount to fair value:
  - `val_discount_to_fair_pct = ((fair_value - current_price) / fair_value) * 100`
- Margin of safety:
  - `val_margin_of_safety = clip(1 - current_price / fair_value, -1, 1)`
- Earnings-quality score scaling:
  - `val_earnings_quality_score = quality_score / 10`
- Quality composite:
  - mean of:
    - moat score
    - scaled 5-year ROCE
    - scaled earnings consistency
- Safety composite:
  - mean of:
    - scaled earnings-quality score
    - scaled debt-safety score
    - scaled interest coverage
- Posterior valuation composite:
  - build family gaps from margin of safety, quality composite, safety composite, and moat
  - aggregate them through `BayesianValuationAggregator`
  - `val_composite_score = clip(50 + 50 * posterior_gap, 0, 100)`
- Cross-sectional outlier control:
  - feature values clipped at `mean +/- 3 * std`
  - z-scores computed on the clipped series

Downstream impact:

- This is the bridge from single-name valuation work into the research/scoring feature surface.

### 3.9.6 PnL ledger

Source: `src/pnl/ledger.py`

Trade-entry formulas:

- Equity trade notional:
  - `abs(quantity * price)`
- Equity settlement:
  - `T + 1`
- Opening trade net PnL:
  - `transaction_cost`
- Options premium settlement:
  - same day

End-of-day MTM:

- Equity:
  - `unrealized_pnl = (current_price - avg_cost) * quantity`
- Options:
  - `unrealized_pnl = current_value - entry_credit_debit`

Downstream impact:

- These values feed realized/unrealized PnL snapshots, drawdown, and governor NAV inputs.

## 4. Confirmed Issue Log

These are not speculative. They are directly supported by code reads.

### 4.1 Alternative-data feature-key mismatches corrupt downstream state

Evidence:

- `src/alternative_data/alternative_feature_block.py:297-300` writes:
  - `credit_market_upgrade_ratio`
  - `credit_market_net_momentum`
  - `credit_market_stress_flag`
- `src/alternative_data/alternative_pipeline_runner.py:490-495` reads:
  - `credit_upgrade_ratio`
  - `credit_net_momentum`
  - `credit_stress_flag`

Also:

- `src/alternative_data/alternative_feature_block.py:359-362` writes:
  - `bulk_market_net_flow`
  - `bulk_market_breadth`
  - `bulk_market_signal_numeric`
- `src/alternative_data/alternative_pipeline_runner.py:510-537` reads:
  - `bulk_signal_numeric`
  - `bulk_net_flow`
  - `bulk_breadth`

Also:

- `src/alternative_data/alternative_feature_block.py` produces `power_deviation_from_seasonal`
- `src/alternative_data/alternative_pipeline_runner.py:458-462` reads `power_deviation_seasonal`

Impact:

- Credit state silently defaults toward neutral/zero.
- Smart-money state silently uses defaults instead of actual feature outputs.
- Power-signal deviation is silently lost.
- The alternative-data branch can therefore look “healthy but uninformative” even when upstream data is rich.

### 4.2 Smart-money numeric-to-enum mapping is inverted/shifted

Evidence:

- Feature block assigns:
  - `2 = STRONG_ACCUMULATION`
  - `1 = MILD_ACCUMULATION`
  - `0 = NEUTRAL`
  - `-1 = MILD_DISTRIBUTION`
  - `-2 = STRONG_DISTRIBUTION`
- Runner mapping in `src/alternative_data/alternative_pipeline_runner.py:510-522` interprets:
  - `<= 0 -> STRONG_DISTRIBUTION`
  - `<= 1 -> MILD_DISTRIBUTION`
  - `<= 2 -> NEUTRAL`
  - `<= 3 -> MILD_ACCUMULATION`
  - else `STRONG_ACCUMULATION`

Impact:

- Even after fixing the key mismatch, `0` becomes `STRONG_DISTRIBUTION`, `1` becomes `MILD_DISTRIBUTION`, and `2` becomes `NEUTRAL`.
- The entire smart-money classification is effectively miswired.

### 4.3 Smart-money distribution breadth can never be positive

Evidence:

- Feature block breadth is defined as:
  - `positive_count / len(bulk_df)` in `src/alternative_data/alternative_feature_block.py:340-345`
- Runner computes:
  - `accumulation_breadth = bulk_breadth if bulk_breadth > 0 else 0`
  - `distribution_breadth = abs(bulk_breadth) if bulk_breadth < 0 else 0` in `src/alternative_data/alternative_pipeline_runner.py:535-537`

Impact:

- Because `bulk_breadth` is a non-negative ratio by construction, `distribution_breadth` is always `0.0`.
- The state cannot represent broad-based distribution correctly.

### 4.4 Recovery restoration in the governor appears dead

Evidence:

- State initializes `recovery_days_elapsed` in `src/portfolio/governor.py:117-125`
- Recovery modifier reads it in `src/portfolio/governor.py:386-394`
- Repo-wide search only finds those two occurrences

Impact:

- Unless some external manual process edits governor state, `recovery_days_elapsed` stays `0`.
- That means recovery restoration likely never adds back equity exposure.

### 4.5 Earnings-quality code contradicts its own India-market note

Evidence:

- Docstring in `src/valuation/forensic/earnings_quality.py:54-63` says high accruals are not to be treated the same way as in the US and explicitly warns not to invert the sign for India.
- Implementation then:
  - flags `abs(accrual_ratio) > 0.10` as a red flag in `:230-233`
  - penalizes `abs(accrual_ratio)` in score at `:269-285`
  - reports `accrual_quality = 100 - abs(accrual_ratio) * 500` in `:375-378`

Impact:

- The comments and the actual model logic disagree.
- Anyone relying on the comment will misunderstand the actual scoring behavior.

### 4.6 Exposure units are mixed between decimal ratios and percentage points

Evidence:

- `src/state/market_state.py:531-537` stores `allowed_exposure` in `5..95` percentage points
- `src/risk/emergency_brake.py:210-219` multiplies emergency cap by `100` before writing it into market state
- `scripts/run_complete_v3_system.py` normalizes values above `1.0` by dividing by `100` before storing ratio-like values in unified state

Impact:

- Different consumers can read the same conceptual field as either `0.55` or `55`.
- This is a classic source of hidden risk-sizing bugs and dashboard confusion.

### 4.7 Governor defaults drift between code and config

Evidence:

- Code defaults in `src/portfolio/capital_structure.py:42-68`
- Config values in `config/portfolio_governor_config.yaml:15-44`

Impact:

- Runtime behavior depends on whether the caller loads the config path correctly.
- Ad hoc scripts or tests using code defaults can produce materially different equity/options/cash mixes.

## 5. Highest-Leverage Dependency Chains

If the goal is to find the most dangerous bugs quickly, start with these chains.

1. `Alternative data -> economic activity regime -> caution score -> capital structure`
   Because the key mismatches and smart-money mapping bugs live here, this path is the highest-probability source of silent allocation distortion.
2. `Market state allowed_exposure -> emergency brake -> ratio normalization`
   Because unit mismatches can cause the same field to be interpreted on different scales.
3. `PnL drawdown -> governor drawdown modifier / recovery modifier`
   Because one side is active and the other appears inert.
4. `Valuation posterior gap -> Kelly allocator`
   Because posterior gap changes both effective expected return and effective variance via the valuation bridge.
5. `Scoring model -> overlays -> turnover constraint`
   Because the final book is not the raw factor ranking; overlays and turnover can materially override it.

## 6. Recommended Next Debug Pass

The next investigation order should be:

1. Fix the alternative-data key mismatches and smart-money mapping.
2. Standardize exposure units end-to-end as either `0-1` or `0-100`, but not both.
3. Decide the intended India-market accrual logic and align comments plus formulas.
4. Decide whether `recovery_days_elapsed` should be updated automatically and wire it in.
5. Freeze one authoritative governor regime table and remove the drift between code and config defaults.

## 7. Audit Deliverables Produced

Human-readable report:

- `audit/FORMULA_AND_CALCULATION_AUDIT_2026-03-21.md`

Machine appendices:

- `audit/formula_inventory_2026-03-21.json`
- `audit/formula_inventory_summary_2026-03-21.json`
- `audit/formula_inventory_2026-03-21.csv`

Use the markdown report to understand the calculation chain, and use the JSON/CSV appendices to confirm repo-wide coverage.
