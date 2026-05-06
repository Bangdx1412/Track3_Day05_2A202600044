"""Benchmark skeleton for single-agent vs multi-agent."""

from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import AgentName, BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

Runner = Callable[[str], ResearchState]


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency and derive lightweight quality/cost metrics."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started
    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=_sum_cost(state),
        quality_score=_score_quality(state),
        notes=_notes(state),
    )
    return state, metrics


def _sum_cost(state: ResearchState) -> float:
    total = 0.0
    for result in state.agent_results:
        cost = result.metadata.get("cost_usd")
        if isinstance(cost, int | float):
            total += float(cost)
    return total


def _score_quality(state: ResearchState) -> float:
    score = 0.0
    if state.final_answer:
        score += 3.0
    if state.sources:
        score += min(2.0, len(state.sources) * 0.5)
    if state.research_notes:
        score += 1.5
    if state.analysis_notes:
        score += 1.5
    if state.final_answer and state.sources:
        cited = sum(
            1
            for index in range(1, len(state.sources) + 1)
            if f"[{index}]" in state.final_answer
        )
        score += min(2.0, 2.0 * cited / len(state.sources))
    if state.errors:
        score -= min(2.0, len(state.errors) * 0.5)
    return max(0.0, min(10.0, score))


def _notes(state: ResearchState) -> str:
    route_summary = " > ".join(state.route_history) if state.route_history else "không có route"
    writer_runs = sum(1 for result in state.agent_results if result.agent == AgentName.WRITER)
    error_note = f"; lỗi={len(state.errors)}" if state.errors else ""
    return (
        f"luồng={route_summary}; nguồn={len(state.sources)}; "
        f"writer_runs={writer_runs}{error_note}"
    )
