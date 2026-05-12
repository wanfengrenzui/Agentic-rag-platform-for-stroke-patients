from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from src.contracts.rag_contract_models import (
    Evidence,
    RetrieverInputContract,
    RetrieverOutputContract,
    RetrievalDiagnostics,
    SectionType,
)


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_result_link = False
        self._in_snippet = False
        self._current_title: list[str] = []
        self._current_href = ""
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._in_result_link = True
            self._current_title = []
            self._current_href = attrs_dict.get("href", "") or ""
        elif tag in {"a", "div"} and "result__snippet" in class_name:
            self._in_snippet = True
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_title.append(data)
        elif self._in_snippet:
            self._current_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            title = " ".join("".join(self._current_title).split())
            if title and self._current_href:
                self.results.append({"title": title, "url": self._clean_url(self._current_href), "snippet": ""})
            self._in_result_link = False
        elif tag in {"a", "div"} and self._in_snippet:
            snippet = " ".join("".join(self._current_snippet).split())
            if self.results and snippet:
                self.results[-1]["snippet"] = snippet
            self._in_snippet = False

    @staticmethod
    def _clean_url(url: str) -> str:
        parsed = urllib.parse.urlparse(html.unescape(url))
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return query["uddg"][0]
        return html.unescape(url)


class WebSearchTool:
    """Small no-key web search adapter used as optional RAG evidence."""

    def search(self, query: str, top_k: int = 4) -> list[dict[str, str]]:
        return self._duckduckgo_html(query, top_k) or self._duckduckgo_instant_answer(query, top_k)

    def _duckduckgo_html(self, query: str, top_k: int) -> list[dict[str, str]]:
        url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return []
        parser = DuckDuckGoResultParser()
        parser.feed(body)
        return [item for item in parser.results if item.get("title")][:top_k]

    def _duckduckgo_instant_answer(self, query: str, top_k: int) -> list[dict[str, str]]:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        url = f"https://api.duckduckgo.com/?{params}"
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            return []
        results = []
        abstract = data.get("AbstractText")
        if abstract:
            results.append({"title": data.get("Heading") or query, "url": data.get("AbstractURL") or "", "snippet": abstract})
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({"title": topic.get("FirstURL") or query, "url": topic.get("FirstURL") or "", "snippet": topic["Text"]})
        return results[:top_k]


class WebAugmentedRetriever:
    """Retriever wrapper that appends web evidence after local evidence."""

    def __init__(self, local_retriever, web_search: WebSearchTool | None = None) -> None:
        self.local_retriever = local_retriever
        self.web_search = web_search or WebSearchTool()

    def run(self, payload: RetrieverInputContract) -> RetrieverOutputContract:
        local = self.local_retriever.run(payload)
        web_evidence = self._web_evidence(payload)
        combined = [*local.evidence_list, *web_evidence]
        combined.sort(key=lambda item: item.score_final, reverse=True)
        return RetrieverOutputContract(
            retrieval_status="success" if combined else local.retrieval_status,
            evidence_list=combined[: payload.top_k],
            retrieval_diagnostics=RetrievalDiagnostics(
                num_candidates_vector=local.retrieval_diagnostics.num_candidates_vector,
                num_candidates_bm25=local.retrieval_diagnostics.num_candidates_bm25 + len(web_evidence),
                num_merged=len(combined),
                num_returned=min(len(combined), payload.top_k),
                low_confidence=local.retrieval_diagnostics.low_confidence,
                norm_method=payload.norm_method,
                dedup_strategy="local_plus_web_url",
            ),
        )

    def _web_evidence(self, payload: RetrieverInputContract) -> list[Evidence]:
        query = " ".join(payload.queries)
        if not query.strip():
            return []
        results = self.web_search.search(query, top_k=max(2, min(4, payload.top_k)))
        evidence = []
        for index, result in enumerate(results):
            title = result.get("title") or "Web result"
            url = result.get("url") or ""
            snippet = result.get("snippet") or title
            text = f"{snippet}\nURL: {url}".strip()
            evidence.append(
                Evidence(
                    evidence_id=f"web_{index + 1}_{_slug(title)[:40]}",
                    paper_id=f"web_{index + 1}",
                    title=title,
                    authors=[],
                    year=None,
                    doi=url or None,
                    section=SectionType.ABSTRACT,
                    chunk_index=index,
                    page_start=1,
                    page_end=1,
                    text=text[:1800],
                    score_vector=0.45,
                    score_bm25=0.55,
                    score_final=max(0.35, 0.62 - index * 0.05),
                    source_type="web_search",
                )
            )
        return evidence


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower() or "result"
