"""Direct Preference Optimisation loss for Arya."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def sequence_log_probs(model, ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    logits = model(ids)
    if isinstance(logits, tuple):
        logits = logits[0]
    log_probs = F.log_softmax(logits[:, :-1], dim=-1)
    targets = ids[:, 1:]
    token_log_probs = log_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    return (token_log_probs * mask[:, 1:].to(token_log_probs.dtype)).sum(dim=-1)


def dpo_loss(
    model,
    ref_model,
    chosen_ids: torch.Tensor,
    chosen_mask: torch.Tensor,
    rejected_ids: torch.Tensor,
    rejected_mask: torch.Tensor,
    beta: float = 0.1,
) -> tuple[torch.Tensor, float]:
    """Return DPO loss and average reward margin.

    Reference-model probabilities are detached; policy probabilities keep their
    gradient so optimisation updates only the current model.
    """

    with torch.no_grad():
        ref_chosen_lp = sequence_log_probs(ref_model, chosen_ids, chosen_mask)
        ref_rejected_lp = sequence_log_probs(ref_model, rejected_ids, rejected_mask)

    policy_chosen_lp = sequence_log_probs(model, chosen_ids, chosen_mask)
    policy_rejected_lp = sequence_log_probs(model, rejected_ids, rejected_mask)

    chosen_ratio = policy_chosen_lp - ref_chosen_lp
    rejected_ratio = policy_rejected_lp - ref_rejected_lp
    preference_logit = chosen_ratio - rejected_ratio
    loss = -F.logsigmoid(beta * preference_logit).mean()
    reward_margin = float(preference_logit.detach().mean().item())
    return loss, reward_margin

