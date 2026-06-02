#!/usr/bin/env python3
"""
northstar_kaggle_automation.py
==============================
Codex-ready automation for the Northstar V3 Kaggle experiment loop.

WHAT THIS DOES (you do nothing except run it):
  1. Deploys the self-contained section scripts to a local bundle directory
  2. Runs experiments locally in smoke/profile mode OR submits to Kaggle via API
  3. Pulls results back from Kaggle output files
  4. Parses every summary JSON and prints a clean compendium-style results table
  5. Auto-updates a local ledger CSV so you always have a single source of truth

USAGE (give this whole file to Codex with the instruction):
  "Run the next blocking experiment in the Northstar compendium ratios campaign"
  "Run EXP-09 through EXP-12 on Kaggle and pull results"
  "Show me the current results table"
  "Run EXP-09 locally in smoke mode"

REQUIREMENTS:
  pip install kaggle pandas rich
  kaggle.json must be in ~/.kaggle/kaggle.json  (from kaggle.com > Account > API)
  Your feature export dataset must be uploaded to Kaggle as:
    northstar-v3-feature-export  (slug used in the section scripts)

CONFIGURATION — edit these 4 lines only:
"""

from __future__ import annotations

import os
from pathlib import Path

# ── User config ────────────────────────────────────────────────────────────────
PROJECT_ROOT          = Path(os.environ.get("NORTHSTAR_PROJECT_ROOT", Path(__file__).resolve().parent)).resolve()
KAGGLE_USERNAME       = "aryakghoshal"                  # your Kaggle username
KAGGLE_DATASET_SLUG   = "northstar-v3-feature-export"   # the feature export dataset slug
LOCAL_BUNDLE_DIR      = PROJECT_ROOT / "tmp/northstar_kaggle_bundle"
LOCAL_EXPORT_DIR      = PROJECT_ROOT / "tmp/kaggle_uploads/northstar_v3_feature_export"
LOCAL_RESULTS_DIR     = PROJECT_ROOT / "tmp/kaggle_results"
LEDGER_CSV            = PROJECT_ROOT / "tmp/northstar_compendium_ledger.csv"
ALLOW_LOCAL_TRAINING  = False
# ──────────────────────────────────────────────────────────────────────────────

import argparse
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import time
import tempfile
import zipfile
from datetime import datetime
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────────────
BUNDLE_DIR   = Path(LOCAL_BUNDLE_DIR).expanduser().resolve()
EXPORT_DIR   = Path(LOCAL_EXPORT_DIR).expanduser().resolve()
RESULTS_DIR  = Path(LOCAL_RESULTS_DIR).expanduser().resolve()
LEDGER_PATH  = Path(LEDGER_CSV).expanduser().resolve()
SCRIPT_DIR   = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(SCRIPT_DIR / "tmp" / ".mplconfig"))
(SCRIPT_DIR / "tmp" / ".mplconfig").mkdir(parents=True, exist_ok=True)
KAGGLE_CLI = shutil.which("kaggle") or "/Library/Frameworks/Python.framework/Versions/3.13/bin/kaggle"

# ── Experiment metadata (from the compendium) ──────────────────────────────────
EXPERIMENTS = {
    "EXP-09": {
        "section_script": "run_section_ratio_09_12.py",
        "title": "CatBoost Depth Ablation + Early Stopping",
        "hypothesis": "Lower tree depth + early stopping reduces train/test ratio below 2.5x without IC collapse.",
        "pass_criteria": "ratio < 2.5 AND IC >= 0.020",
        "priority": 1,
        "group": "ratio_campaign",
    },
    "EXP-10": {
        "section_script": "run_section_ratio_09_12.py",
        "title": "L2 Regularisation Sweep",
        "hypothesis": "l2_leaf_reg sweep on best EXP-09 config further reduces ratio.",
        "pass_criteria": "ratio <= 2.5 AND IC >= 0.038",
        "priority": 2,
        "group": "ratio_campaign",
    },
    "EXP-11": {
        "section_script": "run_section_ratio_09_12.py",
        "title": "Ordered vs Plain Boosting",
        "hypothesis": "Plain boosting reduces ratio without IC penalty.",
        "pass_criteria": "Plain ratio <= Ordered ratio AND IC >= Ordered IC - 0.005",
        "priority": 2,
        "group": "ratio_campaign",
    },
    "EXP-12": {
        "section_script": "run_section_ratio_09_12.py",
        "title": "Training Window Extension (20→30 folds)",
        "hypothesis": "More walk-forward windows lowers variance and ratio.",
        "pass_criteria": "ratio drops, IC stable",
        "priority": 2,
        "group": "ratio_campaign",
    },
    "EXP-13": {
        "section_script": "run_section_sector_13_16.py",
        "title": "Financial Services Sector Model",
        "hypothesis": "Sector IC > full-universe IC on BFSI 95-stock sub-universe.",
        "pass_criteria": "sector IC > full-universe IC",
        "priority": 3,
        "group": "sector_models",
    },
    "EXP-14": {
        "section_script": "run_section_sector_13_16.py",
        "title": "IT Sector Model",
        "hypothesis": "USD/INR dollar-revenue sensitivity creates sector-specific alpha in IT.",
        "pass_criteria": "sector IC > full-universe IC on IT stocks",
        "priority": 3,
        "group": "sector_models",
    },
    "EXP-15": {
        "section_script": "run_section_sector_13_16.py",
        "title": "Capital Goods Sector Model",
        "hypothesis": "Capex-cycle features create sector alpha in 64-stock universe.",
        "pass_criteria": "sector IC > full-universe IC on CapGoods",
        "priority": 3,
        "group": "sector_models",
    },
    "EXP-16": {
        "section_script": "run_section_sector_13_16.py",
        "title": "Sector Model Blend",
        "hypothesis": "Ensemble of sector models beats monolithic full-universe model.",
        "pass_criteria": "blend IC > best single sector IC",
        "priority": 3,
        "group": "sector_models",
    },
    "EXP-17": {
        "section_script": "run_section_regime_17_19.py",
        "title": "Factor IC × Regime Event Heatmap",
        "hypothesis": "Some anchor factors are regime-conditional; identify which.",
        "pass_criteria": "factor x regime IC matrix produced",
        "priority": 4,
        "group": "regime_research",
    },
    "EXP-24": {
        "section_script": "run_section_signal_24_25.py",
        "title": "Forex × Commodity IC Battery",
        "hypothesis": ">=3 of 16 macro signals have IC > 0.015 with stable sign.",
        "pass_criteria": ">=3 signals IC > 0.015 stable",
        "priority": 4,
        "group": "signal_expansion",
    },
    "EXP-26": {
        "section_script": "run_section_verification_26_27.py",
        "title": "Anchor Factor 5-Test Verification",
        "hypothesis": "All 6 anchor factors pass the full 5-test battery.",
        "pass_criteria": "all 5 tests pass for all 6 factors",
        "priority": 4,
        "group": "signal_verification",
    },
}

SECTION_SCRIPTS = {
    "run_section_ratio_09_12.py",
    "run_section_sector_13_16.py",
    "run_section_regime_17_19.py",
    "run_section_redemption_20_23.py",
    "run_section_signal_24_25.py",
    "run_section_verification_26_27.py",
    "run_section_legacy_01_08.py",
}

VERDICT_GATE = {
    "ic_threshold":    0.020,
    "ic_ir_threshold": 1.5,
    "ratio_threshold": 2.5,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pip_import(module: str, pip_spec: str | None = None) -> Any:
    """Import a module, installing it silently if missing."""
    try:
        return __import__(module)
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", pip_spec or module],
            check=False,
            capture_output=True,
        )
        return __import__(module)


def _find_section_script(name: str) -> Path | None:
    """Look for a section script in known locations."""
    candidates = [
        SCRIPT_DIR / name,
        BUNDLE_DIR / name,
        Path.cwd() / name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _runner_path_for_exp(exp_id: str) -> str:
    exp_num = int(str(exp_id).split("-", 1)[1])
    return f"scripts/kaggle/plan_2026_04_08/run_exp{exp_num:02d}.py"


def _rewrite_selfcontained_for_single_exp(script_path: Path, exp_id: str, profile: str) -> str:
    """Return a Kaggle-safe script that runs only the requested EXP runner."""
    content = script_path.read_text(encoding="utf-8")
    target_line = "TARGET_SCRIPT = 'run_section_ratio_09_12.py'"
    replacement = f"TARGET_SCRIPT = '{_runner_path_for_exp(exp_id)}'"
    if target_line not in content:
        raise ValueError(f"Cannot rewrite TARGET_SCRIPT in {script_path}")
    content = content.replace(target_line, replacement)
    old = "    sys.argv[0] = str(script_path)\n    runpy.run_path(str(script_path), run_name='__main__')"
    new = (
        "    sys.argv = [str(script_path), '--profile', "
        f"{profile!r}, '--output-root', '/kaggle/working/northstar_results']\n"
        "    runpy.run_path(str(script_path), run_name='__main__')"
    )
    if old not in content:
        raise ValueError(f"Cannot inject argv in {script_path}")
    return content.replace(old, new)


def _extract_bundle_from_script(script_path: Path, dest_dir: Path) -> Path:
    """
    Extract the embedded zip bundle from a self-contained section script.
    Returns the extracted bundle root directory.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = script_path.read_text(encoding="utf-8")
    marker = 'ARCHIVE_B64 = """'
    start = content.find(marker)
    if start == -1:
        raise ValueError(f"No ARCHIVE_B64 found in {script_path}")
    start += len(marker)
    end = content.find('"""', start)
    b64_data = content[start:end].strip()

    # Verify hash if present
    sha_marker = "ARCHIVE_SHA256 = '"
    sha_start = content.find(sha_marker)
    if sha_start != -1:
        sha_end = content.find("'", sha_start + len(sha_marker))
        expected_sha = content[sha_start + len(sha_marker):sha_end]
        raw = base64.b64decode(b64_data)
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != expected_sha:
            print(f"  ⚠  SHA256 mismatch — script may have been modified")
    else:
        raw = base64.b64decode(b64_data)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        zf.extractall(dest_dir)

    # The bundle lands in a dated subdirectory — find it
    roots = [p for p in dest_dir.iterdir() if p.is_dir()]
    if len(roots) == 1:
        return roots[0]
    # Try to find the main bundle folder
    for r in roots:
        if "bundle" in r.name.lower() or "upload" in r.name.lower():
            return r
    return dest_dir


def _load_results_json(exp_id: str) -> dict | None:
    """Load a previously-saved results JSON for an experiment."""
    for search_dir in [RESULTS_DIR, BUNDLE_DIR]:
        for path in search_dir.rglob(f"*{exp_id.lower().replace('-', '_')}*summary*.json"):
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        for path in search_dir.rglob(f"*summary*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("exp_id") == exp_id:
                    return data
                nested = data.get("results", {}).get(exp_id, {}).get("payload")
                if isinstance(nested, dict):
                    nested.setdefault("exp_id", exp_id)
                    return nested
            except Exception:
                pass
    return None


def _validate_local_inputs() -> None:
    required = [
        EXPORT_DIR / "northstar_features.parquet",
        EXPORT_DIR / "northstar_metadata.parquet",
        EXPORT_DIR / "northstar_regime_labels.parquet",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing local feature export files: " + ", ".join(missing))


def _verdict(ic: float | None, ic_ir: float | None, ratio: float | None) -> str:
    if ic is None or ratio is None:
        return "PENDING"
    if ic >= VERDICT_GATE["ic_threshold"] and ratio < VERDICT_GATE["ratio_threshold"]:
        if ic_ir is not None and ic_ir >= VERDICT_GATE["ic_ir_threshold"]:
            return "VERDICT_A ✓"
        return "VERDICT_A (IC_IR TBC)"
    if ic >= VERDICT_GATE["ic_threshold"]:
        return "VERDICT_B (ratio gate open)"
    return "VERDICT_C ✗"


def _load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    try:
        import csv
        with LEDGER_PATH.open() as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _save_ledger(rows: list[dict]) -> None:
    if not rows:
        return
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    import csv
    fieldnames = list(rows[0].keys())
    with LEDGER_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _upsert_ledger(exp_id: str, result: dict) -> None:
    """Insert or update a result row in the ledger CSV."""
    rows = _load_ledger()
    best = result.get("best_candidate") or {}
    new_row = {
        "exp_id":       exp_id,
        "title":        EXPERIMENTS.get(exp_id, {}).get("title", ""),
        "run_date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mean_test_ic": best.get("mean_test_ic"),
        "ic_ir":        best.get("ic_ir"),
        "ratio":        best.get("mean_train_test_ratio"),
        "hit_rate":     best.get("mean_hit_rate"),
        "windows":      best.get("windows_completed"),
        "best_params":  json.dumps(best.get("params") or {}),
        "verdict":      _verdict(
            best.get("mean_test_ic"),
            best.get("ic_ir"),
            best.get("mean_train_test_ratio"),
        ),
        "pass_criteria": EXPERIMENTS.get(exp_id, {}).get("pass_criteria", ""),
    }
    # Replace existing row for same exp_id, or append
    updated = False
    for i, row in enumerate(rows):
        if row.get("exp_id") == exp_id:
            rows[i] = new_row
            updated = True
            break
    if not updated:
        rows.append(new_row)
    _save_ledger(rows)


# ── Core actions ───────────────────────────────────────────────────────────────

def deploy_bundle(section_script_name: str) -> Path:
    """
    Extract the bundle from a section script and return the bundle root.
    Skips extraction if bundle already exists (use --fresh to force).
    """
    script_path = _find_section_script(section_script_name)
    if script_path is None:
        raise FileNotFoundError(
            f"Cannot find '{section_script_name}'. "
            f"Place it in {SCRIPT_DIR} or {BUNDLE_DIR} or the current directory."
        )
    print(f"  Deploying bundle from: {script_path}")
    bundle_root = _extract_bundle_from_script(script_path, BUNDLE_DIR / "extracted")
    print(f"  Bundle root: {bundle_root}")
    return bundle_root


def run_experiment_locally(
    exp_id: str,
    *,
    profile: str = "smoke",
    max_splits: int | None = 3,
    output_root: Path | None = None,
    fresh: bool = False,
) -> dict:
    """
    Run an experiment using the extracted bundle scripts directly.
    profile='smoke' runs 1-3 splits quickly for validation.
    profile='full' runs all splits (use on Kaggle, not locally).
    """
    meta = EXPERIMENTS.get(exp_id)
    if meta is None:
        raise ValueError(f"Unknown experiment: {exp_id}")
    if not ALLOW_LOCAL_TRAINING:
        raise RuntimeError(
            "Local training is disabled for this Mac. Use --kaggle for real runs, "
            "or set ALLOW_LOCAL_TRAINING=True only for tiny diagnostics."
        )

    bundle_root = deploy_bundle(meta["section_script"])
    exp_runner = bundle_root / _runner_path_for_exp(exp_id)
    if not exp_runner.exists():
        candidates = [
            p for p in bundle_root.rglob(f"run_{exp_id.lower().replace('-', '')}.py")
            if "plan_2026_04_08" in str(p)
        ]
        if candidates:
            exp_runner = candidates[0]
        else:
            raise FileNotFoundError(f"Runner script not found for {exp_id} in {bundle_root}")

    out_root = output_root or (RESULTS_DIR / "local_runs")
    out_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(exp_runner),
        "--export-dir", str(EXPORT_DIR),
        "--profile", profile,
        "--output-root", str(out_root),
    ]
    if max_splits:
        cmd += ["--max-splits", str(max_splits)]
    if fresh:
        cmd += ["--fresh"]

    print(f"\n{'='*60}")
    print(f"  Running {exp_id} locally  [{profile} mode, max_splits={max_splits}]")
    print(f"  {meta['title']}")
    print(f"  Hypothesis: {meta['hypothesis']}")
    print(f"{'='*60}\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(bundle_root) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(cmd, env=env, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n  ✗  {exp_id} exited with code {result.returncode}")

    # Try to find and load results
    results = _load_results_json(exp_id)
    if results:
        _upsert_ledger(exp_id, results)
        print_single_result(exp_id, results)
    else:
        print(f"  ⚠  Could not find results JSON for {exp_id} — check {out_root}")

    return results or {}


def submit_to_kaggle(
    exp_id: str,
    *,
    profile: str = "full",
    notebook_slug: str | None = None,
    wait: bool = True,
) -> dict:
    """
    Submit the section script as a Kaggle notebook script run and wait for output.

    The section script is self-contained and can be uploaded as a Kaggle script notebook.
    Results are pulled back as output files once the run completes.
    """
    try:
        import kaggle  # noqa: F401 — just checking it's installed
    except ImportError:
        print("  Installing kaggle CLI...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "kaggle"], check=True)

    meta = EXPERIMENTS.get(exp_id)
    if meta is None:
        raise ValueError(f"Unknown experiment: {exp_id}")

    script_path = _find_section_script(meta["section_script"])
    if script_path is None:
        raise FileNotFoundError(f"Cannot find section script '{meta['section_script']}'")

    slug = notebook_slug or f"northstar-{exp_id.lower().replace('-', '')}"
    print(f"\n{'='*60}")
    print(f"  Submitting {exp_id} to Kaggle  [notebook: {slug}]")
    print(f"  {meta['title']}")
    print(f"{'='*60}\n")

    # Build Kaggle notebook metadata
    nb_meta = {
        "id":            f"{KAGGLE_USERNAME}/{slug}",
        "title":         slug,
        "code_file":     meta["section_script"],
        "language":      "python",
        "kernel_type":   "script",
        "is_private":    True,
        "enable_gpu":    False,
        "enable_internet": False,
        "dataset_sources": [
            f"{KAGGLE_USERNAME}/{KAGGLE_DATASET_SLUG}"
        ],
        "competition_sources": [],
        "kernel_sources":      [],
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Generate a single-experiment self-contained script so EXP-09 does not
        # accidentally spend a full Kaggle run executing the whole EXP-09..12 section.
        code_file = f"run_{exp_id.lower().replace('-', '')}_single.py"
        (tmp_dir / code_file).write_text(
            _rewrite_selfcontained_for_single_exp(script_path, exp_id, profile),
            encoding="utf-8",
        )
        nb_meta["code_file"] = code_file
        # Write kernel metadata
        (tmp_dir / "kernel-metadata.json").write_text(json.dumps(nb_meta, indent=2))

        print(f"  Pushing notebook to Kaggle...")
        push_result = subprocess.run(
            [KAGGLE_CLI, "kernels", "push", "-p", str(tmp_dir)],
            capture_output=True, text=True,
        )
        if push_result.returncode != 0:
            print(f"  ✗  Push failed:\n{push_result.stdout}\n{push_result.stderr}")
            return {}
        print(f"  ✓  Pushed. Kaggle will now run it (30–90 min).")

    if not wait:
        print(f"\n  Run 'python {__file__} pull {exp_id} --slug {slug}' when done.")
        return {}

    wait_for_kaggle_kernel(f"{KAGGLE_USERNAME}/{slug}")
    return pull_kaggle_results(exp_id, notebook_slug=slug)


def wait_for_kaggle_kernel(kernel_ref: str, *, poll_seconds: int = 60, max_minutes: int = 120) -> str:
    """Poll Kaggle status without doing any local training."""
    deadline = time.time() + max_minutes * 60
    last_status = ""
    while time.time() < deadline:
        status_result = subprocess.run(
            [KAGGLE_CLI, "kernels", "status", kernel_ref],
            capture_output=True, text=True,
        )
        status_text = (status_result.stdout + "\n" + status_result.stderr).strip()
        if status_text and status_text != last_status:
            print(status_text)
            last_status = status_text
        lowered = status_text.lower()
        if any(token in lowered for token in ["complete", "completed"]):
            return status_text
        if any(token in lowered for token in ["error", "failed", "canceled", "cancelled"]):
            raise RuntimeError(f"Kaggle run did not complete cleanly: {status_text}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for Kaggle kernel {kernel_ref}")


def pull_kaggle_results(
    exp_id: str,
    *,
    notebook_slug: str | None = None,
) -> dict:
    """
    Pull output files from a completed Kaggle notebook run and parse results.
    """
    meta = EXPERIMENTS.get(exp_id)
    if meta is None:
        raise ValueError(f"Unknown experiment: {exp_id}")

    slug = notebook_slug or f"northstar-{exp_id.lower().replace('-', '')}"
    output_dir = RESULTS_DIR / exp_id.lower().replace("-", "_")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Pulling results for {exp_id} from {KAGGLE_USERNAME}/{slug}...")

    pull_result = subprocess.run(
        [KAGGLE_CLI, "kernels", "output", f"{KAGGLE_USERNAME}/{slug}", "-p", str(output_dir)],
        capture_output=True, text=True,
    )
    if pull_result.returncode != 0:
        print(f"  ✗  Pull failed:\n{pull_result.stderr}")
        print("  (The notebook may still be running — try again in a few minutes)")
        return {}

    print(f"  ✓  Output saved to {output_dir}")

    # Find and parse the summary JSON
    results = None
    for json_path in sorted(output_dir.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text())
            if data.get("exp_id") == exp_id or "best_candidate" in data:
                results = data
                results.setdefault("exp_id", exp_id)
                print(f"  ✓  Parsed results from {json_path.name}")
                break
        except Exception:
            pass

    if results:
        _upsert_ledger(exp_id, results)
        print_single_result(exp_id, results)
    else:
        print(f"  ⚠  No results JSON found in {output_dir}")
        # List what we got
        files = list(output_dir.iterdir())
        if files:
            print("  Files downloaded:")
            for f in files:
                print(f"    {f.name}")

    return results or {}


def print_single_result(exp_id: str, result: dict) -> None:
    """Print a clean one-experiment result block."""
    meta = EXPERIMENTS.get(exp_id, {})
    best = result.get("best_candidate") or {}
    ic       = best.get("mean_test_ic")
    ic_ir    = best.get("ic_ir")
    ratio    = best.get("mean_train_test_ratio")
    hit_rate = best.get("mean_hit_rate")
    params   = best.get("params") or {}

    verdict = _verdict(ic, ic_ir, ratio)
    passed  = "✓" in verdict

    print(f"\n{'─'*60}")
    print(f"  {exp_id}  {meta.get('title', '')}")
    print(f"{'─'*60}")
    print(f"  IC           : {ic:.4f}"    if ic    is not None else "  IC           : —")
    print(f"  IC IR        : {ic_ir:.2f}" if ic_ir is not None else "  IC IR        : —")
    print(f"  Train/test   : {ratio:.2f}x" if ratio is not None else "  Train/test   : —")
    print(f"  Hit rate     : {hit_rate:.3f}" if hit_rate is not None else "  Hit rate     : —")
    print(f"  Best params  : {json.dumps(params)}")
    print(f"  Gate         : {meta.get('pass_criteria', '')}")
    print(f"  Verdict      : {verdict}")

    if passed:
        print(f"\n  🎉  Gate CLEARED. Proceed to next experiment.")
    elif ratio is not None and ratio < 5.0:
        print(f"\n  ⚡  Ratio improving. Consider running EXP-10 / EXP-11 next.")
    print()


def print_full_ledger() -> None:
    """Print the full compendium ledger as a table."""
    rows = _load_ledger()
    if not rows:
        print("\n  No results yet. Run an experiment first.\n")
        return

    # Try rich for a pretty table
    try:
        rich = _pip_import("rich")
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(title="Northstar Compendium Ledger", show_lines=True)
        table.add_column("Exp",       style="bold")
        table.add_column("IC",        justify="right")
        table.add_column("IC IR",     justify="right")
        table.add_column("Ratio",     justify="right")
        table.add_column("Verdict",   style="bold")
        table.add_column("Gate",      style="dim")

        for row in rows:
            ic    = row.get("mean_test_ic") or "—"
            ic_ir = row.get("ic_ir")        or "—"
            ratio = row.get("ratio")        or "—"
            verdict = row.get("verdict", "PENDING")
            color = "green" if "✓" in verdict else ("yellow" if "PENDING" in verdict else "red")

            try:
                ratio_f = float(ratio)
                ratio_str = f"[red]{ratio_f:.2f}x[/red]" if ratio_f >= 2.5 else f"[green]{ratio_f:.2f}x[/green]"
            except Exception:
                ratio_str = str(ratio)

            try:
                ic_f = float(ic)
                ic_str = f"[green]{ic_f:.4f}[/green]" if ic_f >= 0.020 else f"[red]{ic_f:.4f}[/red]"
            except Exception:
                ic_str = str(ic)

            table.add_row(
                row.get("exp_id", ""),
                ic_str,
                str(ic_ir),
                ratio_str,
                f"[{color}]{verdict}[/{color}]",
                row.get("pass_criteria", "")[:40],
            )
        console.print(table)

    except Exception:
        # Fallback plain table
        header = f"{'Exp':<8} {'IC':>7} {'IC_IR':>6} {'Ratio':>7} {'Verdict':<25} Gate"
        print("\n" + header)
        print("─" * 80)
        for row in rows:
            print(
                f"{row.get('exp_id',''):<8} "
                f"{str(row.get('mean_test_ic','—')):>7} "
                f"{str(row.get('ic_ir','—')):>6} "
                f"{str(row.get('ratio','—')):>7} "
                f"{str(row.get('verdict','PENDING')):<25} "
                f"{str(row.get('pass_criteria',''))[:30]}"
            )
        print()

    print(f"  Ledger saved at: {LEDGER_PATH}")


def describe_experiment(exp_id: str) -> dict[str, Any]:
    meta = EXPERIMENTS.get(exp_id)
    if meta is None:
        raise ValueError(f"Unknown experiment: {exp_id}")
    bundle_root = deploy_bundle(meta["section_script"])
    runner = bundle_root / _runner_path_for_exp(exp_id)
    if not runner.exists():
        raise FileNotFoundError(f"Runner script not found: {runner}")
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"northstar_{exp_id.lower().replace('-', '_')}", runner)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {runner}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = dict(getattr(module, "SCRIPT_CONFIG", {}))
    print(json.dumps(config, indent=2, default=str))
    return config


def preflight(exp_id: str) -> None:
    _validate_local_inputs()
    meta = EXPERIMENTS.get(exp_id)
    if meta is None:
        raise ValueError(f"Unknown experiment: {exp_id}")
    script_path = _find_section_script(meta["section_script"])
    if script_path is None:
        raise FileNotFoundError(f"Cannot find section script '{meta['section_script']}'")
    config = describe_experiment(exp_id)
    if exp_id == "EXP-09":
        grid = config.get("candidate_grid") or []
        depths = sorted({item.get("params", {}).get("depth") for item in grid})
        waits = sorted({item.get("params", {}).get("od_wait") for item in grid})
        if depths != [3, 4, 5] or waits != [20, 30, 50]:
            raise ValueError(f"EXP-09 grid mismatch: depths={depths}, od_wait={waits}")
    print(f"\nPreflight OK for {exp_id}")
    print(f"  Section script : {script_path}")
    print(f"  Export dir     : {EXPORT_DIR}")
    print(f"  Results dir    : {RESULTS_DIR}")
    print(f"  Ledger         : {LEDGER_PATH}")


def next_experiment() -> str:
    """Return the exp_id of the next experiment to run (highest priority, no result yet)."""
    have_results = {row.get("exp_id") for row in _load_ledger() if "VERDICT_A" in str(row.get("verdict", ""))}
    # Order by priority
    candidates = sorted(
        [(meta["priority"], exp_id) for exp_id, meta in EXPERIMENTS.items()
         if exp_id not in have_results],
    )
    if not candidates:
        return ""
    _, exp_id = candidates[0]
    return exp_id


def run_next(*, profile: str = "smoke", max_splits: int = 3) -> dict:
    """Run the next blocking experiment. This is the zero-thought entry point."""
    exp_id = next_experiment()
    if not exp_id:
        print("\n  ✓  All tracked experiments have VERDICT_A results. Nothing left to run.")
        print_full_ledger()
        return {}
    print(f"\n  Next experiment: {exp_id} — {EXPERIMENTS[exp_id]['title']}")
    return run_experiment_locally(exp_id, profile=profile, max_splits=max_splits)


def run_campaign(
    group: str,
    *,
    profile: str = "smoke",
    max_splits: int = 3,
    stop_on_pass: bool = True,
) -> list[dict]:
    """
    Run all experiments in a group sequentially.
    If stop_on_pass=True (default), stops after the first VERDICT_A — no wasted compute.
    """
    group_exps = [
        (meta["priority"], exp_id)
        for exp_id, meta in EXPERIMENTS.items()
        if meta.get("group") == group
    ]
    group_exps.sort()
    results = []
    for _, exp_id in group_exps:
        result = run_experiment_locally(exp_id, profile=profile, max_splits=max_splits)
        results.append(result)
        if stop_on_pass:
            best = result.get("best_candidate") or {}
            verdict = _verdict(
                best.get("mean_test_ic"),
                best.get("ic_ir"),
                best.get("mean_train_test_ratio"),
            )
            if "VERDICT_A" in verdict:
                print(f"\n  🎉  {exp_id} cleared the gate — stopping campaign.")
                break
    print_full_ledger()
    return results


# ── Kaggle dataset push helper ─────────────────────────────────────────────────

def push_feature_dataset(local_export_dir: str | Path) -> None:
    """
    Push your local feature export to Kaggle as a new dataset version.
    Run this whenever you regenerate features locally.

    local_export_dir: path to your northstar_v3_feature_export_augmented_* directory
    """
    export_dir = Path(local_export_dir).expanduser().resolve()
    if not export_dir.exists():
        raise FileNotFoundError(f"Feature export dir not found: {export_dir}")

    meta_path = export_dir / "dataset-metadata.json"
    if not meta_path.exists():
        # Create minimal metadata
        meta = {
            "id":       f"{KAGGLE_USERNAME}/{KAGGLE_DATASET_SLUG}",
            "licenses": [{"name": "other"}],
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"  Created dataset-metadata.json in {export_dir}")

    print(f"  Pushing feature dataset to Kaggle...")
    result = subprocess.run(
        [KAGGLE_CLI, "datasets", "version", "-p", str(export_dir),
         "-m", f"Northstar feature export {datetime.now().strftime('%Y-%m-%d')}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  ✓  Dataset pushed: {KAGGLE_USERNAME}/{KAGGLE_DATASET_SLUG}")
    else:
        print(f"  ✗  Push failed:\n{result.stderr}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Northstar Kaggle automation — zero manual steps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python northstar_kaggle_automation.py next
      Run the next blocking experiment locally (smoke mode, 3 splits)

  python northstar_kaggle_automation.py run EXP-09
      Run EXP-09 locally in smoke mode

  python northstar_kaggle_automation.py run EXP-09 --profile full
      Run EXP-09 locally in full mode (all splits — slow on laptop)

  python northstar_kaggle_automation.py run EXP-09 --kaggle
      Submit EXP-09 to Kaggle and wait for results

  python northstar_kaggle_automation.py campaign ratio_campaign
      Run EXP-09→12 in sequence, stop when ratio gate clears

  python northstar_kaggle_automation.py pull EXP-09
      Pull already-completed EXP-09 results from Kaggle

  python northstar_kaggle_automation.py ledger
      Print the full compendium results table

  python northstar_kaggle_automation.py push-data ~/northstar/feature_export
      Push local feature export to Kaggle as a new dataset version
""",
    )
    sub = p.add_subparsers(dest="command")

    # next
    s = sub.add_parser("next", help="Run the next blocking experiment")
    s.add_argument("--profile", choices=["smoke", "full"], default="smoke")
    s.add_argument("--max-splits", type=int, default=3)

    # run
    s = sub.add_parser("run", help="Run a specific experiment")
    s.add_argument("exp_id", help="e.g. EXP-09")
    s.add_argument("--profile", choices=["smoke", "full"], default="smoke")
    s.add_argument("--max-splits", type=int, default=3)
    s.add_argument("--kaggle", action="store_true", help="Submit to Kaggle instead of running locally")
    s.add_argument("--no-wait", action="store_true", help="Don't wait for Kaggle results (use 'pull' later)")
    s.add_argument("--fresh", action="store_true", help="Force re-extract bundle and re-run")
    s.add_argument("--slug", help="Kaggle notebook slug (default: northstar-expNN)")
    s.add_argument("--describe", action="store_true", help="Print experiment config and exit")
    s.add_argument("--preflight", action="store_true", help="Validate local config/files and experiment grid")

    # campaign
    s = sub.add_parser("campaign", help="Run all experiments in a group")
    s.add_argument("group", choices=["ratio_campaign", "sector_models", "regime_research",
                                      "signal_expansion", "signal_verification"])
    s.add_argument("--profile", choices=["smoke", "full"], default="smoke")
    s.add_argument("--max-splits", type=int, default=3)
    s.add_argument("--no-stop-on-pass", action="store_true",
                   help="Run all experiments even after a gate is cleared")

    # pull
    s = sub.add_parser("pull", help="Pull Kaggle results for a previously-submitted experiment")
    s.add_argument("exp_id", help="e.g. EXP-09")
    s.add_argument("--slug", help="Kaggle notebook slug")

    # ledger
    sub.add_parser("ledger", help="Print the full results ledger")

    # preflight
    s = sub.add_parser("preflight", help="Validate config before spending Kaggle compute")
    s.add_argument("exp_id", help="e.g. EXP-09")

    # push-data
    s = sub.add_parser("push-data", help="Push feature export to Kaggle dataset")
    s.add_argument("export_dir", help="Path to local feature export directory")

    # list
    s = sub.add_parser("list", help="List all tracked experiments and their status")

    return p


def cmd_list() -> None:
    """Print all tracked experiments with their current status."""
    ledger = {row["exp_id"]: row for row in _load_ledger()}
    print(f"\n{'Exp':<8} {'Priority':<10} {'Group':<20} {'Status':<30} Title")
    print("─" * 100)
    for exp_id, meta in sorted(EXPERIMENTS.items(), key=lambda x: x[1]["priority"]):
        row = ledger.get(exp_id, {})
        status = row.get("verdict", "NOT RUN")
        print(f"{exp_id:<8} {meta['priority']:<10} {meta['group']:<20} {status:<30} {meta['title']}")
    print()


def main() -> int:
    parser = _build_cli()
    args = parser.parse_args()

    if args.command == "next":
        run_next(profile=args.profile, max_splits=args.max_splits)

    elif args.command == "run":
        exp_id = args.exp_id.upper()
        if args.describe:
            describe_experiment(exp_id)
        elif args.preflight:
            preflight(exp_id)
        elif args.kaggle:
            preflight(exp_id)
            submit_to_kaggle(exp_id, profile=args.profile, notebook_slug=args.slug, wait=not args.no_wait)
        else:
            run_experiment_locally(
                exp_id,
                profile=args.profile,
                max_splits=args.max_splits,
                fresh=args.fresh,
            )

    elif args.command == "campaign":
        run_campaign(
            args.group,
            profile=args.profile,
            max_splits=args.max_splits,
            stop_on_pass=not args.no_stop_on_pass,
        )

    elif args.command == "pull":
        pull_kaggle_results(args.exp_id.upper(), notebook_slug=args.slug)

    elif args.command == "ledger":
        print_full_ledger()

    elif args.command == "preflight":
        preflight(args.exp_id.upper())

    elif args.command == "push-data":
        push_feature_dataset(args.export_dir)

    elif args.command == "list":
        cmd_list()

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
