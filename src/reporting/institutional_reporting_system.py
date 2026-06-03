#!/usr/bin/env python3
"""
Institutional reporting compatibility surface.

The reporting layer is not fully implemented yet, so this module logs clearly
when it is asked to persist or render institutional outputs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class InstitutionalReportingSystem:
    def __init__(self):
        logger.info("InstitutionalReportingSystem initialized")

    def record_daily_data(
        self,
        specialists_data: Dict[str, Any],
        market_data: Dict[str, Any],
        allocations: Dict[str, Any],
    ) -> None:
        logger.info(
            "InstitutionalReportingSystem.record_daily_data() called but persistence "
            "is not implemented yet; data will not be written."
        )

    def generate_monthly_report(self) -> dict:
        logger.warning(
            "InstitutionalReportingSystem.generate_monthly_report() called but the "
            "monthly institutional report is not implemented yet."
        )
        return {"status": "not_implemented", "report": {}}
