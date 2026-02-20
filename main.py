from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List

from search import SearchConfig, search_strategies
from simulator import CostConfig, SimConfig, monte_carlo_evaluate, parse_probability_vector
from strategy import ThresholdStrategy


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Minecraft enhancement simulator & strategy search")
    p.add_argument("--G", type=int, required=True, help="Target score threshold (S >= G)")
    p.add_argument("--N", type=int, default=200000, help="Monte Carlo runs for single-strategy evaluation")
    p.add_argument("--mode", choices=["discard", "mixed"], default="discard", help="Restart mode")
    p.add_argument("--restart-action", choices=["auto", "discard", "reset"], default="auto")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--probabilities", type=str, default="", help="26 comma-separated probabilities")

    p.add_argument("--a1", type=int, default=0)
    p.add_argument("--a2", type=int, default=0)
    p.add_argument("--a3", type=int, default=0)
    p.add_argument("--a4", type=int, default=0)
    p.add_argument("--gate2-ge3", action="store_true", help="Enable first-two-slot high-attack gate")

    p.add_argument("--search", action="store_true", help="Run two-stage threshold search")
    p.add_argument("--max-threshold", type=int, default=20)
    p.add_argument("--coarse-n", type=int, default=20000)
    p.add_argument("--fine-n", type=int, default=200000)
    p.add_argument("--top-k", type=int, default=30)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--disable-gate-search", action="store_true")

    p.add_argument("--compare-example", action="store_true", help="Compare built-in example strategies")
    p.add_argument("--similar-threshold-pct", type=float, default=5.0)

    p.add_argument("--out-dir", type=str, default="outputs")
    return p


def print_result(title: str, result):
    print(f"\n=== {title} ===")
    for k, v in result.to_dict().items():
        if isinstance(v, float):
            print(f"{k}: {v:.6f}")
        else:
            print(f"{k}: {v}")


def save_results_json_csv(results: List, out_base: Path) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)

    payload = [r.to_dict() for r in results]
    with open(out_base.with_suffix(".json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(out_base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        if not payload:
            return
        writer = csv.DictWriter(f, fieldnames=list(payload[0].keys()))
        writer.writeheader()
        writer.writerows(payload)


def compare_and_conclude(results: List, similar_threshold_pct: float) -> None:
    if len(results) < 2:
        return
    baseline = results[0].expected_server_coins
    print("\n=== Strategy Difference Summary ===")
    for r in results[1:]:
        diff_pct = (r.expected_server_coins - baseline) / baseline * 100.0
        verdict = "差不多" if abs(diff_pct) < similar_threshold_pct else "有明显差异"
        print(f"vs {r.strategy_desc}: diff={diff_pct:.2f}% -> {verdict}")


def main() -> None:
    args = build_parser().parse_args()

    probs = parse_probability_vector(args.probabilities, attr_count=26)
    sim_cfg = SimConfig(
        goal_score=args.G,
        mode=args.mode,
        restart_action=args.restart_action,
        probs=probs,
    )
    cost_cfg = CostConfig()

    all_results = []

    single_strategy = ThresholdStrategy(
        a1=args.a1,
        a2=args.a2,
        a3=args.a3,
        a4=args.a4,
        require_high_attack_in_first_two=args.gate2_ge3,
    )
    single_result = monte_carlo_evaluate(single_strategy, sim_cfg, cost_cfg, n_runs=args.N, seed=args.seed)
    print_result("Single Strategy", single_result)
    all_results.append(single_result)

    if args.compare_example:
        # Example 1: someone proposed
        proposed = ThresholdStrategy(a1=3, a2=6, a3=8, a4=11, require_high_attack_in_first_two=False)
        mine = ThresholdStrategy(a1=0, a2=0, a3=0, a4=8, require_high_attack_in_first_two=True)

        p_res = monte_carlo_evaluate(proposed, sim_cfg, cost_cfg, n_runs=args.N, seed=args.seed + 1)
        m_res = monte_carlo_evaluate(mine, sim_cfg, cost_cfg, n_runs=args.N, seed=args.seed + 2)
        print_result("Compare: Proposed (3,6,8,11)", p_res)
        print_result("Compare: Mine (gate2>=3 + a4=8)", m_res)
        all_results.extend([p_res, m_res])

    if args.search:
        search_cfg = SearchConfig(
            max_threshold=args.max_threshold,
            coarse_n=args.coarse_n,
            fine_n=args.fine_n,
            keep_top_k=args.top_k,
            output_top_n=args.top_n,
            include_logic_gate=not args.disable_gate_search,
        )
        top_results = search_strategies(sim_cfg, cost_cfg, search_cfg, seed=args.seed)
        print("\n=== Top Strategies (by expected server coins) ===")
        for i, r in enumerate(top_results, start=1):
            print(f"#{i} {r.strategy_desc} -> coins={r.expected_server_coins:.2f}, diamonds={r.expected_diamonds:.3f}, tears={r.expected_tears:.3f}")
        all_results.extend(top_results)

    compare_and_conclude(all_results[:3], args.similar_threshold_pct)

    base = Path(args.out_dir) / f"results_G{args.G}_{args.mode}"
    save_results_json_csv(all_results, base)
    print(f"\nSaved results to {base.with_suffix('.json')} and {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
