from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations_with_replacement
from typing import List, Tuple

from simulator import CostConfig, EvalResult, SimConfig, monte_carlo_evaluate
from strategy import ThresholdStrategy


@dataclass(frozen=True)
class SearchConfig:
    max_threshold: int = 20
    coarse_n: int = 20000
    fine_n: int = 200000
    keep_top_k: int = 30
    output_top_n: int = 10
    include_logic_gate: bool = True


def generate_monotonic_thresholds(max_threshold: int):
    for a1, a2, a3, a4 in combinations_with_replacement(range(max_threshold + 1), 4):
        yield a1, a2, a3, a4


def search_strategies(sim_cfg: SimConfig, cost_cfg: CostConfig, search_cfg: SearchConfig, seed: int = 42) -> List[EvalResult]:
    coarse_results: List[Tuple[ThresholdStrategy, EvalResult]] = []
    gates = [False, True] if search_cfg.include_logic_gate else [False]

    idx = 0
    for a1, a2, a3, a4 in generate_monotonic_thresholds(search_cfg.max_threshold):
        for gate in gates:
            st = ThresholdStrategy(a1=a1, a2=a2, a3=a3, a4=a4, require_high_attack_in_first_two=gate)
            res = monte_carlo_evaluate(st, sim_cfg, cost_cfg, n_runs=search_cfg.coarse_n, seed=seed + idx)
            coarse_results.append((st, res))
            idx += 1

    coarse_results.sort(key=lambda x: x[1].expected_server_coins)
    shortlisted = coarse_results[: search_cfg.keep_top_k]

    fine_results: List[EvalResult] = []
    for j, (strategy, _) in enumerate(shortlisted):
        fine = monte_carlo_evaluate(strategy, sim_cfg, cost_cfg, n_runs=search_cfg.fine_n, seed=seed + 100000 + j)
        fine_results.append(fine)

    fine_results.sort(key=lambda x: x.expected_server_coins)
    return fine_results[: search_cfg.output_top_n]
