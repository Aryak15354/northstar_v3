#!/usr/bin/env python3
"""Assigns every new Northstar Institute experiment a permanent ID, in exactly one place.

Fixes the exact failure mode Gen-5's own decision log records: G5-08B/C, two new Paper-3B
experiments that silently reused already-registered IDs, caught only by a full audit. That was a
MANUAL numbering scheme. This module makes manual numbering structurally impossible: an ID is only
ever produced by `register_experiment`, which reads the single shared ledger
(`MASTER_EXPERIMENT_REGISTRY.csv`) to find the next free number for that lab, and no other code path
in any of the four labs is permitted to mint an ID.

ID format: `{LAB_PREFIX}-{NNN}` -- ALPHA-001, MSCI-014, MICRO-002, PORT-007. Never reassigned, never
reused even if an experiment is later judged METHODOLOGICAL_FAILURE (the ID and its row stay in the
ledger permanently, per the append-only / never-silently-rewrite-history discipline every lab charter
inherits).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

from .verdict_schema import Verdict, validate_verdict

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "MASTER_EXPERIMENT_REGISTRY.csv"

LAB_PREFIX = {
    "alpha_engine": "ALPHA",
    "market_science": "MSCI",
    "microstructure": "MICRO",
    "portfolio_engineering": "PORT",
}
VALID_LABS = set(LAB_PREFIX)

FIELDS = ["experiment_id", "lab", "date_registered", "hypothesis_one_line",
         "preregistration_path", "status", "verdict", "closing_doc_path"]


class UnknownLabError(ValueError):
    pass


class DuplicateIDError(RuntimeError):
    """Would have assigned an ID that already exists -- indicates a race or a manual-numbering bug."""


class ExperimentNotFoundError(KeyError):
    pass


def _read_all(path: Path = REGISTRY_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict], path: Path = REGISTRY_PATH) -> None:
    """Rewrites the file from `rows`. Callers must never pass a `rows` list with an ID removed --
    `register_experiment`/`close_experiment` only ever append or mutate in place, never drop a row.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def next_id(lab: str, path: Path = REGISTRY_PATH) -> str:
    """The next free ID for `lab`, derived from the ledger's own current state -- never hand-picked."""
    if lab not in VALID_LABS:
        raise UnknownLabError(f"{lab!r} is not a lab; must be one of {sorted(VALID_LABS)}")
    prefix = LAB_PREFIX[lab]
    rows = _read_all(path)
    existing = [r["experiment_id"] for r in rows if r["lab"] == lab]
    nums = []
    for eid in existing:
        try:
            nums.append(int(eid.split("-")[-1]))
        except (ValueError, IndexError):
            continue
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}-{n:03d}"


def register_experiment(lab: str, hypothesis_one_line: str, preregistration_path: str,
                        path: Path = REGISTRY_PATH) -> str:
    """Register a new experiment. Returns the assigned, permanent ID. APPENDS ONLY -- never drops a row.

    Must be called AFTER the pre-registration document exists on disk (per every lab charter's
    binding requirement: pre-registration before any result-producing code runs) -- this function
    does not itself enforce that the path exists, because a pre-registration is sometimes drafted in
    the same commit as its own registration; the discipline is enforced by review, not by this gate.
    """
    if lab not in VALID_LABS:
        raise UnknownLabError(f"{lab!r} is not a lab; must be one of {sorted(VALID_LABS)}")
    rows = _read_all(path)
    eid = next_id(lab, path)
    if any(r["experiment_id"] == eid for r in rows):
        raise DuplicateIDError(f"{eid} already exists in the registry -- this should be unreachable; "
                               f"if it happened, two processes raced on next_id().")
    rows.append(dict(experiment_id=eid, lab=lab, date_registered=date.today().isoformat(),
                     hypothesis_one_line=hypothesis_one_line,
                     preregistration_path=preregistration_path,
                     status="REGISTERED", verdict="", closing_doc_path=""))
    _write_all(rows, path)
    return eid


def close_experiment(experiment_id: str, verdict: str, closing_doc_path: str,
                     path: Path = REGISTRY_PATH) -> None:
    """Close a registered experiment with one of the four schema verdicts.

    Updates status/verdict/closing_doc_path on the EXISTING row -- the same in-place state-machine
    transition GEN7_RESEARCH_CHARTER.md's own object registries use (Candidate -> Validated ->
    Promoted -> Frozen on one row, never a new row per state). Never deletes a row; never reassigns
    an experiment_id.
    """
    v = validate_verdict(verdict)  # raises InvalidVerdictError for anything outside the schema
    rows = _read_all(path)
    ids_before = {r["experiment_id"] for r in rows}
    for r in rows:
        if r["experiment_id"] == experiment_id:
            r["status"] = "CLOSED"
            r["verdict"] = v.value
            r["closing_doc_path"] = closing_doc_path
            assert {rr["experiment_id"] for rr in rows} == ids_before, \
                "internal error: close_experiment must never change the set of IDs present"
            _write_all(rows, path)
            return
    raise ExperimentNotFoundError(f"{experiment_id} is not in the registry -- cannot close an "
                                  f"experiment that was never registered.")


def get(experiment_id: str, path: Path = REGISTRY_PATH) -> dict:
    for r in _read_all(path):
        if r["experiment_id"] == experiment_id:
            return r
    raise ExperimentNotFoundError(experiment_id)


def all_for_lab(lab: str, path: Path = REGISTRY_PATH) -> list[dict]:
    return [r for r in _read_all(path) if r["lab"] == lab]


if __name__ == "__main__":
    import tempfile

    print("Demonstration: the Gen-5 G5-08B/C collision, and why it cannot recur here.")
    print("(runs against a TEMPORARY ledger, never the real MASTER_EXPERIMENT_REGISTRY.csv)")
    print()
    with tempfile.TemporaryDirectory() as td:
        demo_path = Path(td) / "demo_registry.csv"
        print("Registering three experiments across two labs:")
        a1 = register_experiment("alpha_engine", "test hypothesis A1",
                                 "labs/alpha_engine/protocols/demo1.md", path=demo_path)
        m1 = register_experiment("market_science", "test hypothesis M1",
                                 "labs/market_science/protocols/demo1.md", path=demo_path)
        a2 = register_experiment("alpha_engine", "test hypothesis A2",
                                 "labs/alpha_engine/protocols/demo2.md", path=demo_path)
        print(f"  {a1}, {m1}, {a2}")
        assert a1 == "ALPHA-001" and a2 == "ALPHA-002" and m1 == "MSCI-001", "unexpected ID sequence"
        print("  IDs assigned in order, per-lab, from the ledger's own state -- not hand-picked.")
        print()
        print("Attempting to close ALPHA-001 with an invalid verdict ('looks promising'):")
        try:
            close_experiment(a1, "looks promising", "nowhere.md", path=demo_path)
        except Exception as e:
            print(f"  REJECTED at the gate: {e}")
        print()
        print("Closing ALPHA-001 properly:")
        close_experiment(a1, "INCONCLUSIVE", "labs/alpha_engine/results/demo1/FINDINGS.md",
                         path=demo_path)
        print(" ", get(a1, path=demo_path))
        print("\nReal ledger untouched:",
              REGISTRY_PATH, "exists=" + str(REGISTRY_PATH.exists()))
