from collections.abc import Iterator

import pytest

from multi_agent_research_lab.core.config import get_settings


@pytest.fixture(autouse=True)
def disable_live_tracing_for_tests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
