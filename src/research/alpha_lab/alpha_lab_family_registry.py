"""Phase 1 alpha-family ontology loader and validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _yaml_module():
    import yaml

    return yaml


def _str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_to_str(v) for v in value if _to_str(v)]
    s = _to_str(value)
    return [s] if s else []


def _param_axes(value: Any) -> Dict[str, List[Any]]:
    if not isinstance(value, Mapping):
        return {}
    out: Dict[str, List[Any]] = {}
    for key, raw_vals in value.items():
        axis = _to_str(key)
        if not axis:
            continue
        if isinstance(raw_vals, (list, tuple, set)):
            vals = [v for v in raw_vals]
        elif raw_vals is None:
            vals = []
        else:
            vals = [raw_vals]
        out[axis] = vals
    return out


@dataclass(frozen=True)
class AlphaFamily:
    """Economic alpha hypothesis family definition."""

    key: str
    label: str
    family_type: str
    hypothesis: str
    structural_rationale: List[str] = field(default_factory=list)
    core_signal_form: str = ""
    parameter_axes: Dict[str, List[Any]] = field(default_factory=dict)
    interaction_axes: List[str] = field(default_factory=list)
    activation_variables: List[str] = field(default_factory=list)
    works_when: List[str] = field(default_factory=list)
    fails_when: List[str] = field(default_factory=list)
    expected_decay: str = ""
    holding_period_days: str = ""
    risk_profile: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "family_type": self.family_type,
            "hypothesis": self.hypothesis,
            "structural_rationale": list(self.structural_rationale),
            "core_signal_form": self.core_signal_form,
            "parameter_axes": dict(self.parameter_axes),
            "interaction_axes": list(self.interaction_axes),
            "activation_variables": list(self.activation_variables),
            "works_when": list(self.works_when),
            "fails_when": list(self.fails_when),
            "expected_decay": self.expected_decay,
            "holding_period_days": self.holding_period_days,
            "risk_profile": self.risk_profile,
        }


class AlphaFamilyRegistry:
    """In-memory registry for alpha families declared in YAML."""

    DEFAULT_PATH = Path("config/alpha_family_registry.yaml")

    def __init__(self, families: Mapping[str, AlphaFamily] | None = None, *, metadata: Mapping[str, Any] | None = None):
        self._families: Dict[str, AlphaFamily] = dict(sorted((families or {}).items(), key=lambda kv: kv[0]))
        self.metadata: Dict[str, Any] = dict(metadata or {})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AlphaFamilyRegistry":
        root = dict(payload or {})
        raw_families = root.get("families", {})
        if not isinstance(raw_families, Mapping):
            raise ValueError("alpha family registry must contain mapping key 'families'")

        families: Dict[str, AlphaFamily] = {}
        for key, raw in sorted(raw_families.items(), key=lambda kv: str(kv[0])):
            family_key = _to_str(key)
            if not family_key:
                continue
            node = dict(raw or {}) if isinstance(raw, Mapping) else {}
            families[family_key] = AlphaFamily(
                key=family_key,
                label=_to_str(node.get("label")) or family_key,
                family_type=_to_str(node.get("family_type")) or "core",
                hypothesis=_to_str(node.get("hypothesis")),
                structural_rationale=_str_list(node.get("structural_rationale")),
                core_signal_form=_to_str(node.get("core_signal_form")),
                parameter_axes=_param_axes(node.get("parameter_axes")),
                interaction_axes=_str_list(node.get("interaction_axes")),
                activation_variables=_str_list(node.get("activation_variables")),
                works_when=_str_list(node.get("works_when")),
                fails_when=_str_list(node.get("fails_when")),
                expected_decay=_to_str(node.get("expected_decay")),
                holding_period_days=_to_str(node.get("holding_period_days")),
                risk_profile=_to_str(node.get("risk_profile")),
            )

        metadata = {k: v for k, v in root.items() if k != "families"}
        return cls(families=families, metadata=metadata)

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "AlphaFamilyRegistry":
        p = Path(path) if path is not None else cls.DEFAULT_PATH
        with p.open("r", encoding="utf-8") as f:
            payload = _yaml_module().safe_load(f) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"invalid alpha family registry yaml at {p}")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.metadata)
        out["families"] = {k: v.to_dict() for k, v in self._families.items()}
        return out

    def keys(self) -> List[str]:
        return list(self._families.keys())

    def list(self) -> List[AlphaFamily]:
        return [self._families[k] for k in sorted(self._families)]

    def get(self, key: str) -> AlphaFamily | None:
        return self._families.get(_to_str(key))

    def extend(self, families: Iterable[AlphaFamily]) -> None:
        mutable = dict(self._families)
        for family in families:
            mutable[str(family.key)] = family
        self._families = dict(sorted(mutable.items(), key=lambda kv: kv[0]))

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._families:
            return ["registry has no families"]

        for key, family in self._families.items():
            prefix = f"family:{key}"
            if not family.hypothesis:
                errors.append(f"{prefix}: missing hypothesis")
            if not family.structural_rationale:
                errors.append(f"{prefix}: missing structural_rationale")
            if not family.core_signal_form:
                errors.append(f"{prefix}: missing core_signal_form")
            if not family.activation_variables:
                errors.append(f"{prefix}: missing activation_variables")
            if not family.works_when:
                errors.append(f"{prefix}: missing works_when")
            if not family.fails_when:
                errors.append(f"{prefix}: missing fails_when")
            if not family.parameter_axes:
                errors.append(f"{prefix}: missing parameter_axes")
        return errors

    def require_valid(self) -> None:
        errors = self.validate()
        if errors:
            preview = "; ".join(errors[:8])
            raise ValueError(f"invalid alpha family registry ({len(errors)} issues): {preview}")
