"""Regime-switching reinforcement learner for model selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class RLDecision:
    regime: int
    action: int
    reward: float


class RegimeSwitchAgent:
    def __init__(self, n_regimes: int, n_actions: int, epsilon: float = 0.10, random_state: int = 42):
        self.n_regimes = int(max(1, n_regimes))
        self.n_actions = int(max(1, n_actions))
        self.epsilon = float(max(0.0, min(1.0, epsilon)))
        self.q_table = np.zeros((self.n_regimes, self.n_actions), dtype=float)
        self.rng = np.random.default_rng(int(random_state))

    def select_action(self, regime: int) -> int:
        r = int(np.clip(regime, 0, self.n_regimes - 1))
        if self.rng.random() < self.epsilon:
            return int(self.rng.integers(0, self.n_actions))
        return int(np.argmax(self.q_table[r]))

    def update(self, regime: int, action: int, reward: float, next_regime: int, lr: float = 0.1, gamma: float = 0.95) -> None:
        r = int(np.clip(regime, 0, self.n_regimes - 1))
        a = int(np.clip(action, 0, self.n_actions - 1))
        nr = int(np.clip(next_regime, 0, self.n_regimes - 1))
        target = float(reward) + float(gamma) * float(np.max(self.q_table[nr]))
        self.q_table[r, a] += float(lr) * (target - self.q_table[r, a])

    def snapshot(self) -> Dict[str, List[List[float]]]:
        return {"q_table": self.q_table.tolist()}
