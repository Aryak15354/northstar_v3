"""Phase 2 constrained parameter-surface exploration and filtering."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class SurfaceThresholds:
    """Default Phase 2 stability thresholds."""

    min_test_sharpe: float = 0.80
    min_shrunk_train_sharpe: float = 0.70
    max_gradient_norm: float = 1.00
    max_curvature: float = 1.00
    min_neighbor_stability: float = 1.00
    max_surface_variance_ratio: float = 0.90
    min_plateau_width: int = 3
    max_drift: float = 0.50
    max_regime_variance: float = 0.80
    min_noise_robustness_score: float = 1.00
    max_neighbor_collapse: float = 0.50
    plateau_relative_threshold: float = 0.90
    min_points_for_geometry: int = 9
    bayes_shrink_k: float = 50.0
    monte_carlo_sims: int = 50
    monte_carlo_noise_scale: float = 0.10
    conditional_spread_threshold: float = 0.75


@dataclass(frozen=True)
class SurfacePointResult:
    parameter_hash: str
    params: Dict[str, Any]
    train_sharpe: float
    test_sharpe: float
    shrunk_train_sharpe: float
    gradient_norm: float
    curvature: float
    neighbor_stability: float
    surface_variance_ratio: float
    plateau_width: int
    drift: float
    regime_variance: float
    weighted_regime_score: float
    perturbation_drop: float
    noise_robustness_score: float
    neighbor_collapse: float
    regime_tag: str
    status: str
    reject_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter_hash": self.parameter_hash,
            "params": dict(self.params),
            "train_sharpe": float(self.train_sharpe),
            "test_sharpe": float(self.test_sharpe),
            "shrunk_train_sharpe": float(self.shrunk_train_sharpe),
            "gradient_norm": float(self.gradient_norm),
            "curvature": float(self.curvature),
            "neighbor_stability": float(self.neighbor_stability),
            "surface_variance_ratio": float(self.surface_variance_ratio),
            "plateau_width": int(self.plateau_width),
            "drift": float(self.drift),
            "regime_variance": float(self.regime_variance),
            "weighted_regime_score": float(self.weighted_regime_score),
            "perturbation_drop": float(self.perturbation_drop),
            "noise_robustness_score": float(self.noise_robustness_score),
            "neighbor_collapse": float(self.neighbor_collapse),
            "regime_tag": str(self.regime_tag),
            "status": str(self.status),
            "reject_reason": str(self.reject_reason),
        }


class ParameterSurfaceExplorer:
    """Compute Phase 2 surface geometry and retain plateau-like candidates."""

    def __init__(self, thresholds: SurfaceThresholds | None = None, *, random_seed: int = 42):
        self.thresholds = thresholds or SurfaceThresholds()
        self.random_seed = int(random_seed)

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    @staticmethod
    def _is_numeric_axis(values: Sequence[Any]) -> bool:
        if not values:
            return False
        for v in values:
            if isinstance(v, bool):
                return False
            if isinstance(v, (int, float, np.integer, np.floating)):
                continue
            return False
        return True

    def _axis_values(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        parameter_grid: Mapping[str, Sequence[Any]] | None = None,
    ) -> Dict[str, List[Any]]:
        if parameter_grid:
            axes: Dict[str, List[Any]] = {}
            for key in sorted(parameter_grid):
                vals = list(parameter_grid.get(key, []) or [])
                if vals:
                    axes[str(key)] = vals
            if axes:
                return axes

        observed: Dict[str, List[Any]] = {}
        for row in rows:
            params = dict(row.get("params", {}) or {})
            for key, value in params.items():
                observed.setdefault(str(key), []).append(value)

        out: Dict[str, List[Any]] = {}
        for key in sorted(observed):
            uniq = list(dict.fromkeys(observed[key]))
            if self._is_numeric_axis(uniq):
                uniq = sorted(uniq, key=lambda x: float(x))
            else:
                uniq = sorted(uniq, key=lambda x: str(x))
            out[key] = uniq
        return out

    def _coords(
        self,
        rows: Sequence[Mapping[str, Any]],
        axes: Mapping[str, Sequence[Any]],
    ) -> Dict[str, Tuple[int, ...]]:
        idx_map: Dict[str, Dict[Any, int]] = {}
        axis_names = list(axes.keys())
        for name in axis_names:
            idx_map[name] = {v: i for i, v in enumerate(list(axes[name]))}

        out: Dict[str, Tuple[int, ...]] = {}
        for row in rows:
            ph = str(row.get("parameter_hash", ""))
            params = dict(row.get("params", {}) or {})
            c: List[int] = []
            ok = True
            for name in axis_names:
                value = params.get(name)
                if value not in idx_map[name]:
                    ok = False
                    break
                c.append(int(idx_map[name][value]))
            if ok:
                out[ph] = tuple(c)
        return out

    @staticmethod
    def _neighbors(coord: Tuple[int, ...], coord_map: Mapping[str, Tuple[int, ...]], *, include_self: bool = False) -> List[str]:
        out: List[str] = []
        for ph, other in coord_map.items():
            if len(other) != len(coord):
                continue
            diffs = [abs(int(a) - int(b)) for a, b in zip(coord, other)]
            if max(diffs, default=0) <= 1:
                if (not include_self) and tuple(other) == tuple(coord):
                    continue
                out.append(ph)
        return out

    def _finite_diff_gradient(
        self,
        *,
        ph: str,
        coord: Tuple[int, ...],
        coord_to_hash: Mapping[Tuple[int, ...], str],
        axes: Mapping[str, Sequence[Any]],
        surface: Mapping[str, float],
    ) -> float:
        grads: List[float] = []
        axis_names = list(axes.keys())
        for axis_idx, axis_name in enumerate(axis_names):
            i = int(coord[axis_idx])
            vals = list(axes[axis_name])
            n = len(vals)
            if n <= 1:
                grads.append(0.0)
                continue

            prev_coord = list(coord)
            next_coord = list(coord)
            prev_coord[axis_idx] = max(0, i - 1)
            next_coord[axis_idx] = min(n - 1, i + 1)
            prev_t = tuple(prev_coord)
            next_t = tuple(next_coord)
            prev_ph = coord_to_hash.get(prev_t, ph)
            next_ph = coord_to_hash.get(next_t, ph)

            prev_v = self._safe_float(surface.get(prev_ph, surface.get(ph, 0.0)))
            next_v = self._safe_float(surface.get(next_ph, surface.get(ph, 0.0)))
            cur_v = self._safe_float(surface.get(ph, 0.0))

            numeric = self._is_numeric_axis(vals)
            if numeric:
                x_prev = self._safe_float(vals[prev_coord[axis_idx]], float(prev_coord[axis_idx]))
                x_next = self._safe_float(vals[next_coord[axis_idx]], float(next_coord[axis_idx]))
                denom = float(x_next - x_prev)
                if abs(denom) < 1e-12:
                    denom = 1.0
            else:
                denom = float(next_coord[axis_idx] - prev_coord[axis_idx])
                if abs(denom) < 1e-12:
                    denom = 1.0

            if i <= 0:
                g = (next_v - cur_v) / max(1e-12, abs(denom))
            elif i >= (n - 1):
                g = (cur_v - prev_v) / max(1e-12, abs(denom))
            else:
                g = (next_v - prev_v) / max(1e-12, abs(denom))
            grads.append(float(g))
        return float(np.linalg.norm(np.asarray(grads, dtype=float), ord=2))

    def _finite_diff_curvature(
        self,
        *,
        ph: str,
        coord: Tuple[int, ...],
        coord_to_hash: Mapping[Tuple[int, ...], str],
        axes: Mapping[str, Sequence[Any]],
        surface: Mapping[str, float],
    ) -> float:
        axis_names = list(axes.keys())
        cur_v = self._safe_float(surface.get(ph, 0.0))
        pieces: List[float] = []
        for axis_idx, axis_name in enumerate(axis_names):
            i = int(coord[axis_idx])
            vals = list(axes[axis_name])
            n = len(vals)
            if i <= 0 or i >= (n - 1):
                pieces.append(0.0)
                continue
            prev_coord = list(coord)
            next_coord = list(coord)
            prev_coord[axis_idx] = i - 1
            next_coord[axis_idx] = i + 1
            prev_ph = coord_to_hash.get(tuple(prev_coord), ph)
            next_ph = coord_to_hash.get(tuple(next_coord), ph)
            prev_v = self._safe_float(surface.get(prev_ph, cur_v))
            next_v = self._safe_float(surface.get(next_ph, cur_v))

            numeric = self._is_numeric_axis(vals)
            if numeric:
                x0 = self._safe_float(vals[i - 1], float(i - 1))
                x1 = self._safe_float(vals[i], float(i))
                x2 = self._safe_float(vals[i + 1], float(i + 1))
                d = max(1e-12, abs((x2 - x1) * (x1 - x0)))
            else:
                d = 1.0
            second = (next_v - (2.0 * cur_v) + prev_v) / d
            pieces.append(abs(float(second)))
        return float(np.sum(np.asarray(pieces, dtype=float)))

    @staticmethod
    def _extract_regime_scores(row: Mapping[str, Any]) -> Dict[str, float]:
        aggregate = dict(row.get("aggregate_metrics", {}) or {})
        regime_scores = aggregate.get("regime_sharpes")
        if isinstance(regime_scores, Mapping):
            out: Dict[str, float] = {}
            for k, v in regime_scores.items():
                out[str(k)] = float(v)
            return out

        fold_rows = list(row.get("fold_rows", []) or [])
        out_lists: Dict[str, List[float]] = {}
        for fr in fold_rows:
            regime = str(dict(fr or {}).get("regime", "")).strip()
            if not regime:
                continue
            out_lists.setdefault(regime, []).append(float(dict(fr or {}).get("test_sharpe", 0.0) or 0.0))
        out: Dict[str, float] = {}
        for r, vals in out_lists.items():
            if vals:
                out[r] = float(np.mean(np.asarray(vals, dtype=float)))
        return out

    @staticmethod
    def _extract_regime_priors(row: Mapping[str, Any]) -> Dict[str, float]:
        aggregate = dict(row.get("aggregate_metrics", {}) or {})
        priors = aggregate.get("regime_probabilities")
        out: Dict[str, float] = {}
        if isinstance(priors, Mapping):
            for k, v in priors.items():
                try:
                    out[str(k)] = float(v)
                except Exception:
                    continue
        return out

    def _regime_metrics(self, row: Mapping[str, Any]) -> Tuple[float, float, str]:
        regime_scores = self._extract_regime_scores(row)
        if not regime_scores:
            return 0.0, self._safe_float(dict(row.get("aggregate_metrics", {}) or {}).get("avg_sharpe", 0.0), 0.0), "unknown"

        scores = np.asarray(list(regime_scores.values()), dtype=float)
        var = float(np.var(scores))
        spread = float(np.max(scores) - np.min(scores)) if scores.size else 0.0
        tag = "conditional" if spread >= self.thresholds.conditional_spread_threshold else "core"

        priors = self._extract_regime_priors(row)
        if priors:
            total = float(sum(max(0.0, self._safe_float(v, 0.0)) for v in priors.values()))
            weighted = 0.0
            if total > 1e-12:
                for name, score in regime_scores.items():
                    p = max(0.0, self._safe_float(priors.get(name, 0.0), 0.0)) / total
                    weighted += float(p * score)
            else:
                weighted = float(np.mean(scores))
        else:
            weighted = float(np.mean(scores))
        return var, weighted, tag

    def _monte_carlo_noise_metrics(self, fold_rows: Sequence[Mapping[str, Any]], *, seed_offset: int = 0) -> Tuple[float, float]:
        series = np.asarray(
            [self._safe_float(dict(r or {}).get("test_sharpe", 0.0), 0.0) for r in list(fold_rows or [])],
            dtype=float,
        )
        if series.size <= 1:
            return 0.0, 1.0
        base = float(np.mean(series))
        sigma = float(np.std(series))
        if sigma <= 1e-12:
            return 0.0, 1.0

        rng = np.random.default_rng(self.random_seed + int(seed_offset))
        sims: List[float] = []
        noise_sigma = sigma * float(max(0.0, self.thresholds.monte_carlo_noise_scale))
        n_sim = max(10, int(self.thresholds.monte_carlo_sims))
        for _ in range(n_sim):
            eps = rng.normal(0.0, noise_sigma, size=series.size)
            perturbed = series + eps
            p_mu = float(np.mean(perturbed))
            p_sigma = float(np.std(perturbed))
            sims.append(float(p_mu / (p_sigma + 1e-6)))
        sims_arr = np.asarray(sims, dtype=float)
        mc_mean = float(np.mean(sims_arr))
        mc_std = float(np.std(sims_arr))
        nrs = float(mc_mean / (mc_std + 1e-6))
        perturbation_drop = float(max(0.0, base - mc_mean))
        return perturbation_drop, nrs

    def _plateau_width(
        self,
        *,
        ph: str,
        coord: Tuple[int, ...],
        coord_map: Mapping[str, Tuple[int, ...]],
        values: Mapping[str, float],
    ) -> int:
        neighbors = self._neighbors(coord, coord_map, include_self=True)
        if not neighbors:
            return 1
        local_vals = np.asarray([self._safe_float(values.get(n, 0.0), 0.0) for n in neighbors], dtype=float)
        local_max = float(np.max(local_vals)) if local_vals.size else self._safe_float(values.get(ph, 0.0), 0.0)
        threshold = float(self.thresholds.plateau_relative_threshold * local_max)

        eligible = {
            n
            for n, v in values.items()
            if self._safe_float(v, 0.0) >= threshold
        }
        if ph not in eligible:
            return 1

        q: deque[str] = deque([ph])
        seen: set[str] = {ph}
        while q:
            cur = q.popleft()
            cur_coord = coord_map.get(cur)
            if cur_coord is None:
                continue
            for nxt in self._neighbors(cur_coord, coord_map, include_self=False):
                if nxt in seen or nxt not in eligible:
                    continue
                seen.add(nxt)
                q.append(nxt)
        return int(max(1, len(seen)))

    def _classify(
        self,
        *,
        n_points: int,
        test_sharpe: float,
        shrunk_train: float,
        gradient: float,
        curvature: float,
        ns: float,
        svr: float,
        plateau: int,
        drift: float,
        regime_var: float,
        nrs: float,
        neighbor_collapse: float,
    ) -> Tuple[str, str]:
        if test_sharpe < self.thresholds.min_test_sharpe:
            return "reject", "test_sharpe_below_threshold"
        if drift > self.thresholds.max_drift:
            return "reject", "train_test_drift_above_threshold"
        if regime_var > self.thresholds.max_regime_variance:
            return "reject", "regime_variance_above_threshold"
        if nrs < self.thresholds.min_noise_robustness_score:
            return "reject", "noise_robustness_below_threshold"

        if n_points >= int(self.thresholds.min_points_for_geometry):
            if shrunk_train < self.thresholds.min_shrunk_train_sharpe:
                return "reject", "shrunk_train_sharpe_below_threshold"
            if neighbor_collapse > self.thresholds.max_neighbor_collapse:
                return "reject", "neighbor_sharpe_collapse_above_threshold"
            if gradient > self.thresholds.max_gradient_norm:
                return "reject", "gradient_above_threshold"
            if curvature > self.thresholds.max_curvature:
                return "reject", "curvature_above_threshold"
            if ns < self.thresholds.min_neighbor_stability:
                return "reject", "neighbor_stability_below_threshold"
            if svr > self.thresholds.max_surface_variance_ratio:
                return "reject", "surface_variance_ratio_above_threshold"
            if plateau < int(self.thresholds.min_plateau_width):
                return "reject", "plateau_width_below_threshold"

        return "candidate", "candidate"

    def evaluate(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        parameter_grid: Mapping[str, Sequence[Any]] | None = None,
    ) -> List[SurfacePointResult]:
        if not rows:
            return []

        axes = self._axis_values(rows, parameter_grid=parameter_grid)
        coords = self._coords(rows, axes)
        coord_to_hash = {coord: ph for ph, coord in coords.items()}

        train = {
            str(r.get("parameter_hash", "")): self._safe_float(dict(r.get("aggregate_metrics", {}) or {}).get("avg_sharpe", 0.0), 0.0)
            for r in rows
        }
        test = {
            str(r.get("parameter_hash", "")): float(
                np.mean(
                    np.asarray(
                        [self._safe_float(dict(f or {}).get("test_sharpe", 0.0), 0.0) for f in list(r.get("fold_rows", []) or [])],
                        dtype=float,
                    )
                )
            )
            if list(r.get("fold_rows", []) or [])
            else self._safe_float(dict(r.get("aggregate_metrics", {}) or {}).get("avg_sharpe", 0.0), 0.0)
            for r in rows
        }
        sample_sizes = {
            str(r.get("parameter_hash", "")): max(1, len(list(r.get("fold_rows", []) or [])))
            for r in rows
        }

        train_vals = np.asarray(list(train.values()), dtype=float)
        global_train_mean = float(np.mean(train_vals)) if train_vals.size else 0.0
        global_train_var = float(np.var(train_vals)) if train_vals.size else 0.0
        global_train_var = max(1e-9, global_train_var)

        shrunk: Dict[str, float] = {}
        k = float(max(1.0, self.thresholds.bayes_shrink_k))
        for ph, s in train.items():
            n = float(max(1, sample_sizes.get(ph, 1)))
            lam = float(n / (n + k))
            shrunk[ph] = float((lam * s) + ((1.0 - lam) * global_train_mean))

        out: List[SurfacePointResult] = []
        n_points = len(rows)
        for idx, row in enumerate(rows):
            ph = str(row.get("parameter_hash", ""))
            params = dict(row.get("params", {}) or {})
            coord = coords.get(ph, tuple())
            if not coord:
                coord = tuple(0 for _ in axes.keys())

            neighbor_hashes = self._neighbors(coord, coords, include_self=False)
            local_vals = np.asarray([shrunk.get(n, 0.0) for n in neighbor_hashes] + [shrunk.get(ph, 0.0)], dtype=float)
            local_var = float(np.var(local_vals)) if local_vals.size else 0.0
            svr = float(local_var / global_train_var)

            ns = 0.0
            if neighbor_hashes:
                neigh = np.asarray([shrunk.get(n, 0.0) for n in neighbor_hashes], dtype=float)
                ns = float(np.mean(neigh) / (np.std(neigh) + 1e-6))

            gradient = self._finite_diff_gradient(
                ph=ph,
                coord=coord,
                coord_to_hash=coord_to_hash,
                axes=axes,
                surface=shrunk,
            )
            curvature = self._finite_diff_curvature(
                ph=ph,
                coord=coord,
                coord_to_hash=coord_to_hash,
                axes=axes,
                surface=shrunk,
            )
            plateau = self._plateau_width(ph=ph, coord=coord, coord_map=coords, values=shrunk)
            drift = abs(self._safe_float(train.get(ph, 0.0), 0.0) - self._safe_float(test.get(ph, 0.0), 0.0))
            regime_var, regime_weighted, regime_tag = self._regime_metrics(row)
            perturbation_drop, nrs = self._monte_carlo_noise_metrics(
                list(row.get("fold_rows", []) or []),
                seed_offset=idx,
            )

            neighbor_collapse = 0.0
            if neighbor_hashes:
                nvals = np.asarray([test.get(n, 0.0) for n in neighbor_hashes], dtype=float)
                min_neigh = float(np.min(nvals)) if nvals.size else 0.0
                self_val = self._safe_float(test.get(ph, 0.0), 0.0)
                if abs(self_val) > 1e-9:
                    neighbor_collapse = float(max(0.0, (self_val - min_neigh) / abs(self_val)))

            status, reason = self._classify(
                n_points=n_points,
                test_sharpe=self._safe_float(test.get(ph, 0.0), 0.0),
                shrunk_train=self._safe_float(shrunk.get(ph, 0.0), 0.0),
                gradient=self._safe_float(gradient, 0.0),
                curvature=self._safe_float(curvature, 0.0),
                ns=self._safe_float(ns, 0.0),
                svr=self._safe_float(svr, 0.0),
                plateau=int(plateau),
                drift=self._safe_float(drift, 0.0),
                regime_var=self._safe_float(regime_var, 0.0),
                nrs=self._safe_float(nrs, 0.0),
                neighbor_collapse=self._safe_float(neighbor_collapse, 0.0),
            )

            out.append(
                SurfacePointResult(
                    parameter_hash=ph,
                    params=params,
                    train_sharpe=self._safe_float(train.get(ph, 0.0), 0.0),
                    test_sharpe=self._safe_float(test.get(ph, 0.0), 0.0),
                    shrunk_train_sharpe=self._safe_float(shrunk.get(ph, 0.0), 0.0),
                    gradient_norm=self._safe_float(gradient, 0.0),
                    curvature=self._safe_float(curvature, 0.0),
                    neighbor_stability=self._safe_float(ns, 0.0),
                    surface_variance_ratio=self._safe_float(svr, 0.0),
                    plateau_width=int(plateau),
                    drift=self._safe_float(drift, 0.0),
                    regime_variance=self._safe_float(regime_var, 0.0),
                    weighted_regime_score=self._safe_float(regime_weighted, 0.0),
                    perturbation_drop=self._safe_float(perturbation_drop, 0.0),
                    noise_robustness_score=self._safe_float(nrs, 0.0),
                    neighbor_collapse=self._safe_float(neighbor_collapse, 0.0),
                    regime_tag=str(regime_tag),
                    status=str(status),
                    reject_reason=str(reason),
                )
            )
        return out
