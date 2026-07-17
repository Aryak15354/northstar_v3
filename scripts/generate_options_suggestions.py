#!/usr/bin/env python3
"""Generate the daily options suggestions off live v3 output.

Runs the unified OptionsOrgan against the current v3 artifacts (daily scorer
scores, sentiment, canonical prices, portfolio holdings) and writes the ranked
suggestions (shorts / longs / hedges / opportunities) to
data/options/suggestions/options_suggestions_latest.json.

This is the daily entry point for the options complement; it is advisory and
never places an order.

    python3 scripts/generate_options_suggestions.py
    python3 scripts/generate_options_suggestions.py --print
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.options.options_organ import OptionsOrgan  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Generate daily options suggestions from v3 output")
    p.add_argument("--print", action="store_true", dest="do_print", help="Print the suggestions")
    p.add_argument("--target-dte", type=int, default=None, help="Override target days-to-expiry")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = {}
    if args.target_dte:
        config = {"options_organ": {"target_dte": args.target_dte}}

    organ = OptionsOrgan(config=config)
    suggestions = organ.run_from_v3_artifacts()
    counts = dict(Counter(s.category for s in suggestions))
    continued = sum(1 for s in suggestions if s.status == "continued")
    print(f"OptionsOrgan: {len(suggestions)} suggestions {counts} "
          f"({continued} continued from prior days) -> {organ.report_path}")

    # History-based "what happened last week" view.
    if organ._store is not None:
        summ = organ._store.recent_summary(lookback_days=7)
        print(f"Last {summ['days']} trading day(s): {summ['by_category']}")
        if summ["persistent_names"]:
            top = ", ".join(f"{p['underlying']}({p['category']},{p['days']}d)"
                            for p in summ["persistent_names"][:6])
            print(f"Persistent convictions: {top}")

    if args.do_print:
        for s in suggestions:
            mp = "uncapped" if s.max_profit in (None, float("inf")) else f"{s.max_profit:,.0f}"
            print(
                f"[{s.category:11s}] {s.underlying:16s} {s.structure:18s} "
                f"debit/credit={s.net_debit_credit:>10,.0f} maxloss={s.max_loss:>9,.0f} "
                f"maxprofit={mp:>9} | {s.thesis[:55]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
