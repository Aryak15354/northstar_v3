"""India-focused structural regime map for segmented research runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RegimeWindow:
    name: str
    start_date: str
    end_date: str
    category: str = "structural"
    description: str = ""


INDIA_REGIME_WINDOWS: List[RegimeWindow] = [
    RegimeWindow(
        name="dotcom_spillover",
        start_date="2000-01-01",
        end_date="2002-12-31",
        category="crisis",
        description="India IT-heavy drawdown linked to global dot-com unwind.",
    ),
    RegimeWindow(
        name="credit_supercycle",
        start_date="2003-01-01",
        end_date="2007-09-30",
        category="expansion",
        description="Leverage/capex-driven expansion with broad cyclicals participation.",
    ),
    RegimeWindow(
        name="gfc_liquidity_shock",
        start_date="2007-10-01",
        end_date="2009-06-30",
        category="crisis",
        description="Global liquidity stress with sharp FII outflows and INR weakness.",
    ),
    RegimeWindow(
        name="npa_policy_paralysis",
        start_date="2011-01-01",
        end_date="2013-12-31",
        category="stress",
        description="Twin-deficit and policy drag period with credit quality deterioration.",
    ),
    RegimeWindow(
        name="reform_rally",
        start_date="2014-05-01",
        end_date="2017-12-31",
        category="expansion",
        description="Post-election reform optimism with strong momentum regimes.",
    ),
    RegimeWindow(
        name="demonetization_liquidity_shock",
        start_date="2016-11-01",
        end_date="2017-06-30",
        category="crisis",
        description="Cash/liquidity shock with uneven sector-level impact.",
    ),
    RegimeWindow(
        name="nbfc_credit_crisis",
        start_date="2018-09-01",
        end_date="2019-12-31",
        category="crisis",
        description="Shadow banking stress and credit transmission disruption.",
    ),
    RegimeWindow(
        name="covid_lockdown_shock",
        start_date="2020-02-01",
        end_date="2020-06-30",
        category="crisis",
        description="Pandemic crash and rapid policy-led market stabilization.",
    ),
    RegimeWindow(
        name="retail_liquidity_bull",
        start_date="2020-07-01",
        end_date="2021-12-31",
        category="expansion",
        description="Retail flow-driven momentum expansion and speculative breadth.",
    ),
    RegimeWindow(
        name="inflation_tightening",
        start_date="2022-01-01",
        end_date="2023-12-31",
        category="stress",
        description="Inflation and policy tightening with factor/churn rotation.",
    ),
    RegimeWindow(
        name="corporate_governance_shock",
        start_date="2023-01-01",
        end_date="2023-12-31",
        category="event",
        description="Concentration/governance stress impacting index-level behavior.",
    ),
]


def regime_lookup() -> Dict[str, RegimeWindow]:
    return {r.name: r for r in INDIA_REGIME_WINDOWS}


def get_regime(name: str) -> Optional[RegimeWindow]:
    return regime_lookup().get(str(name).strip().lower())


def list_regimes(*, category: Optional[str] = None) -> List[RegimeWindow]:
    if category is None:
        return list(INDIA_REGIME_WINDOWS)
    key = str(category).strip().lower()
    return [r for r in INDIA_REGIME_WINDOWS if r.category.lower() == key]

