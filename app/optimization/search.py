from __future__ import annotations

import random
from typing import Any

from app.optimization.parameter_space import ParameterSpace


class GridSearchOptimizer:
    def generate(self, parameter_space: ParameterSpace) -> tuple[dict[str, Any], ...]:
        return parameter_space.combinations()


class RandomSearchOptimizer:
    def __init__(self, *, seed: int, max_iterations: int) -> None:
        if max_iterations <= 0:
            raise ValueError("max_iterations debe ser positivo.")
        self.seed = seed
        self.max_iterations = max_iterations

    def generate(self, parameter_space: ParameterSpace) -> tuple[dict[str, Any], ...]:
        combinations = list(parameter_space.combinations())
        rng = random.Random(self.seed)
        rng.shuffle(combinations)
        return tuple(combinations[: self.max_iterations])
