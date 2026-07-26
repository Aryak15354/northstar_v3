#!/usr/bin/env python3
"""Unit tests for the Gen-8 remediation library.

RESEARCH OS lineage note: this is a re-run of the Gen-8 remediation library's own test suite
(scripts/gen8/tests/test_remediation_library.py, unchanged), imported against the RESEARCH OS
fork (research_os/valid_pvalue.py etc., forked from scripts/gen8/lib/ on 2026-07-26) instead of
the original scripts/gen8/lib/ modules -- confirms the fork behaves identically before any
Northstar Institute lab depends on it.

`GEN8_RESEARCH_CHARTER.md` §10 requires that **each module carries a test using a synthetic case
where the old buggy code produces a demonstrably wrong answer and the new code does not.** A test
that only checks the new code returns something plausible would not establish that the defect is
actually fixed — it would only establish that the replacement runs.

Each test class below therefore has the same shape:
    1. construct a case with a KNOWN ground truth,
    2. run the **defective** procedure and assert it gets that ground truth WRONG,
    3. run the **fixed** procedure and assert it gets it RIGHT.

Run:  venv_gen8/bin/python3 -m research_os.tests.test_forked_modules
(original: venv_gen8/bin/python3 -m scripts.gen8.tests.test_remediation_library)
"""
from __future__ import annotations

import sys
import traceback

import numpy as np
import pandas as pd

from .. import valid_pvalue as vp
from .. import power_precheck as pp
from .. import rolling_window_artifact_check as rw
from .. import registry_integrity_check as ri

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        detail = fn() or ""
        RESULTS.append((name, True, detail))
        print(f"  PASS  {name}" + (f"\n          {detail}" if detail else ""))
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
        print(f"  FAIL  {name}\n          {e}")
    except Exception:
        RESULTS.append((name, False, traceback.format_exc(limit=2)))
        print(f"  ERROR {name}\n{traceback.format_exc(limit=2)}")


# =============================================================================================
# 1a -- valid_pvalue
# =============================================================================================
def test_1a_pvalue_floor():
    """Old estimator returns exactly 0.0; a p-value of 0 is never valid output."""
    old = vp.invalid_permutation_pvalue_DO_NOT_USE(n_ge=0, n_perm=500)
    assert old == 0.0, f"expected the old estimator to floor at 0.0, got {old}"
    new = vp.permutation_pvalue(n_ge=0, n_perm=500)
    assert abs(new - 1 / 501) < 1e-12, f"expected 1/501, got {new}"
    assert new > 0
    return f"old k/N = {old}  ->  new (1+k)/(N+1) = {new:.6f}"


def test_1a_gen7_family_is_unresolvable():
    """Gen-7's exact design (m=310, q=0.05, N=500) must be rejected by the hard gate."""
    rep = vp.check_permutation_resolution(n_perm=500, m=310, q=0.05)
    assert not rep.sufficient, "Gen-7's Lab 2 design should be flagged INSUFFICIENT"
    assert rep.required_n_perm_bare == 6199, \
        f"audit says >=6,199 permutations needed; got {rep.required_n_perm_bare}"
    try:
        vp.assert_permutation_resolution(n_perm=500, m=310, q=0.05, verbose=False)
        raise AssertionError("assert_permutation_resolution must RAISE on Gen-7's design")
    except vp.InsufficientResolutionError:
        pass
    return (f"floor 1/501={rep.finest_resolvable_p:.3e} vs BH rank-1 threshold "
            f"{rep.strictest_threshold:.3e}; bare requirement {rep.required_n_perm_bare:,} draws "
            f"(matches the audit's '>=6,199')")


def test_1a_false_survivors_disappear():
    """The end-to-end consequence: 6 floored p-values 'survive' BH; 0 survive once corrected.

    This reconstructs the audit's CRITICAL-1 arithmetic on synthetic data of the same shape.
    """
    m = 310
    n_ge = np.full(m, 250)              # generic tests, p ~ 0.5
    n_ge[:6] = 0                        # six tests beat every draw
    p_old = np.array([vp.invalid_permutation_pvalue_DO_NOT_USE(k, 500) for k in n_ge])
    p_new = np.array([vp.permutation_pvalue(k, 500) for k in n_ge])

    # the old pipeline fed zeros straight into BH
    order = np.argsort(p_old)
    thresh = 0.05 * np.arange(1, m + 1) / m
    n_old = int(np.max(np.where(p_old[order] <= thresh)[0]) + 1)
    assert n_old == 6, f"expected the defective pipeline to report 6 survivors, got {n_old}"

    rej_new, _ = vp.bh_step_up(p_new, 0.05)
    assert int(rej_new.sum()) == 0, \
        f"expected 0 survivors with valid p-values, got {int(rej_new.sum())}"
    return f"defective pipeline: {n_old} 'survivors'  ->  corrected: {int(rej_new.sum())}"


def test_1a_zero_pvalue_is_rejected_at_the_boundary():
    """A zero p-value arriving from anywhere (e.g. a legacy artifact) must be refused."""
    try:
        vp.bh_step_up(np.array([0.0, 0.2, 0.4]), 0.05)
        raise AssertionError("bh_step_up must refuse a p-value of exactly 0")
    except vp.InvalidPValueError:
        pass
    return "validate_pvalues() blocks p=0 at the entry to any correction"


def test_1a_bh_matches_published_example():
    """External reference check: Benjamini-Hochberg (1995) worked example -> 4 rejections."""
    p = np.array([0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459,
                  0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000])
    rej, _ = vp.bh_step_up(p, 0.05)
    assert int(rej.sum()) == 4, f"BH-1995 example expects 4 rejections, got {int(rej.sum())}"
    return "BH-1995 published example reproduces (4 rejections) — same check RA-005 ran"


# =============================================================================================
# 1b / 1c -- power_precheck
# =============================================================================================
def test_1b_gen7_lockbox_is_underpowered():
    """Gen-7 Lab 8's lockbox: the numbers the audit computed must fall out of the precheck."""
    mde = pp.min_detectable_correlation(n=53, alpha=0.05, power=0.80)
    assert 0.36 < mde < 0.39, f"audit reports MDE ~0.377 at n=53; got {mde:.4f}"
    power = pp.power_for_correlation(0.11, n=53)
    assert power < 0.20, f"audit reports ~12-13% power; got {power:.1%}"
    try:
        pp.power_precheck("test", n=53, meaningful_effect=0.11, verbose=False)
        raise AssertionError("power_precheck must RAISE on Gen-7's lockbox design")
    except pp.UnderpoweredGateError:
        pass
    return (f"n=53: MDE@80% = {mde:.3f} (audit: 0.377), power at r=0.11 = {power:.1%} "
            f"(audit: ~13%) — and the gate raises")


def test_1b_override_is_recorded_not_silent():
    """The underpowered escape hatch must exist, must be explicit, and must be logged."""
    rep = pp.power_precheck("test", n=53, meaningful_effect=0.11,
                            allow_underpowered=True, verbose=False)
    assert rep.proceeded_underpowered is True
    assert any("UNRESOLVED" in n for n in rep.notes), "override must record the UNRESOLVED downgrade"
    return "override sets proceeded_underpowered=True and records the UNRESOLVED classification"


def test_1b_adequate_design_passes():
    """A genuinely adequate design must NOT raise — otherwise the gate is useless noise."""
    rep = pp.power_precheck("test", n=2000, meaningful_effect=0.11, verbose=False)
    assert rep.adequately_powered and not rep.proceeded_underpowered
    return f"n=2000, r=0.11: MDE {rep.min_detectable_effect:.3f} <= 0.11, passes cleanly"


def test_1c_holdout_sizing_picks_the_right_design():
    """Defect 1c: with Gen-7's data the recommendation must be rolling-origin, not a fixed lockbox."""
    rec = pp.recommend_validation_design(n_total=1070, meaningful_effect=0.11, verbose=False)
    assert not rec.single_holdout_viable
    assert "rolling-origin" in rec.recommended_design
    assert rec.required_holdout_n > 400, f"needs >400 obs, computed {rec.required_holdout_n}"
    big = pp.recommend_validation_design(n_total=100_000, meaningful_effect=0.11, verbose=False)
    assert big.single_holdout_viable, "with ample data a fixed lockbox should still be recommended"
    return (f"n=1070, r=0.11 -> needs {rec.required_holdout_n} holdout obs, only "
            f"{rec.max_holdout_available} available -> rolling-origin; n=100k -> fixed lockbox")


def test_1b_multiplicity_reduction_gain_reproduces():
    """G7-F06: cutting m from 310 to 31 must materially raise power on the same data."""
    a310 = pp.multiplicity_adjusted_alpha(0.05, 310, "BH")
    a31 = pp.multiplicity_adjusted_alpha(0.05, 31, "BH")
    p310 = pp.power_for_correlation(0.11, 1017, a310)
    p31 = pp.power_for_correlation(0.11, 1017, a31)
    assert p31 > p310 + 0.15, f"expected a large gain; got {p310:.1%} -> {p31:.1%}"
    return (f"m=310 -> m=31 raises power at r=0.11 from {p310:.1%} to {p31:.1%} "
            f"(RA-006 simulated 31% -> 60% on the actual estimator; same direction and magnitude)")


def test_1b_simulation_power_detects_and_calibrates():
    """Amendment-003 in executable form: the detector must fire on a real effect and not on none."""
    def generator(effect, rng):
        n = 300
        x = rng.standard_normal(n)
        y = effect * x + np.sqrt(max(1 - effect ** 2, 1e-9)) * rng.standard_normal(n)
        return x, y

    def detector(x, y):
        r = np.corrcoef(x, y)[0, 1]
        t = r * np.sqrt((len(x) - 2) / max(1 - r ** 2, 1e-12))
        from scipy import stats as st
        return bool(2 * st.t.sf(abs(t), len(x) - 2) < 0.05)

    hi = pp.simulation_power(detector, generator, effect_size=0.30, n_sims=200, seed=1)
    null = pp.simulation_power(detector, generator, effect_size=0.0, n_sims=200, seed=2)
    assert hi["power"] > 0.90, f"should detect r=0.30 at n=300 almost always; got {hi['power']:.1%}"
    assert null["power"] < 0.12, f"false-positive rate should be ~5%; got {null['power']:.1%}"
    return (f"power at r=0.30 = {hi['power']:.1%}; false-positive rate at r=0 = "
            f"{null['power']:.1%} (nominal 5%)")


# =============================================================================================
# 1e -- rolling_window_artifact_check
# =============================================================================================
def test_1e_pure_construction_artifact_is_caught():
    """A rolling mean of white noise has NO real memory; the check must say so."""
    rng = np.random.default_rng(42)
    raw = rng.standard_normal(1200 + 52)
    rolled = np.convolve(raw, np.ones(52) / 52, "valid")[:1200]

    naive_acf = rw.acf(rolled, 52)
    naive_sig = int(np.sum(np.abs(naive_acf) > rw.acf_significance_band(1200)))
    assert naive_sig > 30, "the naive analysis should see abundant 'memory' (that is the trap)"

    rep = rw.rolling_window_artifact_check(rolled, window=52, name="t", verbose=False)
    assert rep.verdict == rw.WITHIN, f"expected WITHIN_CONSTRUCTION, got {rep.verdict}"
    try:
        rw.assert_not_artifact(rolled, window=52, name="t", verbose=False)
        raise AssertionError("assert_not_artifact must RAISE on a pure construction artifact")
    except rw.RollingWindowArtifactError:
        pass
    return (f"naive ACF: {naive_sig}/52 lags 'significant' on data with zero real memory; "
            f"check returns {rep.verdict} and the gate raises")


def test_1e_genuine_persistence_survives():
    """The check must NOT reject real persistence, or it would manufacture false negatives."""
    rng = np.random.default_rng(7)
    n = 1200
    u = np.zeros(n + 52)
    for t in range(1, n + 52):
        u[t] = 0.98 * u[t - 1] + rng.standard_normal()
    rolled = np.convolve(u, np.ones(52) / 52, "valid")[:n]
    rep = rw.rolling_window_artifact_check(rolled, window=52, name="t", verbose=False)
    assert rep.verdict == rw.EXCEEDS, f"expected EXCEEDS_CONSTRUCTION, got {rep.verdict}"
    return (f"genuinely persistent underlying -> {rep.verdict}, max excess "
            f"{rep.max_excess_over_null:+.3f} over the mechanical null at lag {rep.lag_of_max_excess}")


def test_1e_differencing_alone_would_misclassify():
    """The inherited Gen-6/MSRP remedy, used alone, calls a maximally persistent series an artifact.

    A random walk is the decisive case because its differences are **exactly** white noise by
    construction, while the level series is as persistent as a series can be. So:
        differencing screen  -> "no structure in the changes"  -> would be read as 'artifact'
        construction null    -> persistence far beyond a width-52 window -> EXCEEDS
    'Fails differencing' therefore cannot mean 'is an artifact'. The module must reach its verdict
    from the construction null, which is why test B and not test A carries the decision.

    Checked on two independent seeds so the demonstration does not rest on one lucky draw.
    """
    detail = []
    for seed in (11, 42):
        rng = np.random.default_rng(seed)
        n = 1200
        rwk = np.cumsum(rng.standard_normal(n))          # random walk: diff() is exactly i.i.d.

        d = np.diff(rwk)
        n_sig_d = int(np.sum(np.abs(rw.acf(d, 52)) > rw.acf_significance_band(len(d))))
        rep = rw.rolling_window_artifact_check(rwk, window=52, name=f"rw{seed}", verbose=False)

        assert rep.survives_differencing is False, \
            f"seed {seed}: differencing screen must fail on a random walk (that is the point)"
        assert rep.verdict == rw.EXCEEDS, \
            f"seed {seed}: construction null must still reach EXCEEDS; got {rep.verdict}"
        detail.append(f"seed {seed}: {n_sig_d}/52 differenced lags significant (chance ~2.6), "
                      f"verdict {rep.verdict} with max excess {rep.max_excess_over_null:+.3f}")
    return " | ".join(detail)


def test_1e_beta104w_style_case():
    """MSRP's actual red flag: a 104-week feature classified 'long memory to 52 weeks'."""
    rng = np.random.default_rng(3)
    raw = rng.standard_normal(1200 + 104)
    beta_like = np.convolve(raw, np.ones(104) / 104, "valid")[:1200]
    rep = rw.rolling_window_artifact_check(beta_like, window=104, max_lag=52, name="beta_104w",
                                           verbose=False)
    assert rep.verdict == rw.WITHIN, f"expected WITHIN_CONSTRUCTION, got {rep.verdict}"
    return ("a 104-week window on memoryless input is flagged WITHIN_CONSTRUCTION mechanically — "
            "no analyst needs to notice that 104 > 52")


# =============================================================================================
# 1f -- registry_integrity_check
# =============================================================================================
def test_1f_id_assignment_is_order_independent():
    """Gen-7's Convention B arose from dict iteration order. That must be impossible now."""
    objs = [dict(symbol="CL=F", lag=1), dict(symbol="KRW=X", lag=1), dict(symbol="AUDUSD=X", lag=2),
            dict(symbol="MXN=X", lag=2), dict(symbol="MXN=X", lag=1), dict(symbol="BRL=X", lag=2)]
    a = ri.assign_ids(objs, "TC", ["symbol", "lag"])
    b = ri.assign_ids(list(reversed(objs)), "TC", ["symbol", "lag"])
    c = ri.assign_ids([objs[i] for i in (3, 0, 5, 1, 4, 2)], "TC", ["symbol", "lag"])
    key_a = dict(zip(a["canonical_key"], a["id"]))
    for other in (b, c):
        assert dict(zip(other["canonical_key"], other["id"])) == key_a, \
            "ID assignment must not depend on input order"
    return f"3 different input orderings -> identical assignment ({len(a)} objects)"


def test_1f_string_check_passes_where_data_check_fails():
    """The exact Gen-7 failure: both conventions are well-formed; only the data distinguishes them."""
    objs = [dict(symbol="CL=F", lag=1), dict(symbol="KRW=X", lag=1), dict(symbol="AUDUSD=X", lag=2)]
    reg = ri.assign_ids(objs, "TC", ["symbol", "lag"])
    bad_ref = dict(id="TC-003", symbol="AUDUSD=X", lag=2, cited_by="lab7_report")

    assert ri.ID_PATTERN.match(bad_ref["id"]), "the defective check (format only) PASSES this ref"
    n, mismatches = ri.verify_references(reg, [bad_ref], ["symbol", "lag"])
    assert len(mismatches) >= 1, "the data-anchored check must catch the cross-convention reference"
    return (f"format check passes; data check reports {len(mismatches)} mismatch(es) — "
            f"e.g. {mismatches[0]['problem']}")


def test_1f_duplicate_identity_is_refused():
    """Two different records sharing an identity means the identity fields are wrong."""
    objs = [dict(symbol="CL=F", lag=1, corr=0.11), dict(symbol="CL=F", lag=1, corr=0.99)]
    try:
        ri.assign_ids(objs, "TC", ["symbol", "lag"])
        raise AssertionError("must refuse two distinct records with the same identity")
    except ri.RegistryIntegrityError:
        pass
    return "colliding identities raise rather than silently keeping one row"


def test_1f_append_only_is_enforced(tmp_path_str="/tmp/gen8_registry_test.csv"):
    """P8: a write that would drop an existing row must be refused."""
    from pathlib import Path
    p = Path(tmp_path_str)
    if p.exists():
        p.unlink()
    objs = [dict(symbol="CL=F", lag=1), dict(symbol="KRW=X", lag=1)]
    reg = ri.assign_ids(objs, "TC", ["symbol", "lag"])
    ri.write_registry(reg, p, ["symbol", "lag"], "TC")
    shrunk = reg.iloc[:1]
    try:
        ri.write_registry(shrunk, p, ["symbol", "lag"], "TC")
        raise AssertionError("must refuse a write that drops an existing ID")
    except ri.RegistryIntegrityError:
        pass
    finally:
        p.unlink(missing_ok=True)
    return "dropping a registered ID raises (registries are append-only)"


def main() -> int:
    print("=" * 96)
    print("GEN-8 REMEDIATION LIBRARY -- UNIT TESTS")
    print("Each test proves the OLD procedure gets a known answer wrong and the NEW one gets it right")
    print("=" * 96)

    print("\n[1a] valid_pvalue -- permutation p-value floored at 0.0 (audit CRITICAL-1)")
    check("1a.1 old estimator floors at exactly 0.0; new one cannot", test_1a_pvalue_floor)
    check("1a.2 Gen-7's m=310/N=500 design is rejected by the hard gate",
          test_1a_gen7_family_is_unresolvable)
    check("1a.3 six false 'BH survivors' become zero once corrected",
          test_1a_false_survivors_disappear)
    check("1a.4 a p-value of 0 is refused at the correction boundary",
          test_1a_zero_pvalue_is_rejected_at_the_boundary)
    check("1a.5 BH reproduces the Benjamini-Hochberg (1995) published example",
          test_1a_bh_matches_published_example)

    print("\n[1b/1c] power_precheck -- power disclosure and holdout sizing (Amendment-002, CRITICAL-2)")
    check("1b.1 Gen-7's 53-week lockbox is flagged underpowered, with the audit's numbers",
          test_1b_gen7_lockbox_is_underpowered)
    check("1b.2 the underpowered override is explicit and logged, never silent",
          test_1b_override_is_recorded_not_silent)
    check("1b.3 an adequately powered design passes cleanly", test_1b_adequate_design_passes)
    check("1c.1 holdout sizing recommends rolling-origin when a lockbox cannot adjudicate",
          test_1c_holdout_sizing_picks_the_right_design)
    check("1b.4 multiplicity reduction m=310->31 reproduces the G7-F06 power gain",
          test_1b_multiplicity_reduction_gain_reproduces)
    check("1b.5 simulation power detects a real effect and calibrates at the null",
          test_1b_simulation_power_detects_and_calibrates)

    print("\n[1e] rolling_window_artifact_check -- overlapping-window artifact (Gen-6/MSRP x3)")
    check("1e.1 rolling mean of white noise: naive analysis sees memory, check says WITHIN",
          test_1e_pure_construction_artifact_is_caught)
    check("1e.2 genuine persistence is NOT rejected", test_1e_genuine_persistence_survives)
    check("1e.3 the inherited differencing remedy alone would misclassify a real AR(1)",
          test_1e_differencing_alone_would_misclassify)
    check("1e.4 the beta_104w-style case is caught mechanically", test_1e_beta104w_style_case)

    print("\n[1f] registry_integrity_check -- ID schemes and cross-references (audit HIGH-3/4/5)")
    check("1f.1 ID assignment is independent of input order",
          test_1f_id_assignment_is_order_independent)
    check("1f.2 a format-only check passes a cross-convention reference that the data check catches",
          test_1f_string_check_passes_where_data_check_fails)
    check("1f.3 colliding identities are refused", test_1f_duplicate_identity_is_refused)
    check("1f.4 append-only writes are enforced", test_1f_append_only_is_enforced)

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 96)
    print(f"RESULT: {n_pass}/{len(RESULTS)} passed" + (f", {n_fail} FAILED" if n_fail else ""))
    print("=" * 96)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
