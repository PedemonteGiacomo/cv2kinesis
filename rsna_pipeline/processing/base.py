from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Processor(ABC):
    """Abstract interface for image processing algorithms."""

    ALGO_ID = "base"

    @abstractmethod
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        """Run the algorithm and return a result dictionary."""

    @staticmethod
    def factory(algo_id: str):
        """Return the correct Processor instance for the given ID."""
        for cls in Processor.__subclasses__():
            if cls.ALGO_ID == algo_id:
                return cls()
        raise ValueError(f"Algoritmo '{algo_id}' non registrato.")
