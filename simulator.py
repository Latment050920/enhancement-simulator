from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from strategy import ItemState, ThresholdStrategy

DEFAULT_ATTRS: List[str] = [
    "melee",
    "ranged",
    "physical",
    "true",
] + [f"other_{i}" for i in range(1, 23)]

ProgressFn = Callable[[Dict[str, float]], None]


@dataclass(frozen=True)
class CostConfig:
    enhance_coin: int = 5000
    clear_coin: int = 2000
    diamonds_per_item: int = 7
    diamond_price: int = 50
    tears_price: int = 10000


@dataclass(frozen=True)
class SimConfig:
    goal_score: int
    mode: str = "discard"  # discard | mixed
    restart_action: str = "auto"  # auto | discard | reset
    attrs: Optional[List[str]] = None
    probs: Optional[List[float]] = None


@dataclass
class EvalResult:
    strategy_desc: str
    goal_score: int
    expected_server_coins: float
    expected_diamonds: float
    expected_tears: float
    success_rate: float
    expected_attempts: float
    std_err_coins: float
    ci95_coins_low: float
    ci95_coins_high: float
    enhance_coins: float
    clear_coins: float
    diamond_coins: float
    tear_coins: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "strategy": self.strategy_desc,
            "G": self.goal_score,
            "expected_server_coins": self.expected_server_coins,
            "expected_diamonds": self.expected_diamonds,
            "expected_tears": self.expected_tears,
            "success_rate": self.success_rate,
            "expected_attempts": self.expected_attempts,
            "std_err_coins": self.std_err_coins,
            "ci95_coins_low": self.ci95_coins_low,
            "ci95_coins_high": self.ci95_coins_high,
            "enhance_coins": self.enhance_coins,
            "clear_coins": self.clear_coins,
            "diamond_coins": self.diamond_coins,
            "tear_coins": self.tear_coins,
        }


def _resolve_restart_action(sim_cfg: SimConfig, cost_cfg: CostConfig) -> str:
    if sim_cfg.mode == "discard":
        return "discard"
    if sim_cfg.restart_action in {"discard", "reset"}:
        return sim_cfg.restart_action
    discard_coin = cost_cfg.diamonds_per_item * cost_cfg.diamond_price
    reset_coin = cost_cfg.clear_coin
    return "discard" if discard_coin <= reset_coin else "reset"


def _draw_attr_and_value(rng: random.Random, attrs: List[str], probs: List[float]) -> tuple[str, int]:
    attr = rng.choices(attrs, weights=probs, k=1)[0]
    value = rng.randint(1, 5) if attr in {"melee", "ranged", "physical", "true"} else 0
    return attr, value


def simulate_one_success(
    strategy: ThresholdStrategy,
    sim_cfg: SimConfig,
    cost_cfg: CostConfig,
    rng: random.Random,
) -> Dict[str, float]:
    attrs = sim_cfg.attrs or DEFAULT_ATTRS
    probs = sim_cfg.probs if sim_cfg.probs is not None else [1.0 / len(attrs)] * len(attrs)
    restart_action = _resolve_restart_action(sim_cfg, cost_cfg)

    coins = 0.0
    diamonds = 0.0
    tears = 0.0
    attempts = 0
    enhance_coins = 0.0
    clear_coins = 0.0
    diamond_coins = 0.0
    tear_coins = 0.0

    state = ItemState()

    while True:
        attempts += 1
        diamonds += cost_cfg.diamonds_per_item
        dcoin = cost_cfg.diamonds_per_item * cost_cfg.diamond_price
        coins += dcoin
        diamond_coins += dcoin
        state.reset()

        restart = False
        for slot in range(1, 7):
            coins += cost_cfg.enhance_coin
            enhance_coins += cost_cfg.enhance_coin
            if slot >= 5:
                tears += 1
                coins += cost_cfg.tears_price
                tear_coins += cost_cfg.tears_price

            attr, value = _draw_attr_and_value(rng, attrs, probs)
            state.add_roll(slot, attr, value)

            if slot <= 4:
                threshold = strategy.checkpoint_threshold(slot)
                if state.score < threshold:
                    restart = True
                if slot == 2 and strategy.require_high_attack_in_first_two and not state.high_attack_in_first_two:
                    restart = True
                if slot == 4 and state.score < strategy.a4:
                    restart = True

                if restart:
                    break

        if not restart and state.score >= sim_cfg.goal_score:
            return {
                "coins": coins,
                "diamonds": diamonds,
                "tears": tears,
                "attempts": attempts,
                "enhance_coins": enhance_coins,
                "clear_coins": clear_coins,
                "diamond_coins": diamond_coins,
                "tear_coins": tear_coins,
            }

        if restart_action == "reset":
            coins += cost_cfg.clear_coin
            clear_coins += cost_cfg.clear_coin


def monte_carlo_evaluate(
    strategy: ThresholdStrategy,
    sim_cfg: SimConfig,
    cost_cfg: CostConfig,
    n_runs: int,
    seed: int = 42,
    progress: bool = False,
    progress_every: int = 5000,
    progress_cb: Optional[ProgressFn] = None,
) -> EvalResult:
    rng = random.Random(seed)

    coins: List[float] = []
    diamonds: List[float] = []
    tears: List[float] = []
    attempts: List[float] = []
    enhance_all: List[float] = []
    clear_all: List[float] = []
    diamond_all: List[float] = []
    tear_all: List[float] = []
    start = time.time()

    for i in range(n_runs):
        out = simulate_one_success(strategy, sim_cfg, cost_cfg, rng)
        coins.append(out["coins"])
        diamonds.append(out["diamonds"])
        tears.append(out["tears"])
        attempts.append(out["attempts"])
        enhance_all.append(out["enhance_coins"])
        clear_all.append(out["clear_coins"])
        diamond_all.append(out["diamond_coins"])
        tear_all.append(out["tear_coins"])

        done = i + 1
        if progress and (done % progress_every == 0 or done == n_runs):
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0.0
            eta = (n_runs - done) / rate if rate > 0 else 0.0
            est_success = statistics.fmean([1.0 / x for x in attempts])
            payload = {
                "done": float(done),
                "total": float(n_runs),
                "percent": done / n_runs * 100.0,
                "elapsed_sec": elapsed,
                "eta_sec": eta,
                "success_count": float(done),
                "success_rate_est": est_success,
            }
            if progress_cb:
                progress_cb(payload)

    expected_coins = statistics.fmean(coins)
    std_err = statistics.stdev(coins) / (n_runs ** 0.5) if n_runs > 1 else 0.0
    ci_delta = 1.96 * std_err

    return EvalResult(
        strategy_desc=strategy.describe(),
        goal_score=sim_cfg.goal_score,
        expected_server_coins=expected_coins,
        expected_diamonds=statistics.fmean(diamonds),
        expected_tears=statistics.fmean(tears),
        success_rate=statistics.fmean([1.0 / x for x in attempts]),
        expected_attempts=statistics.fmean(attempts),
        std_err_coins=std_err,
        ci95_coins_low=expected_coins - ci_delta,
        ci95_coins_high=expected_coins + ci_delta,
        enhance_coins=statistics.fmean(enhance_all),
        clear_coins=statistics.fmean(clear_all),
        diamond_coins=statistics.fmean(diamond_all),
        tear_coins=statistics.fmean(tear_all),
    )


def parse_probability_vector(text: Optional[str], attr_count: int) -> Optional[List[float]]:
    if not text:
        return None
    parts = [float(x.strip()) for x in text.split(",") if x.strip()]
    if len(parts) != attr_count:
        raise ValueError(f"Probability vector must contain {attr_count} values, got {len(parts)}")
    if any(x < 0 for x in parts):
        raise ValueError("Probabilities must be non-negative")
    s = sum(parts)
    if s <= 0:
        raise ValueError("Probability sum must be > 0")
    return [x / s for x in parts]
