"""Analyst agent skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`.

        Extract key claims, compare viewpoints, and flag weak evidence.
        """

        if not state.research_notes:
            state.analysis_notes = (
                "Analysis notes:\n"
                "- Evidence is missing; answer should be framed as a cautious hypothesis.\n"
                "- Next best action is to run the researcher before producing a final answer."
            )
        else:
            claims = [
                f"- Source {index} supports: {source.snippet}"
                for index, source in enumerate(state.sources, start=1)
            ]
            gaps = []
            if len(state.sources) < 2:
                gaps.append("- Evidence breadth is weak because fewer than two sources were found.")
            if any(source.url is None for source in state.sources):
                gaps.append(
                    "- At least one source has no URL and should be treated as context only."
                )
            if not gaps:
                gaps.append(
                    "- Evidence is adequate for a concise synthesis; still avoid overclaiming."
                )

            state.analysis_notes = "\n".join(
                [
                    "Analysis notes:",
                    "Key claims:",
                    *claims,
                    "Risks and gaps:",
                    *gaps,
                    "Recommended synthesis:",
                    (
                        "- Explain the answer directly, cite source-indexed evidence, and separate "
                        "confirmed points from implementation advice."
                    ),
                ]
            )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=state.analysis_notes,
                metadata={"source_count": len(state.sources)},
            )
        )
        state.add_trace_event("analyst.notes", {"has_analysis": bool(state.analysis_notes)})
        return state
