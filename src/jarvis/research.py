from __future__ import annotations

from dataclasses import dataclass
import html
from html.parser import HTMLParser
import re
import json
from pathlib import Path
import ssl
import threading
import unicodedata
from typing import Callable
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import certifi


@dataclass(frozen=True)
class ResearchResult:
    query: str
    summary: str
    sources: tuple[tuple[str, str], ...]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "svg"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "svg"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)


class BackgroundResearcher:
    """Investiga varias fuentes sin bloquear la conversación principal."""

    def __init__(
        self,
        summarizer: Callable[[str, list[dict[str, str]]], str],
        on_complete: Callable[[ResearchResult], None] | None = None,
        storage_path: Path | None = None,
    ) -> None:
        self.summarizer = summarizer
        self.on_complete = on_complete
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._state = "idle"
        self._query = ""
        self._progress = ""
        self._result: ResearchResult | None = None
        self._load_result()

    def start(self, query: str) -> bool:
        clean_query = query.strip()[:500]
        with self._lock:
            if self._state == "running" or not clean_query:
                return False
            self._state = "running"
            self._query = clean_query
            self._progress = "buscando fuentes"
            self._result = None
        threading.Thread(target=self._run, args=(clean_query,), daemon=True).start()
        return True

    def status(self) -> tuple[str, str]:
        with self._lock:
            if self._state == "running":
                return self._state, self._progress
            if self._state == "done" and self._result is not None:
                return self._state, self._result.summary
            return self._state, self._progress

    def result(self) -> ResearchResult | None:
        with self._lock:
            return self._result

    def _run(self, query: str) -> None:
        try:
            links = self._search(query)
            sources: list[dict[str, str]] = []
            for index, (title, url, description) in enumerate(links[:5], start=1):
                with self._lock:
                    self._progress = f"leyendo la fuente {index} de {min(5, len(links))}"
                text = self._fetch_text(url)
                sources.append(
                    {
                        "title": title,
                        "url": url,
                        "text": (text or description)[:6000],
                    }
                )
            if not sources:
                raise RuntimeError("No he encontrado fuentes accesibles.")
            with self._lock:
                self._progress = "comparando la información"
            summary = self.summarizer(query, sources)
            result = ResearchResult(
                query=query,
                summary=summary,
                sources=tuple((source["title"], source["url"]) for source in sources),
            )
            with self._lock:
                self._result = result
                self._state = "done"
                self._progress = "investigación terminada"
            self._save_result(result)
            if self.on_complete is not None:
                self.on_complete(result)
        except Exception as error:
            with self._lock:
                self._state = "error"
                self._progress = str(error)[:300]

    def _save_result(self, result: ResearchResult) -> None:
        if self.storage_path is None:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(
                json.dumps(
                    {
                        "query": result.query,
                        "summary": result.summary,
                        "sources": list(result.sources),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_result(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._result = ResearchResult(
                query=str(data["query"]),
                summary=str(data["summary"]),
                sources=tuple((str(title), str(url)) for title, url in data["sources"]),
            )
            self._state = "done"
            self._progress = "investigación anterior disponible"
        except (OSError, ValueError, KeyError, TypeError):
            pass

    @staticmethod
    def _context() -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())

    @classmethod
    def _search(cls, query: str) -> list[tuple[str, str, str]]:
        keywords = cls._keywords(query)
        results = cls._bing_search(query)
        relevant = [
            result for result in results
            if any(keyword in cls._plain(f"{result[0]} {result[2]}") for keyword in keywords)
        ]
        if keywords and (len(relevant) < 3 or len(keywords) >= 2):
            refined = " ".join(keywords) + " comparison speed durability advantages"
            retry = cls._bing_search(refined)
            relevant.extend(
                result for result in retry
                if result not in relevant
                and any(keyword in cls._plain(f"{result[0]} {result[2]}") for keyword in keywords)
            )
        candidates = relevant or results
        commerce = ("amazon.", "mediamarkt.", "idealo.", "ebay.", "aliexpress.")
        return sorted(
            candidates,
            key=lambda result: (
                -sum(keyword in cls._plain(f"{result[0]} {result[2]}") for keyword in keywords),
                any(domain in result[1].casefold() for domain in commerce),
            ),
        )

    @classmethod
    def _bing_search(cls, query: str) -> list[tuple[str, str, str]]:
        url = f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 Jarvis/0.4"})
        with urlopen(request, timeout=12, context=cls._context()) as response:
            root = ET.fromstring(response.read(2_000_000))
        results: list[tuple[str, str, str]] = []
        for item in root.findall(".//item"):
            title = html.unescape(item.findtext("title", default="")).strip()
            link = item.findtext("link", default="").strip()
            description = re.sub(
                r"<[^>]+>", " ", html.unescape(item.findtext("description", default=""))
            )
            if link.startswith(("http://", "https://")):
                results.append((title, link, " ".join(description.split())))
        return results

    @staticmethod
    def _keywords(query: str) -> list[str]:
        stopwords = {
            "para", "como", "cual", "cuales", "sobre", "entre", "desde", "hasta",
            "diferencia", "diferencias", "practica", "practicas", "mejor", "peor",
            "quiero", "saber", "informacion", "investiga", "compara", "averigua",
            "que", "por", "con", "una", "uno", "del", "las", "los", "sus",
        }
        words = re.findall(r"[\w]{3,}", BackgroundResearcher._plain(query))
        return [word for word in words if word not in stopwords][:8]

    @staticmethod
    def _plain(text: str) -> str:
        return "".join(
            character
            for character in unicodedata.normalize("NFKD", text.casefold())
            if not unicodedata.combining(character)
        )

    @classmethod
    def _fetch_text(cls, url: str) -> str:
        if urlparse(url).scheme not in {"http", "https"}:
            return ""
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 Jarvis/0.4"})
            with urlopen(request, timeout=10, context=cls._context()) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "text/plain"}:
                    return ""
                body = response.read(1_500_000).decode(
                    response.headers.get_content_charset() or "utf-8", errors="ignore"
                )
        except (OSError, TimeoutError, UnicodeError):
            return ""
        extractor = _TextExtractor()
        extractor.feed(body)
        return " ".join(extractor.parts)[:10_000]
