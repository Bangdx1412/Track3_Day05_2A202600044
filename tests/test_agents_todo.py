from multi_agent_research_lab.agents import (
    AnalystAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.services.llm_client import LLMResponse


class FakeSearchClient:
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        return [
            SourceDocument(
                title="Fake source for tests",
                url="https://example.com/test",
                snippet=f"Test evidence for: {query}",
                metadata={"provider": "test"},
            )
        ][:max_results]


class FakeLLMClient:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(
            content="Fake cited answer for tests. [1]",
            input_tokens=10,
            output_tokens=6,
            cost_usd=0.000001,
        )


def test_supervisor_routes_to_researcher_first() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = SupervisorAgent().run(state)
    assert result.route_history == ["researcher"]


def test_workflow_produces_final_answer() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = MultiAgentWorkflow(
        agents={
            "researcher": ResearcherAgent(search_client=FakeSearchClient()),
            "analyst": AnalystAgent(),
            "writer": WriterAgent(llm_client=FakeLLMClient()),
        }
    ).run(state)
    assert result.final_answer
    assert result.research_notes
    assert result.analysis_notes
    assert result.route_history[-1] == "done"
