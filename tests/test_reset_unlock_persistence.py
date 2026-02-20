import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from simulator import CostConfig, SimConfig, monte_carlo_evaluate
from strategy import ThresholdStrategy


def test_reset_mode_persists_slot_unlocks_and_consumables_stay_constant():
    strategy = ThresholdStrategy(a1=0, a2=0, a3=0, a4=0, require_high_attack_in_first_two=False)
    sim_cfg = SimConfig(
        goal_score=16,
        mode="mixed",
        restart_action="reset",
        persist_slot_unlocks_on_reset=True,
    )
    out = monte_carlo_evaluate(strategy, sim_cfg, CostConfig(), n_runs=200, seed=123)

    # Never discard => one item only; slot5/slot6 unlock once each on that item.
    assert abs(out.expected_diamonds - 7.0) < 1e-9
    assert abs(out.expected_tears - 2.0) < 1e-9
    assert abs(out.diamond_coins - 350.0) < 1e-9
    assert abs(out.tear_coins - 20000.0) < 1e-9


if __name__ == "__main__":
    test_reset_mode_persists_slot_unlocks_and_consumables_stay_constant()
    print("ok")
