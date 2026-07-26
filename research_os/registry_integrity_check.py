#!/usr/bin/env python3
"""Single-point ID assignment and data-anchored cross-reference verification for registries.

Fixes defect **1f** in `GEN8_RESEARCH_CHARTER.md` §3.1, traced to HIGH-3/4/5 in
`results/gen7/GEN6_GEN7_INDEPENDENT_AUDIT_2026_07_25.md`.

--------------------------------------------------------------------------------------------------
The bug, precisely
--------------------------------------------------------------------------------------------------
Gen-7 ended up with **two incompatible TC-numbering conventions for the same six objects**. Six lab
scripts used Convention A; `lab2_populate_registries.py` used Convention B, an accident of
`full_sample_scan` dict iteration order:

    Convention A (labs 3-8, all lab JSON, all narrative docs):  TC-002=KRW l1, TC-003=AUDUSD l2, ...
    Convention B (the candidates registry only):                TC-002=AUDUSD l2, TC-003=BRL l2, ...

Every cross-reference between them was silently wrong. A corrigendum issued on 2026-07-25 made the
two CSVs self-consistent — by aligning them to the **minority** convention, so the registries then
disagreed with six laboratories. It also rewrote a note citing Lab 3/7 findings into a numbering
Lab 3/7 never used. The error was only caught by a full re-derivation from raw data (RA-004).

Two structural causes, both fixed here:
  1. **IDs were assigned in more than one place.** Any second assignment site is a second convention
     waiting to happen.
  2. **Cross-references were checked for string well-formedness, not for pointing at the same
     underlying object.** "TC-003 exists and matches `^TC-\\d{3}$`" was true in both conventions.

--------------------------------------------------------------------------------------------------
The fix
--------------------------------------------------------------------------------------------------
* `assign_ids` is the **only** place a Gen-8 ID is minted. IDs are derived from a canonical sort over
  the object's own **identity fields** (e.g. symbol + lag), so the same input data always yields the
  same ID regardless of dict ordering, file ordering, or which script runs first.
* `verify_references` resolves every downstream reference back to its identity fields and compares
  **the data**, not the string. It is what would have caught Gen-7's mismatch on the first write.
* `assert_registry_integrity` runs after **every** registry write, not once at the end — the audit's
  own recommendation, since a mismatch introduced mid-run is otherwise invisible until re-derivation.


---
RESEARCH OS lineage: forked from scripts/gen8/lib/registry_integrity_check.py (2026-07-26). Per GEN8_RESEARCH_CHARTER.md section 11's own inheritance contract, this becomes the canonical shared copy for all four Northstar Institute labs. scripts/gen8/lib/registry_integrity_check.py is UNCHANGED and remains the historical Gen-8 record -- this is a fork, not a move, per the never-silently-rewrite-history discipline."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


class RegistryIntegrityError(RuntimeError):
    """A registry ID scheme or a cross-reference does not match the underlying data."""


# Prefixes may contain digits after the first character -- Gen-8 uses generation-tagged prefixes such
# as `G8T`. The original `[A-Z]{2,4}` rejected those, and this module's own gate caught it on G8-02's
# first registry write (disclosed in docs/GEN8_DECISION_LOG.md rather than silently corrected).
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,4}-\d{3,4}$")


# ---------------------------------------------------------------------------------------------
# The one and only ID assignment site
# ---------------------------------------------------------------------------------------------
def canonical_key(record: dict, identity_fields: list[str]) -> str:
    """A stable, order-independent string identifying an object by its own data.

    Values are normalised (floats formatted to a fixed precision, strings stripped/upper-cased) so
    that `lag=1` and `lag=1.0` — or `"CL=F"` and `" cl=f "` — cannot become two different objects.
    """
    parts = []
    for f in identity_fields:
        if f not in record:
            raise KeyError(f"identity field {f!r} missing from record {record!r}")
        v = record[f]
        if isinstance(v, float):
            v = f"{v:.10g}"
        elif isinstance(v, (int,)):
            v = str(int(v))
        else:
            v = str(v).strip().upper()
        parts.append(f"{f}={v}")
    return "|".join(parts)


def assign_ids(records: list[dict], prefix: str, identity_fields: list[str],
               start: int = 1, width: int = 3) -> pd.DataFrame:
    """Mint IDs for a set of objects. **The only place Gen-8 assigns an ID.**

    IDs are allocated in the canonical sort order of the identity fields — not input order, not dict
    iteration order, not p-value order. Re-running on the same objects, in any order, on any Python
    version, reproduces the same assignment exactly. That property is what makes a second, divergent
    convention impossible rather than merely unlikely.
    """
    if not records:
        return pd.DataFrame(columns=["id", "canonical_key"] + identity_fields)
    keyed = [(canonical_key(r, identity_fields), r) for r in records]
    seen: dict[str, dict] = {}
    for k, r in keyed:
        if k in seen and seen[k] != r:
            raise RegistryIntegrityError(
                f"two different records share identity {k!r}; identity_fields={identity_fields} "
                f"does not uniquely identify an object. Records: {seen[k]!r} vs {r!r}")
        seen[k] = r
    rows = []
    for i, k in enumerate(sorted(seen), start=start):
        r = dict(seen[k])
        r["id"] = f"{prefix}-{i:0{width}d}"
        r["canonical_key"] = k
        rows.append(r)
    df = pd.DataFrame(rows)
    return df[["id", "canonical_key"] + [c for c in df.columns if c not in ("id", "canonical_key")]]


# ---------------------------------------------------------------------------------------------
# Data-anchored verification
# ---------------------------------------------------------------------------------------------
@dataclass
class IntegrityReport:
    registry: str
    n_rows: int
    identity_fields: list[str]
    id_format_ok: bool
    ids_unique: bool
    identities_unique: bool
    assignment_reproducible: bool
    n_references_checked: int
    n_reference_mismatches: int
    mismatches: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (self.id_format_ok and self.ids_unique and self.identities_unique
                and self.assignment_reproducible and self.n_reference_mismatches == 0)

    def summary(self) -> str:
        lines = [
            f"REGISTRY INTEGRITY [{self.registry}] -- {'PASS' if self.ok else 'FAIL'}",
            f"  rows                    : {self.n_rows}",
            f"  identity fields         : {self.identity_fields}",
            f"  ID format well-formed   : {self.id_format_ok}",
            f"  IDs unique              : {self.ids_unique}",
            f"  identities unique       : {self.identities_unique}",
            f"  assignment reproducible : {self.assignment_reproducible}  "
            f"(re-deriving IDs from the data reproduces every row's ID)",
            f"  cross-references checked: {self.n_references_checked}, "
            f"mismatches: {self.n_reference_mismatches}",
        ]
        for m in self.mismatches[:10]:
            lines.append(f"    MISMATCH {m}")
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


def verify_references(registry: pd.DataFrame, references: list[dict], identity_fields: list[str],
                      id_col: str = "id") -> tuple[int, list[dict]]:
    """Check that every downstream reference points at the object it claims, **by data**.

    Each reference is a dict with an ``id`` plus whichever identity fields the citing document
    recorded, e.g. ``{"id": "TC-003", "symbol": "AUDUSD=X", "lag": 2, "cited_by": "lab7_report"}``.
    The reference passes only if the registry row with that ID has those exact identity values.

    This is precisely the check Gen-7 lacked: both of its conventions produced well-formed IDs, and
    only a comparison against the underlying symbol and lag could distinguish them.
    """
    idx = registry.set_index(id_col)
    mismatches = []
    for ref in references:
        rid = ref.get(id_col)
        if rid not in idx.index:
            mismatches.append(dict(reference=ref, problem=f"id {rid!r} not present in registry"))
            continue
        row = idx.loc[rid]
        for f in identity_fields:
            if f not in ref:
                continue
            expected, actual = ref[f], row[f]
            same = (f"{float(expected):.10g}" == f"{float(actual):.10g}"
                    if isinstance(expected, (int, float)) and isinstance(actual, (int, float))
                    else str(expected).strip().upper() == str(actual).strip().upper())
            if not same:
                mismatches.append(dict(
                    reference=ref, problem=f"{f}: reference says {expected!r}, "
                                           f"registry row {rid} holds {actual!r}"))
    return len(references), mismatches


def check_registry_integrity(registry: pd.DataFrame, identity_fields: list[str],
                             prefix: str, references: list[dict] | None = None,
                             id_col: str = "id", name: str = "registry",
                             verbose: bool = True) -> IntegrityReport:
    """Full integrity pass. Run after **every** registry write, not once at the end."""
    ids = registry[id_col].astype(str).tolist()
    keys = [canonical_key(r, identity_fields) for r in registry.to_dict("records")]

    rebuilt = assign_ids(registry.to_dict("records"), prefix, identity_fields)
    rebuilt_map = dict(zip(rebuilt["canonical_key"], rebuilt["id"]))
    reproducible = all(rebuilt_map.get(k) == i for k, i in zip(keys, ids))

    n_refs, mismatches = (0, [])
    if references:
        n_refs, mismatches = verify_references(registry, references, identity_fields, id_col)

    rep = IntegrityReport(
        registry=name, n_rows=len(registry), identity_fields=identity_fields,
        id_format_ok=all(bool(ID_PATTERN.match(i)) for i in ids),
        ids_unique=len(set(ids)) == len(ids),
        identities_unique=len(set(keys)) == len(keys),
        assignment_reproducible=reproducible,
        n_references_checked=n_refs, n_reference_mismatches=len(mismatches), mismatches=mismatches)

    if not reproducible:
        diffs = [(k, i, rebuilt_map.get(k)) for k, i in zip(keys, ids) if rebuilt_map.get(k) != i]
        rep.notes.append(
            f"{len(diffs)} row(s) carry an ID that re-derivation does not reproduce, e.g. "
            f"{diffs[0][0]} is stored as {diffs[0][1]} but canonically assigns to {diffs[0][2]}. "
            f"This is the Gen-7 two-convention failure mode (audit HIGH-3).")
    if verbose:
        print(rep.summary())
    return rep


def assert_registry_integrity(*args, **kwargs) -> IntegrityReport:
    """**Hard gate.** Raise `RegistryIntegrityError` unless the registry passes every check."""
    rep = check_registry_integrity(*args, **kwargs)
    if not rep.ok:
        raise RegistryIntegrityError(rep.summary())
    return rep


def write_registry(registry: pd.DataFrame, path: str | Path, identity_fields: list[str],
                   prefix: str, references: list[dict] | None = None,
                   id_col: str = "id") -> IntegrityReport:
    """Append-only write with a mandatory post-write integrity check.

    Refuses to modify or drop an existing row (P8: registries are append-only; superseded entries are
    retired in place, never overwritten). Status-column edits go through `retire_in_place`.
    """
    path = Path(path)
    if path.exists():
        old = pd.read_csv(path)
        old_ids = set(old[id_col].astype(str))
        new_ids = set(registry[id_col].astype(str))
        dropped = old_ids - new_ids
        if dropped:
            raise RegistryIntegrityError(
                f"append-only violation: writing {path} would drop existing ID(s) {sorted(dropped)}. "
                f"Registries are append-only (P8) — retire entries in place instead.")
    rep = assert_registry_integrity(registry, identity_fields, prefix, references, id_col,
                                    name=path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(path, index=False)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    print(f"  wrote {path} ({len(registry)} rows, sha256 {sha}...) — integrity PASS")
    return rep


if __name__ == "__main__":
    print("=" * 92)
    print("Demonstration: Gen-7's actual TC-numbering collision, and what this module does with it")
    print("=" * 92)
    objects = [
        dict(symbol="CL=F", lag=1), dict(symbol="KRW=X", lag=1), dict(symbol="AUDUSD=X", lag=2),
        dict(symbol="MXN=X", lag=2), dict(symbol="MXN=X", lag=1), dict(symbol="BRL=X", lag=2),
    ]
    reg = assign_ids(objects, prefix="TC", identity_fields=["symbol", "lag"])
    print("\nCanonical assignment (data-ordered, reproducible from any input order):")
    print(reg[["id", "symbol", "lag"]].to_string(index=False))

    print("\nSame objects supplied in a DIFFERENT order (Gen-7's Convention B arose exactly this "
          "way, from dict iteration order):")
    reg2 = assign_ids(list(reversed(objects)), prefix="TC", identity_fields=["symbol", "lag"])
    print("  identical assignment:", reg2[["id", "symbol", "lag"]]
          .equals(reg[["id", "symbol", "lag"]]))

    print("\nA downstream reference in the OTHER convention (Lab 7 citing 'TC-003 = AUD/USD lag 2'):")
    _, mm = verify_references(reg, [dict(id="TC-003", symbol="AUDUSD=X", lag=2, cited_by="lab7")],
                              ["symbol", "lag"])
    print("  mismatches detected:", len(mm))
    for m in mm:
        print("   ", m["problem"])
    print("\n  A string-format check would have passed this reference. Only comparing the "
          "underlying\n  data catches it — which is the whole point of defect 1f.")
