"""Replaceable search and language-model adapters used by Phase 4."""
from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx
import keyring

from app.core.config import settings


class ProviderUnavailable(RuntimeError):
    pass


class SearchProvider(Protocol):
    def search(self, topic: str, *, limit: int = 8) -> list[dict[str, Any]]: ...


class AIProvider(Protocol):
    def generate_json(self, *, system: str, prompt: str) -> dict[str, Any]: ...


def _post_json(endpoint: str, *, headers: dict[str, str] | None, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Retry once only when the connection failed before a request could be sent."""
    for attempt in range(2):
        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise ProviderUnavailable("Provider response exceeded the 2 MB response limit.")
            data = response.json()
            if not isinstance(data, dict):
                raise ProviderUnavailable("Provider returned an unexpected response format.")
            return data
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 0:
                time.sleep(0.2)
                continue
            raise
    raise ProviderUnavailable("Provider connection failed.")


def credential(service: str) -> str:
    try:
        value = keyring.get_password("GeoChronicle", service)
    except Exception as exc:
        raise ProviderUnavailable("Windows Credential Manager is unavailable. Configure the provider credential, then retry.") from exc
    if not value:
        raise ProviderUnavailable(f"No {service} credential is stored in Windows Credential Manager.")
    return value


class TavilySearchProvider:
    def __init__(self, endpoint: str = settings.search_endpoint, timeout: float = settings.provider_timeout_seconds, get_credential=credential):
        self.endpoint, self.timeout, self.get_credential = endpoint, timeout, get_credential

    def search(self, topic: str, *, limit: int = 8) -> list[dict[str, Any]]:
        api_key = self.get_credential("tavily")
        try:
            data = _post_json(self.endpoint, headers=None, payload={"api_key": api_key, "query": topic, "max_results": min(max(limit, 1), 10), "search_depth": "advanced", "include_answer": False}, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("Search provider timed out. Check your connection and retry.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderUnavailable("Search provider rate limit reached. Wait a moment and retry.") from exc
            raise ProviderUnavailable(f"Search provider returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable("Search provider could not be reached or returned invalid data.") from exc
        rows = data.get("results", [])
        return [
            {"title": str(item.get("title", "Untitled source"))[:500], "url": str(item.get("url", ""))[:2048],
             "publisher": item.get("source"), "content": str(item.get("content", ""))[:12000], "score": item.get("score"),
             "published_date": item.get("published_date"), "author": None, "source_type": "other",
             "provenance": {"provider": "tavily", "search_query": topic}}
            for item in rows if isinstance(item, dict) and str(item.get("url", "")).startswith(("https://", "http://"))
        ]


class OpenAICompatibleProvider:
    def __init__(self, endpoint: str = settings.ai_endpoint, model: str = settings.ai_model, timeout: float = settings.provider_timeout_seconds, get_credential=credential):
        self.endpoint, self.model, self.timeout, self.get_credential = endpoint, model, timeout, get_credential

    def generate_json(self, *, system: str, prompt: str) -> dict[str, Any]:
        api_key = self.get_credential("openai")
        try:
            data = _post_json(self.endpoint, headers={"Authorization": f"Bearer {api_key}"}, payload={
                "model": self.model, "temperature": 0.2, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            }, timeout=self.timeout)
            text = data["choices"][0]["message"]["content"]
            result = json.loads(text)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("AI provider timed out. Check your connection and retry.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderUnavailable("AI provider rate limit reached. Wait a moment and retry.") from exc
            raise ProviderUnavailable(f"AI provider returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable("AI provider could not be reached or returned invalid structured data.") from exc
        if not isinstance(result, dict):
            raise ProviderUnavailable("AI provider returned an unexpected response format.")
        return result


def configured_search_provider() -> SearchProvider:
    if settings.search_provider == "tavily":
        return TavilySearchProvider()
    raise ProviderUnavailable("No supported search provider is configured. Set GEOCHRONICLE_SEARCH_PROVIDER=tavily and add its credential to Windows Credential Manager.")


def configured_ai_provider() -> AIProvider:
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleProvider()
    raise ProviderUnavailable("No supported AI provider is configured. Set GEOCHRONICLE_AI_PROVIDER=openai_compatible and add its credential to Windows Credential Manager.")
