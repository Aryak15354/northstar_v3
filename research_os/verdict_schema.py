#!/usr/bin/env python3
"""The four-outcome verdict schema, made structural rather than a naming convention.

Every experiment run under any of the four Northstar Institute labs closes with EXACTLY ONE of four
verdicts. This is not a new invention -- it is the convention MSRP, Gen-5, and Gen-7 already
independently converged on, made into an enforced schema so no experiment can close as "looks
promising" or any other unlabelled state.

    VALIDATED              -- the pre-registered hypothesis was tested by a design demonstrated
                              capable of detecting the pre-specified minimum effect, and the effect
                              was found, surviving every gate the lab's charter requires.
    REJECTED               -- the pre-registered hypothesis was tested by a design demonstrated
                              capable of detecting the pre-specified minimum effect, and the effect
                              was NOT found. This is a negative result with power behind it.
    INCONCLUSIVE           -- the design was NOT capable of detecting the pre-specified minimum
                              effect (underpowered), OR a required input (data, a prior validated
                              finding) was unavailable. Per Amendment-003 / Gen-8's standing rule,
                              INCONCLUSIVE is not a weaker synonym for REJECTED -- conflating the two
                              is exactly the error Gen-7's original Paper A made.
    METHODOLOGICAL_FAILURE -- the experiment's own procedure was found invalid (a bug, a broken null,
                              a design that could not have answered the question as built). The
                              scientific question itself remains untouched and open for re-attempt
                              under a corrected design.

A verdict MUST be attached before an experiment's status can be set to CLOSED in the master registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Verdict(str, Enum):
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    METHODOLOGICAL_FAILURE = "METHODOLOGICAL_FAILURE"


VALID_VERDICTS = {v.value for v in Verdict}


class InvalidVerdictError(ValueError):
    """A verdict string that is not one of the four schema values."""


def validate_verdict(v: str) -> Verdict:
    """Coerce and validate a verdict string. Raises on anything not in the four-value schema."""
    if v not in VALID_VERDICTS:
        raise InvalidVerdictError(
            f"{v!r} is not a valid verdict. Must be one of {sorted(VALID_VERDICTS)}. "
            f"'Looks promising', 'partial success', 'mixed', 'weak positive', etc. are not verdicts "
            f"-- resolve to REJECTED (tested, not found), INCONCLUSIVE (untestable as designed), or "
            f"state explicitly why VALIDATED/METHODOLOGICAL_FAILURE applies instead."
        )
    return Verdict(v)


@dataclass
class ClosingRecord:
    """The minimum information required to close an experiment. Enforced, not advisory."""
    experiment_id: str
    verdict: Verdict
    power_at_meaningful_effect: float | None      # None only permitted for METHODOLOGICAL_FAILURE
    survived_rolling_window_check: bool | None     # None permitted only if no windowed feature involved
    closing_doc_path: str
    closed_date: str = ""

    def __post_init__(self):
        if not self.closed_date:
            self.closed_date = date.today().isoformat()
        if self.verdict == Verdict.INCONCLUSIVE and self.power_at_meaningful_effect is None:
            raise ValueError(
                "INCONCLUSIVE requires power_at_meaningful_effect to be stated (even if it's the "
                "reason for the INCONCLUSIVE verdict) -- 'we don't know why it's inconclusive' is "
                "not a valid closing record.")
        if self.verdict in (Verdict.VALIDATED, Verdict.REJECTED) and self.power_at_meaningful_effect is None:
            raise ValueError(
                f"{self.verdict.value} requires a stated power_at_meaningful_effect -- a "
                f"VALIDATED or REJECTED verdict with no disclosed power is exactly the Gen-7 "
                f"CRITICAL-1/2 failure mode this schema exists to prevent.")


def assert_closeable(verdict: str, power_at_meaningful_effect: float | None,
                     survived_rolling_window_check: bool | None,
                     has_windowed_feature: bool) -> None:
    """Hard gate: raise if an experiment's closing state does not meet the schema's requirements.

    Call this before writing a CLOSED status to the master registry.
    """
    v = validate_verdict(verdict)
    if v in (Verdict.VALIDATED, Verdict.REJECTED) and power_at_meaningful_effect is None:
        raise ValueError(f"{v.value} requires power_at_meaningful_effect to be logged before closing.")
    if has_windowed_feature and survived_rolling_window_check is None:
        raise ValueError(
            "this experiment involves a windowed/rolling feature and a persistence, memory, or "
            "autocorrelation claim -- survived_rolling_window_check must be stated (True/False), "
            "with the Gen-8 conservative-screen caveat disclosed inline in the closing document, "
            "before this experiment can close.")


if __name__ == "__main__":
    print("Four-outcome verdict schema:", sorted(VALID_VERDICTS))
    print()
    print("Demonstration: the exact Gen-7 failure this schema is designed to catch --")
    try:
        assert_closeable("VALIDATED", power_at_meaningful_effect=None,
                         survived_rolling_window_check=None, has_windowed_feature=False)
    except ValueError as e:
        print(f"  REJECTED at the gate: {e}")
    print()
    print("A correctly-formed INCONCLUSIVE closing record:")
    rec = ClosingRecord(experiment_id="ALPHA-001", verdict=Verdict.INCONCLUSIVE,
                        power_at_meaningful_effect=0.675, survived_rolling_window_check=None,
                        closing_doc_path="labs/alpha_engine/results/ALPHA-001/FINDINGS.md")
    print(" ", rec)
