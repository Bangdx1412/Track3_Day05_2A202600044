"""Researcher agent skeleton."""

from typing import Protocol

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.search_client import SearchClient


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]: ...


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(self, search_client: SearchProvider | None = None) -> None:
        self.search_client = search_client or SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`.

        The researcher deduplicates by URL/title and keeps notes source-indexed so the
        writer can cite them later.
        """

        sources = self.search_client.search(state.request.query, state.request.max_sources)
        state.sources = _dedupe_sources([*state.sources, *sources])[: state.request.max_sources]
        state.research_notes = _render_research_notes(state.sources)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=state.research_notes,
                metadata={"source_count": len(state.sources)},
            )
        )
        state.add_trace_event(
            "researcher.sources",
            {
                "source_count": len(state.sources),
                "titles": [source.title for source in state.sources],
            },
        )
        return state


def _dedupe_sources(sources: list[SourceDocument]) -> list[SourceDocument]:
    seen: set[str] = set()
    unique: list[SourceDocument] = []
    for source in sources:
        key = (source.url or source.title).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _render_research_notes(sources: list[SourceDocument]) -> str:
    if not sources:
        return "No sources were found. Proceed with caveats and state uncertainty clearly."

    lines = ["Research notes:"]
    for index, source in enumerate(sources, start=1):
        citation = f"[{index}]"
        url = f" ({source.url})" if source.url else ""
        lines.append(f"{citation} {source.title}{url}: {source.snippet}")
    return "\n".join(lines)
