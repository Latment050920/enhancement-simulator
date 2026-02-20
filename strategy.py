from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

ATTACK_TYPES = {"melee", "ranged", "physical", "true"}


@dataclass(frozen=True)
class ThresholdStrategy:
    """Stage-wise threshold strategy with optional logic gate."""

    a1: int = 0
    a2: int = 0
    a3: int = 0
    a4: int = 0
    require_high_attack_in_first_two: bool = False

    def thresholds(self) -> Tuple[int, int, int, int]:
        return self.a1, self.a2, self.a3, self.a4

    def checkpoint_threshold(self, slot: int) -> int:
        if slot == 1:
            return self.a1
        if slot == 2:
            return self.a2
        if slot == 3:
            return self.a3
        if slot == 4:
            return self.a4
        return -10**9

    def describe(self) -> str:
        gate = "gate2>=3:on" if self.require_high_attack_in_first_two else "gate2>=3:off"
        return f"a=[{self.a1},{self.a2},{self.a3},{self.a4}],{gate}"


@dataclass
class ItemState:
    melee: int = 0
    ranged: int = 0
    physical: int = 0
    true: int = 0
    high_attack_in_first_two: bool = False

    def add_roll(self, slot: int, attr_name: str, value: int) -> None:
        if attr_name == "melee":
            self.melee += value
        elif attr_name == "ranged":
            self.ranged += value
        elif attr_name == "physical":
            self.physical += value
        elif attr_name == "true":
            self.true += value

        if slot <= 2 and attr_name in ATTACK_TYPES and value >= 3:
            self.high_attack_in_first_two = True

    @property
    def score(self) -> int:
        return max(self.melee, self.ranged) + self.physical + self.true

    def reset(self) -> None:
        self.melee = 0
        self.ranged = 0
        self.physical = 0
        self.true = 0
        self.high_attack_in_first_two = False
