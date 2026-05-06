"""Command-line entrypoint for the lab starter."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient
from multi_agent_research_lab.services.storage import LocalArtifactStore

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline."""

    _init()
    state = _run_baseline(query)
    console.print(Panel.fit(state.final_answer or "", title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow."""

    _init()
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    result = workflow.run(state)
    console.print(result.model_dump_json(indent=2))


@app.command()
def benchmark(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Report path relative to reports/"),
    ] = "benchmark_report.md",
) -> None:
    """Benchmark baseline vs multi-agent and write a markdown report."""

    _init()
    _, baseline_metrics = run_benchmark("baseline", query, _run_baseline)
    _, multi_metrics = run_benchmark("multi-agent", query, _run_multi_agent)
    report = render_markdown_report([baseline_metrics, multi_metrics])
    path = LocalArtifactStore().write_text(output, report)
    console.print(Panel.fit(str(path), title="Benchmark Report Written"))


def _run_multi_agent(query: str) -> ResearchState:
    return MultiAgentWorkflow().run(ResearchState(request=ResearchQuery(query=query)))


def _run_baseline(query: str) -> ResearchState:
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    sources = SearchClient().search(request.query, request.max_sources)
    state.sources = sources
    source_lines = [
        f"[{index}] {source.title}: {source.snippet}"
        for index, source in enumerate(sources, start=1)
    ]
    response = LLMClient().complete(
        system_prompt=(
            "You are a single research agent. Answer directly, cite sources when available, "
            "and mention uncertainty."
        ),
        user_prompt="\n".join([f"Question: {query}", "Sources:", *source_lines]),
    )
    evidence = "\n".join(source_lines) if source_lines else "No sources available."
    state.final_answer = "\n".join(
        [
            f"Answer for: {query}",
            "",
            response.content,
            "",
            "Evidence used:",
            evidence,
        ]
    )
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=state.final_answer,
            metadata={
                "mode": "single-agent",
                "source_count": len(sources),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )
    )
    state.add_trace_event("baseline.complete", {"source_count": len(sources)})
    return state


if __name__ == "__main__":
    app()
