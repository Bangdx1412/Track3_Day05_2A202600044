"""Search client abstraction for ResearcherAgent."""

from __future__ import annotations

import json
from typing import Any
from urllib import request

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import SourceDocument


class SearchClient:
    """Provider-backed search client.

    Runtime search is intentionally live-only. Tests may inject a fake search client,
    but application code should not silently fall back to mock data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        use_provider: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.tavily_api_key
        self.use_provider = settings.use_live_providers if use_provider is None else use_provider

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query.

        Tavily is used as the live search provider. If live providers are disabled or
        `TAVILY_API_KEY` is missing, fail loudly instead of using mock data.
        """

        if not self.use_provider:
            raise LabError(
                "Live search is disabled. Set USE_LIVE_PROVIDERS=true to use Tavily."
            )
        if not self.api_key:
            raise LabError("TAVILY_API_KEY is required for live search.")

        return self._search_tavily(query, max_results)

    def _search_tavily(self, query: str, max_results: int) -> list[SourceDocument]:
        body = json.dumps(
            {"api_key": self.api_key, "query": query, "max_results": max_results}
        ).encode("utf-8")
        tavily_request = request.Request(
            "https://api.tavily.com/search",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(tavily_request, timeout=20) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return [
            SourceDocument(
                title=str(item.get("title") or "Untitled source"),
                url=item.get("url"),
                snippet=str(item.get("content") or item.get("snippet") or ""),
                metadata={"provider": "tavily", "score": item.get("score")},
            )
            for item in payload.get("results", [])[:max_results]
            if item.get("content") or item.get("snippet")
        ]
