from random import Random
from typing import Any, List


class RandomSource(object):
    def next_integer(self) -> int:
        return 0

    def choose(self, options: List[Any]) -> Any:
        k = self.next_integer() % len(options)
        return options[k]


class SeededRandomSource(RandomSource):
    def __init__(self, seed):
        self.r = Random()
        self.r.seed(seed)

    def next_integer(self) -> int:
        return self.r.randint(-100000, 100000)
