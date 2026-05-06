"""Supervisor / router skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self, max_iterations: int | None = None) -> None:
        self.max_iterations = max_iterations or get_settings().max_iterations

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route.

        Policy:
        - gather sources/research notes first
        - analyze notes second
        - write the final answer third
        - stop when final answer exists or max iterations is reached
        """

        if state.final_answer:
            next_route = "done"
        elif state.iteration >= self.max_iterations:
            next_route = "writer" if state.research_notes or state.analysis_notes else "done"
            state.errors.append("Max iterations reached; using best available result.")
        elif not state.sources or not state.research_notes:
            next_route = "researcher"
        elif not state.analysis_notes:
            next_route = "analyst"
        else:
            next_route = "writer"

        state.record_route(next_route)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.SUPERVISOR,
                content=f"Routed to {next_route}.",
                metadata={"iteration": state.iteration},
            )
        )
        state.add_trace_event(
            "supervisor.route",
            {"next": next_route, "iteration": state.iteration},
        )
        return state
