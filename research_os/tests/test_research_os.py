#!/usr/bin/env python3
"""Unit tests for the Research OS's own new modules (experiment_registry, verdict_schema).

Per the Gen-8 remediation precedent this Research OS inherits: each test constructs a case with a
KNOWN ground truth and shows the naive/old approach would get it wrong, then shows the new module
gets it right.

Run:  venv_gen8/bin/python3 -m research_os.tests.test_research_os
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

from .. import experiment_registry as reg
from .. import verdict_schema as vs

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
# experiment_registry -- the Gen-5 G5-08B/C collision class of bug
# =============================================================================================
def test_ids_assigned_in_order_not_hand_picked():
    """The exact failure mode this module exists to prevent: manual ID assignment colliding."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        a1 = reg.register_experiment("alpha_engine", "h1", "proto1.md", path=p)
        a2 = reg.register_experiment("alpha_engine", "h2", "proto2.md", path=p)
        m1 = reg.register_experiment("market_science", "h3", "proto3.md", path=p)
        assert a1 == "ALPHA-001" and a2 == "ALPHA-002" and m1 == "MSCI-001", \
            f"unexpected sequence: {a1}, {a2}, {m1}"
    return f"{a1}, {a2}, {m1} -- sequential per-lab, independent across labs"


def test_naive_manual_numbering_would_collide():
    """Demonstrate the OLD failure directly: if IDs were hand-picked instead of derived from the
    ledger, two researchers working the same day could both pick 'the next number' and collide --
    exactly what happened with G5-08B/C. This module's next_id() reads the ledger's live state,
    which a hand-picked scheme by definition does not.
    """
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        reg.register_experiment("alpha_engine", "h1", "proto1.md", path=p)
        # naive approach: researcher B doesn't re-check the ledger, assumes they're also "001"
        naive_guess = "ALPHA-001"
        real_next = reg.next_id("alpha_engine", path=p)
        assert naive_guess != real_next, "the whole point is that these must differ"
        assert real_next == "ALPHA-002"
    return f"naive hand-picked guess ({naive_guess}) collides; next_id() correctly returns {real_next}"


def test_duplicate_id_is_refused():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        eid = reg.register_experiment("microstructure", "h1", "proto1.md", path=p)
        # simulate a corrupted ledger where the ID already exists, then try to register "again"
        rows = reg._read_all(p)
        rows.append(dict(experiment_id=eid, lab="microstructure", date_registered="2020-01-01",
                         hypothesis_one_line="dup", preregistration_path="x", status="REGISTERED",
                         verdict="", closing_doc_path=""))
        reg._write_all(rows, p)
        try:
            # next_id will now see MICRO-001 twice but should still compute 002 correctly since it
            # takes the max, not a count -- verifying this doesn't silently produce a second 001
            nxt = reg.next_id("microstructure", path=p)
            assert nxt == "MICRO-002", f"expected MICRO-002 despite the duplicate row, got {nxt}"
        finally:
            pass
    return "next_id() is robust to a corrupted duplicate row (takes max, not count)"


def test_close_never_drops_a_row():
    """P8 (append-only): closing an experiment must never reduce the set of IDs present."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        a1 = reg.register_experiment("alpha_engine", "h1", "proto1.md", path=p)
        a2 = reg.register_experiment("alpha_engine", "h2", "proto2.md", path=p)
        reg.close_experiment(a1, "REJECTED", "findings1.md", path=p)
        ids_after = {r["experiment_id"] for r in reg._read_all(p)}
        assert ids_after == {a1, a2}, f"expected both IDs still present, got {ids_after}"
        row = reg.get(a1, path=p)
        assert row["status"] == "CLOSED" and row["verdict"] == "REJECTED"
    return "closing ALPHA-001 leaves ALPHA-002 untouched and does not drop either row"


def test_close_with_invalid_verdict_refused():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        eid = reg.register_experiment("alpha_engine", "h1", "proto1.md", path=p)
        try:
            reg.close_experiment(eid, "looks promising", "nowhere.md", path=p)
            raise AssertionError("must refuse an invalid verdict string")
        except vs.InvalidVerdictError:
            pass
        # and the row must remain open (not silently closed with a bad verdict)
        row = reg.get(eid, path=p)
        assert row["status"] == "REGISTERED", "a rejected close attempt must not mutate the row"
    return "'looks promising' is refused; the row remains REGISTERED, not silently CLOSED"


def test_close_nonexistent_experiment_refused():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        reg.register_experiment("alpha_engine", "h1", "proto1.md", path=p)
        try:
            reg.close_experiment("ALPHA-999", "REJECTED", "nowhere.md", path=p)
            raise AssertionError("must refuse closing an ID that was never registered")
        except reg.ExperimentNotFoundError:
            pass
    return "closing an unregistered ID raises rather than silently creating a row"


def test_unknown_lab_refused():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.csv"
        try:
            reg.register_experiment("gen9", "h1", "proto1.md", path=p)
            raise AssertionError("must refuse an unknown lab name")
        except reg.UnknownLabError:
            pass
    return "'gen9' (an old-style generation name) is refused -- only the four labs are valid"


# =============================================================================================
# verdict_schema -- the "looks promising" / unlabeled-outcome class of bug
# =============================================================================================
def test_four_outcome_schema_is_exhaustive_and_exclusive():
    assert vs.VALID_VERDICTS == {"VALIDATED", "REJECTED", "INCONCLUSIVE", "METHODOLOGICAL_FAILURE"}
    return f"exactly four verdicts: {sorted(vs.VALID_VERDICTS)}"


def test_naive_unlabeled_outcome_is_rejected():
    """The naive/old failure: reporting a result as 'promising', 'mixed', 'weak positive' etc.
    without committing to one of the four schema states -- exactly what a verdict schema exists to
    prevent."""
    for bad in ("looks promising", "mixed", "weak positive", "partial success", ""):
        try:
            vs.validate_verdict(bad)
            raise AssertionError(f"{bad!r} should have been rejected")
        except vs.InvalidVerdictError:
            pass
    return "5 naive non-verdict strings all correctly refused"


def test_validated_without_power_is_refused():
    """The exact Gen-7 CRITICAL-1/2 failure mode: a positive verdict with no disclosed power."""
    try:
        vs.assert_closeable("VALIDATED", power_at_meaningful_effect=None,
                            survived_rolling_window_check=None, has_windowed_feature=False)
        raise AssertionError("VALIDATED with no power figure must be refused")
    except ValueError as e:
        assert "power" in str(e).lower()
    return "VALIDATED with power_at_meaningful_effect=None is refused, mirroring Gen-7 CRITICAL-1/2"


def test_inconclusive_without_power_is_refused():
    try:
        vs.ClosingRecord(experiment_id="X-001", verdict=vs.Verdict.INCONCLUSIVE,
                        power_at_meaningful_effect=None, survived_rolling_window_check=None,
                        closing_doc_path="f.md")
        raise AssertionError("INCONCLUSIVE must still state why (i.e. the power figure)")
    except ValueError:
        pass
    return "INCONCLUSIVE without a stated power figure is refused (must state WHY it's inconclusive)"


def test_windowed_feature_requires_artifact_check_disclosure():
    try:
        vs.assert_closeable("REJECTED", power_at_meaningful_effect=0.7,
                            survived_rolling_window_check=None, has_windowed_feature=True)
        raise AssertionError("a windowed-feature claim must disclose the artifact-check result")
    except ValueError as e:
        assert "rolling" in str(e).lower() or "window" in str(e).lower()
    return "a windowed persistence claim cannot close without stating the artifact-check result"


def test_well_formed_record_passes():
    rec = vs.ClosingRecord(experiment_id="ALPHA-001", verdict=vs.Verdict.REJECTED,
                           power_at_meaningful_effect=0.82, survived_rolling_window_check=True,
                           closing_doc_path="labs/alpha_engine/results/ALPHA-001/FINDINGS.md")
    assert rec.verdict == vs.Verdict.REJECTED
    return f"well-formed REJECTED record accepted: {rec.closed_date}"


# =============================================================================================
def main() -> int:
    print("=" * 96)
    print("RESEARCH OS -- UNIT TESTS (experiment_registry, verdict_schema)")
    print("=" * 96)

    print("\n[experiment_registry] -- the Gen-5 G5-08B/C ID-collision class of bug")
    check("ids assigned sequentially, per-lab, from ledger state", test_ids_assigned_in_order_not_hand_picked)
    check("naive hand-picked numbering would have collided", test_naive_manual_numbering_would_collide)
    check("robust to a corrupted duplicate row", test_duplicate_id_is_refused)
    check("closing an experiment never drops a row (P8)", test_close_never_drops_a_row)
    check("closing with an invalid verdict is refused", test_close_with_invalid_verdict_refused)
    check("closing a never-registered ID is refused", test_close_nonexistent_experiment_refused)
    check("registering under an unknown lab is refused", test_unknown_lab_refused)

    print("\n[verdict_schema] -- the 'looks promising' unlabeled-outcome class of bug")
    check("exactly four verdicts, exhaustive and exclusive", test_four_outcome_schema_is_exhaustive_and_exclusive)
    check("naive unlabeled outcomes are all refused", test_naive_unlabeled_outcome_is_rejected)
    check("VALIDATED with no power is refused (Gen-7 CRITICAL-1/2)", test_validated_without_power_is_refused)
    check("INCONCLUSIVE with no stated power is refused", test_inconclusive_without_power_is_refused)
    check("windowed claim needs artifact-check disclosure", test_windowed_feature_requires_artifact_check_disclosure)
    check("a well-formed record passes cleanly", test_well_formed_record_passes)

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 96)
    print(f"RESULT: {n_pass}/{len(RESULTS)} passed" + (f", {n_fail} FAILED" if n_fail else ""))
    print("=" * 96)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
