"""Optional critic agent skeleton for bonus work."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append findings.

        The critic is deliberately lightweight: it checks whether the writer cited available
        sources and records gaps without blocking the workflow.
        """

        findings: list[str] = []
        if not state.final_answer:
            findings.append("Final answer is missing.")
        if state.sources and state.final_answer:
            missing = [
                str(index)
                for index in range(1, len(state.sources) + 1)
                if f"[{index}]" not in state.final_answer
            ]
            if missing:
                findings.append(f"Missing citations for source indexes: {', '.join(missing)}.")
        if not findings:
            findings.append("Citation coverage and final-answer presence look acceptable.")

        content = "\n".join(f"- {finding}" for finding in findings)
        state.agent_results.append(
            AgentResult(agent=AgentName.CRITIC, content=content, metadata={"findings": findings})
        )
        state.add_trace_event("critic.findings", {"findings": findings})
        return state
