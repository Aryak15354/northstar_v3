# Legacy Test Quarantine

This directory contains tests that describe old contracts and should not run in
the default production gate.

Rules:

- Do not add new tests here.
- Move a test here only when it is demonstrably stale and blocks the current
  contract suite from representing reality.
- Before restoring a test to the active suite, update it against the current
  public API and verify it passes locally.

Current quarantine:

- `intelligence_observer/`: old ObserverSnapshot, output artifact, question
  engine, and integration tests that assert constructor names and methods no
  longer exposed by the current implementation. The active Observer contract is
  currently represented by `tests/intelligence_observer/test_authority_firewall.py`.
