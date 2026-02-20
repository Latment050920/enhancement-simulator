from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations_with_replacement
from typing import Callable, Dict, List, Optional, Tuple

from simulator import CostConfig, EvalResult, SimConfig, monte_carlo_evaluate
from strategy import ThresholdStrategy

SearchProgressFn = Callable[[Dict[str, float]], None]


@dataclass(frozen=True)
class SearchConfig:
    max_threshold: int = 20
    coarse_n: int = 20000
    fine_n: int = 200000
    keep_top_k: int = 30
    output_top_n: int = 10
    include_logic_gate: bool = True


def count_total_strategies(max_threshold: int, include_logic_gate: bool) -> int:
    base = 0
    for _ in combinations_with_replacement(range(max_threshold + 1), 4):
        base += 1
    return base * (2 if include_logic_gate else 1)


def generate_monotonic_thresholds(max_threshold: int):
    for a1, a2, a3, a4 in combinations_with_replacement(range(max_threshold + 1), 4):
        yield a1, a2, a3, a4


def search_strategies(
    sim_cfg: SimConfig,
    cost_cfg: CostConfig,
    search_cfg: SearchConfig,
    seed: int = 42,
    progress: bool = False,
    progress_every: int = 20,
    progress_cb: Optional[SearchProgressFn] = None,
) -> List[EvalResult]:
    coarse_results: List[Tuple[ThresholdStrategy, EvalResult]] = []
    gates = [False, True] if search_cfg.include_logic_gate else [False]
    total = count_total_strategies(search_cfg.max_threshold, search_cfg.include_logic_gate)

    idx = 0
    for a1, a2, a3, a4 in generate_monotonic_thresholds(search_cfg.max_threshold):
        for gate in gates:
            st = ThresholdStrategy(a1=a1, a2=a2, a3=a3, a4=a4, require_high_attack_in_first_two=gate)
            res = monte_carlo_evaluate(st, sim_cfg, cost_cfg, n_runs=search_cfg.coarse_n, seed=seed + idx)
            coarse_results.append((st, res))
            idx += 1
            if progress and (idx % progress_every == 0 or idx == total):
                topk = sorted([x[1].expected_server_coins for x in coarse_results])[: search_cfg.keep_top_k]
                threshold = topk[-1] if topk else 0.0
                payload = {
                    "phase": 1.0,
                    "done": float(idx),
                    "total": float(total),
                    "percent": idx / total * 100.0,
                    "topk_threshold": threshold,
                }
                if progress_cb:
                    progress_cb(payload)

    coarse_results.sort(key=lambda x: x[1].expected_server_coins)
    shortlisted = coarse_results[: search_cfg.keep_top_k]

    fine_results: List[EvalResult] = []
    for j, (strategy, _) in enumerate(shortlisted, start=1):
        fine = monte_carlo_evaluate(strategy, sim_cfg, cost_cfg, n_runs=search_cfg.fine_n, seed=seed + 100000 + j)
        fine_results.append(fine)
        if progress:
            payload = {
                "phase": 2.0,
                "done": float(j),
                "total": float(len(shortlisted)),
                "percent": j / len(shortlisted) * 100.0,
            }
            if progress_cb:
                progress_cb(payload)

    fine_results.sort(key=lambda x: x.expected_server_coins)
    return fine_results[: search_cfg.output_top_n]
