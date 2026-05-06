"""Tracing hooks.

This file intentionally avoids binding to one provider. Students can plug in LangSmith,
Langfuse, OpenTelemetry, or simple JSON traces.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Literal

from multi_agent_research_lab.core.config import get_settings


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Provider-neutral span with optional LangSmith upload.

    The yielded dictionary is still recorded locally in `ResearchState.trace`. When
    `LANGSMITH_API_KEY` is configured, the same span is also sent to LangSmith.
    """

    started = perf_counter()
    span: dict[str, Any] = {"name": name, "attributes": attributes or {}, "duration_seconds": None}
    langsmith_context = _langsmith_trace_context(name, span["attributes"])
    if langsmith_context is None:
        try:
            yield span
        finally:
            span["duration_seconds"] = perf_counter() - started
        return

    with langsmith_context as run:
        try:
            yield span
        finally:
            span["duration_seconds"] = perf_counter() - started
            outputs = span.get(
                "outputs",
                {
                    "duration_seconds": span["duration_seconds"],
                    "attributes": span["attributes"],
                },
            )
            run.end(outputs=outputs)


def _langsmith_trace_context(name: str, attributes: dict[str, Any]) -> Any | None:
    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return None

    try:
        from langsmith import Client
        from langsmith.run_helpers import trace, tracing_context
    except ImportError:
        return None

    client = Client(api_key=settings.langsmith_api_key, auto_batch_tracing=False)

    @contextmanager
    def _enabled_trace() -> Iterator[Any]:
        with tracing_context(
            enabled=True,
            project_name=settings.langsmith_project,
            client=client,
            metadata={"app_env": settings.app_env},
        ), trace(
            name,
            run_type=_run_type_for_span(name),
            inputs={"attributes": attributes},
            project_name=settings.langsmith_project,
            client=client,
            metadata={"app_env": settings.app_env},
        ) as run:
            yield run
        client.flush()

    return _enabled_trace()


def _run_type_for_span(
    name: str,
) -> Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]:
    if name.endswith("writer") or name.endswith("llm"):
        return "llm"
    if name.endswith("researcher") or name.endswith("search"):
        return "tool"
    return "chain"
