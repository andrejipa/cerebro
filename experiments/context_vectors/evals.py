from __future__ import annotations

from dataclasses import dataclass

from .index import VectorIndex, query_index


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    expected_path: str


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    hits_at_1: int
    hits_at_3: int
    missing: tuple[EvaluationCase, ...]

    @property
    def recall_at_1(self) -> float:
        return 0.0 if self.total == 0 else self.hits_at_1 / self.total

    @property
    def recall_at_3(self) -> float:
        return 0.0 if self.total == 0 else self.hits_at_3 / self.total


def evaluate_queries(index: VectorIndex, cases: list[EvaluationCase] | tuple[EvaluationCase, ...]) -> EvaluationResult:
    hits_at_1 = 0
    hits_at_3 = 0
    missing: list[EvaluationCase] = []

    for case in cases:
        hits = query_index(index, case.query, limit=3)
        paths = [hit.relative_path for hit in hits]
        if paths and paths[0] == case.expected_path:
            hits_at_1 += 1
        if case.expected_path in paths:
            hits_at_3 += 1
        else:
            missing.append(case)

    return EvaluationResult(
        total=len(cases),
        hits_at_1=hits_at_1,
        hits_at_3=hits_at_3,
        missing=tuple(missing),
    )
