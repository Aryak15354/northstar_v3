"""Finance QA benchmark primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceQAItem:
    question: str
    expected_terms: tuple[str, ...]


FINANCE_QA_SEED = [
    FinanceQAItem(
        "What does India VIX measure, and what is considered an elevated reading?",
        ("volatility", "nifty", "fear"),
    ),
    FinanceQAItem(
        "What is the difference between a repo rate and a reverse repo rate?",
        ("rbi", "borrow", "lend"),
    ),
    FinanceQAItem(
        "What does FII stand for and how do FII flows typically affect the NIFTY?",
        ("foreign institutional investor", "flows", "nifty"),
    ),
    FinanceQAItem(
        "What is SEBI and what is its primary regulatory function?",
        ("securities", "regulator", "india"),
    ),
    FinanceQAItem(
        "What is promoter pledging and why does it signal risk?",
        ("shares", "collateral", "risk"),
    ),
]


def score_keyword_qa(answers: dict[str, str], items: list[FinanceQAItem] | None = None) -> float:
    items = items or FINANCE_QA_SEED
    if not items:
        return 0.0
    correct = 0
    for item in items:
        answer = answers.get(item.question, "").lower()
        if any(term.lower() in answer for term in item.expected_terms):
            correct += 1
    return correct / len(items)

