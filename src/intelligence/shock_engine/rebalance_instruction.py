from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InstructionType(str, Enum):
    REDUCE_EQUITY = "reduce_equity"
    INCREASE_EQUITY = "increase_equity"
    HEDGE_WITH_OPTIONS = "hedge_with_options"


class InstructionUrgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IMMEDIATE = "immediate"


@dataclass
class RebalanceInstruction:
    instruction_type: InstructionType
    symbol: str
    sector: str
    urgency: InstructionUrgency
    current_weight: float
    target_weight_change: float
    max_reducible_quantity: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptionsInstruction:
    strategy: str
    underlying: str
    objective: str
    urgency: InstructionUrgency
    sizing_lots: int
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShockResponsePlan:
    rebalance_instructions: list[RebalanceInstruction] = field(default_factory=list)
    options_instructions: list[OptionsInstruction] = field(default_factory=list)
