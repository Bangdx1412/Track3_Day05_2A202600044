"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
The default implementation is intentionally usable without network access: it calls OpenAI
when an API key and SDK are available, otherwise it returns a deterministic extractive
completion that keeps the lab runnable in CI and classrooms.
"""

import logging
from dataclasses import dataclass
from textwrap import shorten

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Provider-agnostic LLM client with an offline fallback."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        use_provider: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.timeout_seconds = timeout_seconds or settings.timeout_seconds
        self.use_provider = settings.use_live_providers if use_provider is None else use_provider

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion.

        The method keeps retry, timeout, and token/cost accounting outside agents. If the
        provider is not configured, it produces a short deterministic response so the rest
        of the application can still be developed and benchmarked.
        """

        if self.api_key and self.use_provider:
            try:
                return self._complete_openai(system_prompt, user_prompt)
            except Exception as exc:  # pragma: no cover - depends on optional SDK/network.
                logger.warning("OpenAI completion failed; using fallback: %s", exc)

        return self._complete_fallback(system_prompt, user_prompt)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def _complete_openai(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError("openai package is not installed") from exc

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        return LLMResponse(
            content=content.strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_estimate_cost_usd(self.model, input_tokens, output_tokens),
        )

    def _complete_fallback(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        question = _extract_field(user_prompt, "Question")
        sources = _extract_source_lines(user_prompt)
        if sources:
            evidence = " ".join(
                f"{snippet} [{index}]" for index, snippet in sources[:3] if snippet
            )
            content = (
                f"For '{question or 'the requested topic'}', the strongest supported "
                f"synthesis is: {evidence} Use this as a grounded draft and avoid claims "
                "that are not backed by the listed evidence."
            )
        else:
            sentences = _split_sentences(user_prompt)
            selected = (
                sentences[:3] if sentences else [shorten(prompt, width=300, placeholder="...")]
            )
            content = " ".join(selected).strip()
        if not content:
            content = "No completion could be generated from the provided prompt."

        input_tokens = _estimate_tokens(prompt)
        output_tokens = _estimate_tokens(content)
        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_estimate_cost_usd(self.model, input_tokens, output_tokens),
        )


def _split_sentences(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(normalized):
        if char in ".!?":
            sentence = normalized[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    tail = normalized[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _extract_field(text: str, field_name: str) -> str | None:
    prefix = f"{field_name}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _extract_source_lines(text: str) -> list[tuple[int, str]]:
    sources: list[tuple[int, str]] = []
    seen: set[int] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("[") or "]" not in stripped:
            continue
        marker, _, rest = stripped.partition("]")
        index_text = marker.removeprefix("[")
        if not index_text.isdigit() or int(index_text) in seen:
            continue
        seen.add(int(index_text))
        _, separator, snippet = rest.rpartition(": ")
        sources.append((int(index_text), snippet.strip() if separator else rest.strip()))
    return sources


def _estimate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None

    # Conservative public-list-price placeholders for common small lab models.
    price_per_million = {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (5.00, 15.00),
    }
    input_price, output_price = price_per_million.get(model, (0.0, 0.0))
    return (input_tokens / 1_000_000 * input_price) + (
        output_tokens / 1_000_000 * output_price
    )
