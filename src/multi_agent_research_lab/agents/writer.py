"""Writer agent skeleton."""

from typing import Protocol

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class CompletionProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse: ...


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self, llm_client: CompletionProvider | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`.

        Synthesize a clear response with source references.
        """

        state.final_answer, metadata = self._write_answer(state)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=state.final_answer,
                metadata={"source_count": len(state.sources), **metadata},
            )
        )
        state.add_trace_event("writer.final_answer", {"length": len(state.final_answer)})
        return state

    def _write_answer(self, state: ResearchState) -> tuple[str, dict[str, int | float | None]]:
        source_lines = [
            f"[{index}] {source.title}: {source.snippet}"
            for index, source in enumerate(state.sources, start=1)
        ]
        user_prompt = "\n".join(
            [
                f"Question: {state.request.query}",
                f"Audience: {state.request.audience}",
                state.research_notes or "Research notes: none",
                state.analysis_notes or "Analysis notes: none",
                "Sources:",
                *source_lines,
            ]
        )
        draft = self.llm_client.complete(
            system_prompt=(
                "Write a concise research answer. Use numbered citations like [1] when "
                "sources are available. Be explicit about uncertainty."
            ),
            user_prompt=user_prompt,
        )

        citations = " ".join(f"[{index}]" for index in range(1, len(state.sources) + 1))
        evidence_summary = "\n".join(
            f"- [{index}] {source.title}: {source.snippet}"
            for index, source in enumerate(state.sources, start=1)
        )
        if not evidence_summary:
            evidence_summary = "- No external sources available; treat the answer as a draft."

        answer = "\n".join(
            [
                f"Answer for: {state.request.query}",
                "",
                draft.content,
                "",
                "Evidence used:",
                evidence_summary,
                "",
                f"Citation coverage: {citations or 'no citations available'}",
            ]
        ).strip()
        metadata: dict[str, int | float | None] = {
            "input_tokens": draft.input_tokens,
            "output_tokens": draft.output_tokens,
            "cost_usd": draft.cost_usd,
        }
        return answer, metadata
