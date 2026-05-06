"""Multi-agent workflow orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass

from multi_agent_research_lab.agents import (
    AnalystAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Keep orchestration here; keep agent internals in `agents/`.
    """

    def __init__(
        self,
        supervisor: SupervisorAgent | None = None,
        agents: Mapping[str, BaseAgent] | None = None,
        max_iterations: int | None = None,
    ) -> None:
        settings = get_settings()
        self.max_iterations = max_iterations or settings.max_iterations
        self.supervisor = supervisor or SupervisorAgent(max_iterations=self.max_iterations)
        self.agents: dict[str, BaseAgent] = dict(
            agents
            or {
                "researcher": ResearcherAgent(),
                "analyst": AnalystAgent(),
                "writer": WriterAgent(),
            }
        )
        self._graph: _SequentialGraph | None = None

    def build(self) -> object:
        """Create the workflow graph.

        A real LangGraph implementation can replace this adapter without changing agent
        contracts. The sequential graph mirrors the target nodes and conditional routing,
        while staying dependency-light for the base lab install.
        """

        self._graph = _SequentialGraph(
            supervisor=self.supervisor,
            agents=self.agents,
            max_supervisor_steps=self.max_iterations + 4,
        )
        return self._graph

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return final state."""

        graph = self._graph or self.build()
        if not isinstance(graph, _SequentialGraph):
            raise AgentExecutionError("Unsupported workflow graph implementation.")
        with trace_span(
            "workflow.multi_agent",
            {"query": state.request.query, "max_sources": state.request.max_sources},
        ) as span:
            result = graph.invoke(state)
            span["outputs"] = {
                "route_history": result.route_history,
                "source_count": len(result.sources),
                "has_final_answer": bool(result.final_answer),
                "error_count": len(result.errors),
            }
        result.add_trace_event("span.workflow", span)
        return result


@dataclass
class _SequentialGraph:
    supervisor: SupervisorAgent
    agents: Mapping[str, BaseAgent]
    max_supervisor_steps: int

    def invoke(self, state: ResearchState) -> ResearchState:
        for _ in range(self.max_supervisor_steps):
            with trace_span("agent.supervisor", {"iteration": state.iteration}) as span:
                state = self.supervisor.run(state)
            state.add_trace_event("span.supervisor", span)

            route = state.route_history[-1]
            if route == "done":
                return state

            agent = self.agents.get(route)
            if agent is None:
                state.errors.append(f"Unknown route: {route}")
                state.record_route("done")
                return state

            with trace_span(f"agent.{route}", {"iteration": state.iteration}) as span:
                state = agent.run(state)
            state.add_trace_event(f"span.{route}", span)

        state.errors.append("Workflow stopped by hard iteration guard.")
        if not state.final_answer and "writer" in self.agents:
            state = self.agents["writer"].run(state)
        return state
