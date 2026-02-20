from __future__ import annotations

import argparse
import itertools
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reporter import write_report
from search import SearchConfig, search_strategies
from simulator import CostConfig, SimConfig, monte_carlo_evaluate, parse_probability_vector
from strategy import ThresholdStrategy

try:
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn
except Exception:
    Progress = None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Minecraft enhancement simulator & strategy search")
    p.add_argument("--G", type=str, required=True, help="Target score threshold (single int or comma list)")
    p.add_argument("--N", type=int, default=200000, help="Monte Carlo runs for single-strategy evaluation")
    p.add_argument("--mode", choices=["discard", "mixed"], default="discard", help="Restart mode")
    p.add_argument("--restart-action", choices=["auto", "discard", "reset"], default="auto")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--probabilities", type=str, default="", help="26 comma-separated probabilities")
    p.add_argument("--probabilities-envs", type=str, default="", help="Multiple envs split by ';'")

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

    p.add_argument("--progress", action="store_true", help="Show runtime progress")
    p.add_argument("--progress-every", type=int, default=5000, help="Progress batch size")

    p.add_argument("--out-dir", type=str, default="outputs")
    return p


def _parse_g_values(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def print_result(title: str, result):
    print(f"\n=== {title} ===")
    for k, v in result.to_dict().items():
        if isinstance(v, float):
            print(f"{k}: {v:.6f}")
        else:
            print(f"{k}: {v}")


def compare_and_conclude(results: List, similar_threshold_pct: float) -> None:
    if len(results) < 2:
        return
    baseline = results[0].expected_server_coins
    print("\n=== Strategy Difference Summary ===")
    for r in results[1:]:
        diff_pct = (r.expected_server_coins - baseline) / baseline * 100.0
        verdict = "差不多" if abs(diff_pct) < similar_threshold_pct else "有明显差异"
        print(f"vs {r.strategy_desc}: diff={diff_pct:.2f}% -> {verdict}")


def make_mc_progress(progress_enabled: bool, total: int):
    if not progress_enabled:
        return None

    if Progress is not None:
        progress = Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TextColumn("{task.fields[extra]}"),
        )
        progress.start()
        task = progress.add_task("MC", total=total, extra="")

        def cb(payload):
            done = int(payload["done"])
            extra = f" succ={int(payload['success_count'])}, p≈{payload['success_rate_est']:.4f} "
            progress.update(task, completed=done, extra=extra)
            if done >= total:
                progress.stop()

        return cb

    def cb(payload):
        print(
            f"\r[MC] {payload['percent']:.1f}% elapsed={payload['elapsed_sec']:.1f}s "
            f"eta={payload['eta_sec']:.1f}s succ={int(payload['success_count'])} "
            f"p≈{payload['success_rate_est']:.5f}",
            end="",
            flush=True,
        )
        if int(payload["done"]) >= total:
            print()

    return cb


def make_search_progress(progress_enabled: bool):
    if not progress_enabled:
        return None

    def cb(payload):
        if int(payload["phase"]) == 1:
            print(
                f"\r[Search-Coarse] {int(payload['done'])}/{int(payload['total'])} "
                f"({payload['percent']:.1f}%) topK_threshold={payload['topk_threshold']:.2f}",
                end="",
                flush=True,
            )
            if int(payload["done"]) >= int(payload["total"]):
                print()
        else:
            print(
                f"\r[Search-Fine] candidate {int(payload['done'])}/{int(payload['total'])} "
                f"({payload['percent']:.1f}%)",
                end="",
                flush=True,
            )
            if int(payload["done"]) >= int(payload["total"]):
                print()

    return cb


def main() -> None:
    args = build_parser().parse_args()

    g_values = _parse_g_values(args.G)
    env_probs = [args.probabilities] if not args.probabilities_envs else [x.strip() for x in args.probabilities_envs.split(";") if x.strip()]
    if not env_probs:
        env_probs = [""]

    cost_cfg = CostConfig()
    all_results = []

    single_strategy = ThresholdStrategy(
        a1=args.a1,
        a2=args.a2,
        a3=args.a3,
        a4=args.a4,
        require_high_attack_in_first_two=args.gate2_ge3,
    )

    for run_idx, (g, prob_text) in enumerate(itertools.product(g_values, env_probs)):
        probs = parse_probability_vector(prob_text, attr_count=26)
        sim_cfg = SimConfig(goal_score=g, mode=args.mode, restart_action=args.restart_action, probs=probs)
        mc_progress_cb = make_mc_progress(args.progress, args.N)
        single_result = monte_carlo_evaluate(
            single_strategy,
            sim_cfg,
            cost_cfg,
            n_runs=args.N,
            seed=args.seed + run_idx,
            progress=args.progress,
            progress_every=max(1, args.progress_every),
            progress_cb=mc_progress_cb,
        )
        single_dict = single_result.to_dict()
        single_dict["group_label"] = f"G={g},env={run_idx+1}"
        print_result(f"Single Strategy ({single_dict['group_label']})", single_result)
        all_results.append(single_dict)

        if args.compare_example:
            proposed = ThresholdStrategy(a1=3, a2=6, a3=8, a4=11, require_high_attack_in_first_two=False)
            mine = ThresholdStrategy(a1=0, a2=0, a3=0, a4=8, require_high_attack_in_first_two=True)

            p_res = monte_carlo_evaluate(proposed, sim_cfg, cost_cfg, n_runs=args.N, seed=args.seed + 1000 + run_idx)
            m_res = monte_carlo_evaluate(mine, sim_cfg, cost_cfg, n_runs=args.N, seed=args.seed + 2000 + run_idx)
            print_result("Compare: Proposed (3,6,8,11)", p_res)
            print_result("Compare: Mine (gate2>=3 + a4=8)", m_res)
            all_results.extend([p_res.to_dict(), m_res.to_dict()])

        if args.search:
            search_cfg = SearchConfig(
                max_threshold=args.max_threshold,
                coarse_n=args.coarse_n,
                fine_n=args.fine_n,
                keep_top_k=args.top_k,
                output_top_n=args.top_n,
                include_logic_gate=not args.disable_gate_search,
            )
            search_progress_cb = make_search_progress(args.progress)
            top_results = search_strategies(
                sim_cfg,
                cost_cfg,
                search_cfg,
                seed=args.seed,
                progress=args.progress,
                progress_every=max(1, args.progress_every // 100),
                progress_cb=search_progress_cb,
            )
            print("\n=== Top Strategies (by expected server coins) ===")
            for i, r in enumerate(top_results, start=1):
                print(f"#{i} {r.strategy_desc} -> coins={r.expected_server_coins:.2f}, diamonds={r.expected_diamonds:.3f}, tears={r.expected_tears:.3f}")
                rd = r.to_dict()
                rd["group_label"] = f"G={g},env={run_idx+1}"
                all_results.append(rd)

    # compare first three entries if they are Eval-like dict converted from same run
    if len(all_results) >= 3 and "expected_server_coins" in all_results[0]:
        class _Wrap:
            def __init__(self, d):
                self.expected_server_coins = d["expected_server_coins"]
                self.strategy_desc = d["strategy"]

        compare_and_conclude([_Wrap(x) for x in all_results[:3]], args.similar_threshold_pct)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / timestamp
    report_path = write_report(
        out_dir,
        run_config={"G": args.G, "N": args.N, "mode": args.mode, "search": args.search, "progress": args.progress},
        results=all_results,
    )
    print(f"\nReport folder: {out_dir}")
    print(f"Open in browser: {report_path}")


if __name__ == "__main__":
    main()
