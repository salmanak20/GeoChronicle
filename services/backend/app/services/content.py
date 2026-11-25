from __future__ import annotations

import re
from typing import Any

from app.models import Claim, ClaimSource, ResearchSession, ResearchSource, ScriptSection
from app.services.providers import AIProvider, SearchProvider


class ResearchOrchestrator:
    def __init__(self, search: SearchProvider, ai: AIProvider):
        self.search, self.ai = search, ai

    def research(self, topic: str, configuration: dict[str, Any]) -> dict[str, Any]:
        results = self.search.search(topic, limit=configuration.get("source_limit", 8))
        if not results:
            raise ValueError("Search provider returned no usable sources; no research was saved.")
        # Canonicalize URLs before prompting or persisting, preserving provenance per result.
        seen: set[str] = set()
        sources = []
        for result in results:
            url = result["url"].split("#", 1)[0].rstrip("/")
            if url and url not in seen:
                seen.add(url)
                result["url"] = url
                sources.append(result)
        evidence = [{"url": row["url"], "title": row["title"], "publisher": row.get("publisher"), "content": row.get("content", "")[:6000]} for row in sources]
        extracted = self.ai.generate_json(
            system="Extract concise, traceable research claims. Use only the supplied source excerpts. Return JSON with overview (string), claims (array of objects with text, category fact|interpretation|estimate|opinion, source_urls array, supporting_source_urls array, contradicting_source_urls array, evidence string), and perspectives (array of strings). Include a source URL in the supporting or contradicting list only when its supplied excerpt provides that evidence; otherwise leave the claim unlinked. Do not invent citations, source metadata, dates, or facts. If evidence is missing, omit the claim.",
            prompt=f"Topic: {topic}\nResearch settings: {configuration}\nSource excerpts (unverified search results): {evidence}",
        )
        claims = []
        for item in extracted.get("claims", []):
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                continue
            urls = lambda key: [url for url in item.get(key, []) if isinstance(url, str)] if isinstance(item.get(key, []), list) else []
            claims.append({"text": str(item["text"])[:4000], "category": item.get("category", "fact"), "source_urls": urls("source_urls"), "supporting_source_urls": urls("supporting_source_urls"), "contradicting_source_urls": urls("contradicting_source_urls"), "evidence": str(item.get("evidence", ""))[:4000]})
        perspectives = extracted.get("perspectives", [])
        return {"sources": sources, "claims": claims, "overview": str(extracted.get("overview", ""))[:12000], "perspectives": [str(x)[:2000] for x in perspectives[:30] if isinstance(x, (str, int, float))] if isinstance(perspectives, list) else []}


def persist_research(session: ResearchSession, output: dict[str, Any]) -> None:
    by_url: dict[str, ResearchSource] = {}
    for item in output["sources"]:
        url = item["url"]
        if url in by_url:
            continue
        source = ResearchSource(session_id=session.id, title=item["title"], url=url, publisher=item.get("publisher"), author=item.get("author"),
            publication_date=item.get("published_date"), source_type=item.get("source_type", "other"), content=item.get("content"),
            summary=item.get("content"), provenance=item.get("provenance", {}))
        session.sources.append(source)
        by_url[url] = source
    for item in output["claims"]:
        category = item.get("category")
        if category not in {"fact", "interpretation", "estimate", "opinion"}:
            category = "fact"
        claim = Claim(session_id=session.id, text=item["text"], category=category, verification_status="unverified")
        session.claims.append(claim)
        relevant_urls = item.get("source_urls", []) if isinstance(item.get("source_urls", []), list) else []
        supporting_urls = item.get("supporting_source_urls", []) if isinstance(item.get("supporting_source_urls", []), list) else []
        contradicting_urls = item.get("contradicting_source_urls", []) if isinstance(item.get("contradicting_source_urls", []), list) else []
        source_urls = set(relevant_urls) | set(supporting_urls) | set(contradicting_urls)
        for url in source_urls:
            source = by_url.get(url)
            if source:
                relation = "contradicting" if url in contradicting_urls else "supporting" if url in supporting_urls else "relevant"
                claim.source_links.append(ClaimSource(source=source, relationship_type=relation, evidence=item.get("evidence") or None))


SECTION_ORDER = [
    ("hook", "Hook"), ("introduction", "Introduction"), ("historical_background", "Historical background"),
    ("main_developments", "Main developments"), ("turning_points", "Key turning points"),
    ("geopolitical_implications", "Geopolitical implications"), ("conclusion", "Conclusion"),
]


def clean_script_sections(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("sections", {})
    output = []
    for position, (key, title) in enumerate(SECTION_ORDER):
        content = raw.get(key, "") if isinstance(raw, dict) else ""
        if isinstance(content, str):
            output.append({"section_key": key, "title": title, "content": content[:12000], "position": position})
    return output


def segment_narration(text: str) -> list[dict[str, str | int]]:
    """Return sentence text and its paragraph index, retaining punctuation and order."""
    output = []
    for paragraph_number, paragraph in enumerate(re.split(r"\n+", text), start=1):
        sentences = re.findall(r"[^.!?]+(?:[.!?]+[\"'’”)]*)?", paragraph)
        output.extend({"paragraph_number": paragraph_number, "text": sentence.strip()} for sentence in sentences if sentence.strip())
    return output
