#!/usr/bin/env python3
"""Validate Cedarwave's static site without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://cedarwavetechnologies.com"
EXPECTED_HTML_COUNT = 8
UNSUPPORTED_ROOFMATES_CLAIMS = {
    "chores": re.compile(r"\bchores?\b", re.IGNORECASE),
    "groceries": re.compile(r"\bgroceries\b", re.IGNORECASE),
    "maintenance": re.compile(r"\bmaintenance\b", re.IGNORECASE),
    "Event tasks": re.compile(r"\bevent\s+tasks?\b", re.IGNORECASE),
    "Pool contributions": re.compile(r"\bpool\s+contributions?\b", re.IGNORECASE),
    "Finder": re.compile(r"\bfinder\b", re.IGNORECASE),
    "Premium": re.compile(r"\bpremium\b", re.IGNORECASE),
}
TRACKING_MARKERS = (
    "google-analytics",
    "googletagmanager",
    "gtag(",
    "facebook.com/tr",
    "connect.facebook.net",
    "segment.com/analytics",
    "plausible.io/js",
    "posthog",
    "mixpanel",
)


def compact(value: str) -> str:
    return " ".join(value.split())


@dataclass
class PageData:
    path: Path
    titles: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    canonicals: list[str] = field(default_factory=list)
    h1s: list[str] = field(default_factory=list)
    robots: list[str] = field(default_factory=list)
    json_ld: list[str] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    ids: set[str] = field(default_factory=set)
    image_alts: list[str | None] = field(default_factory=list)
    html_lang: str | None = None
    charsets: list[str] = field(default_factory=list)
    viewports: list[str] = field(default_factory=list)
    external_scripts: list[str] = field(default_factory=list)


class SiteHTMLParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.page = PageData(path)
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._h1_depth = 0
        self._h1_parts: list[str] = []
        self._json_depth = 0
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs}
        tag = tag.lower()

        if tag == "html":
            self.page.html_lang = values.get("lang")
        if values.get("id"):
            self.page.ids.add(values["id"] or "")

        if tag == "title":
            self._title_depth += 1
            self._title_parts = []
        elif tag == "h1":
            self._h1_depth += 1
            self._h1_parts = []
        elif tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._json_depth += 1
            self._json_parts = []

        if tag == "meta":
            name = (values.get("name") or "").lower()
            if name == "description":
                self.page.descriptions.append(values.get("content") or "")
            elif name == "robots":
                self.page.robots.append(values.get("content") or "")
            if values.get("charset") is not None:
                self.page.charsets.append(values.get("charset") or "")
            if name == "viewport":
                self.page.viewports.append(values.get("content") or "")

        if tag == "link":
            rel = {part.lower() for part in (values.get("rel") or "").split()}
            href = values.get("href")
            if "canonical" in rel:
                self.page.canonicals.append(href or "")

        for attribute in ("href", "src"):
            value = values.get(attribute)
            if value:
                self.page.references.append((f"{tag}[{attribute}]", value))

        if tag == "script" and values.get("src"):
            script_src = values["src"] or ""
            parsed = urlsplit(script_src)
            if parsed.scheme or parsed.netloc:
                self.page.external_scripts.append(script_src)
        if tag == "img":
            self.page.image_alts.append(values.get("alt"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
            self.page.titles.append(compact("".join(self._title_parts)))
        elif tag == "h1" and self._h1_depth:
            self._h1_depth -= 1
            self.page.h1s.append(compact("".join(self._h1_parts)))
        elif tag == "script" and self._json_depth:
            self._json_depth -= 1
            self.page.json_ld.append("".join(self._json_parts).strip())

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self._title_parts.append(data)
        if self._h1_depth:
            self._h1_parts.append(data)
        if self._json_depth:
            self._json_parts.append(data)


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.pages: dict[Path, PageData] = {}
        self.reference_count = 0
        self.json_ld_count = 0
        self.sitemap_count = 0

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def parse_pages(self) -> list[Path]:
        pages = sorted(ROOT.glob("*.html"))
        self.check(
            len(pages) == EXPECTED_HTML_COUNT,
            f"expected {EXPECTED_HTML_COUNT} root HTML pages; found {len(pages)}",
        )
        for page in pages:
            parser = SiteHTMLParser(page)
            try:
                parser.feed(page.read_text(encoding="utf-8"))
                parser.close()
            except Exception as error:  # HTMLParser raises only for exceptional input failures.
                self.errors.append(f"{page.name}: HTML parse failed: {error}")
            self.pages[page] = parser.page
        return pages

    def validate_page_metadata(self, pages: list[Path]) -> None:
        unique_fields: dict[str, list[tuple[Path, str]]] = {
            "title": [],
            "meta description": [],
            "canonical": [],
            "H1": [],
        }
        for page in pages:
            data = self.pages[page]
            expected_canonical = f"{ORIGIN}/" if page.name == "index.html" else f"{ORIGIN}/{page.name}"
            requirements = {
                "title": data.titles,
                "meta description": data.descriptions,
                "canonical": data.canonicals,
                "H1": data.h1s,
            }
            for label, values in requirements.items():
                self.check(len(values) == 1, f"{page.name}: expected one {label}; found {len(values)}")
                if len(values) == 1:
                    self.check(bool(values[0].strip()), f"{page.name}: {label} is empty")
                    unique_fields[label].append((page, compact(values[0])))

            self.check(data.canonicals == [expected_canonical], f"{page.name}: canonical must be {expected_canonical}")
            self.check(data.html_lang == "en", f"{page.name}: html lang must be en")
            self.check([value.lower() for value in data.charsets] == ["utf-8"], f"{page.name}: expected one UTF-8 charset")
            self.check(len(data.viewports) == 1 and bool(data.viewports[0]), f"{page.name}: expected one nonempty viewport meta")
            self.check(len(data.robots) == 1 and bool(data.robots[0]), f"{page.name}: expected one nonempty robots meta")
            for image_alt in data.image_alts:
                self.check(image_alt is not None, f"{page.name}: every image must define alt text")

        for label, entries in unique_fields.items():
            grouped: dict[str, list[str]] = {}
            for page, value in entries:
                grouped.setdefault(value.casefold(), []).append(page.name)
            for names in grouped.values():
                self.check(len(names) == 1, f"duplicate {label} across: {', '.join(names)}")

    def validate_json_ld(self, pages: list[Path]) -> None:
        for page in pages:
            for block_number, source in enumerate(self.pages[page].json_ld, start=1):
                self.json_ld_count += 1
                try:
                    parsed = json.loads(source)
                except json.JSONDecodeError as error:
                    self.errors.append(f"{page.name}: JSON-LD block {block_number} is invalid: {error}")
                    continue
                objects = parsed if isinstance(parsed, list) else [parsed]
                self.check(bool(objects), f"{page.name}: JSON-LD block {block_number} is empty")
                for item in objects:
                    self.check(isinstance(item, dict), f"{page.name}: JSON-LD block {block_number} must contain objects")
                    if isinstance(item, dict):
                        self.check(item.get("@context") == "https://schema.org", f"{page.name}: JSON-LD must use schema.org context")
                        self.check(bool(item.get("@type")), f"{page.name}: JSON-LD object is missing @type")
        self.check(self.json_ld_count > 0, "site must contain at least one JSON-LD block")

    def resolve_local_target(self, source: Path, raw_url: str) -> tuple[Path | None, str | None, bool]:
        parsed = urlsplit(raw_url)
        if parsed.scheme in {"mailto", "tel", "data"}:
            return None, None, False
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.netloc != "cedarwavetechnologies.com":
                return None, parsed.fragment or None, False
            url_path = unquote(parsed.path)
            candidate = ROOT / (url_path.lstrip("/") or "index.html")
        else:
            url_path = unquote(parsed.path)
            if not url_path:
                candidate = source
            elif url_path.startswith("/"):
                candidate = ROOT / url_path.lstrip("/")
            else:
                candidate = source.parent / url_path

        candidate = candidate.resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            self.errors.append(f"{source.name}: local reference escapes the site root: {raw_url}")
            return None, parsed.fragment or None, True
        if candidate.is_dir():
            candidate = candidate / "index.html"
        return candidate, parsed.fragment or None, True

    def validate_references(self, pages: list[Path]) -> None:
        for page in pages:
            for location, raw_url in self.pages[page].references:
                self.reference_count += 1
                target, fragment, is_local = self.resolve_local_target(page, raw_url)
                if not is_local:
                    continue
                self.check(target is not None and target.is_file(), f"{page.name}: missing target for {location}: {raw_url}")
                if target is not None and target.is_file() and fragment:
                    target_data = self.pages.get(target)
                    if target_data is None and target.suffix.lower() == ".html":
                        parser = SiteHTMLParser(target)
                        parser.feed(target.read_text(encoding="utf-8"))
                        parser.close()
                        target_data = parser.page
                    self.check(
                        target_data is not None and fragment in target_data.ids,
                        f"{page.name}: missing fragment #{fragment} in {target.name}",
                    )

        css = ROOT / "styles.css"
        for raw_url in re.findall(r"url\(\s*['\"]?([^)'\"]+)", css.read_text(encoding="utf-8"), re.IGNORECASE):
            self.reference_count += 1
            target, _, is_local = self.resolve_local_target(css, raw_url.strip())
            if is_local:
                self.check(target is not None and target.is_file(), f"styles.css: missing asset: {raw_url}")

    def validate_sitemap(self) -> None:
        sitemap_path = ROOT / "sitemap.xml"
        try:
            root = ElementTree.parse(sitemap_path).getroot()
        except (ElementTree.ParseError, OSError) as error:
            self.errors.append(f"sitemap.xml: invalid XML: {error}")
            return
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        self.check(root.tag == f"{namespace}urlset", "sitemap.xml: root must be a sitemap urlset")
        locations = [compact(node.text or "") for node in root.findall(f"{namespace}url/{namespace}loc")]
        self.sitemap_count = len(locations)
        self.check(bool(locations), "sitemap.xml: no URLs found")
        self.check(len(locations) == len(set(locations)), "sitemap.xml: duplicate URLs found")

        indexable_canonicals: set[str] = set()
        for page, data in self.pages.items():
            directives = {part.strip().lower() for value in data.robots for part in value.split(",")}
            if "index" in directives and len(data.canonicals) == 1:
                indexable_canonicals.add(data.canonicals[0])
        self.check(set(locations) == indexable_canonicals, "sitemap.xml: URLs must exactly match indexable page canonicals")

        for location in locations:
            target, _, is_local = self.resolve_local_target(sitemap_path, location)
            self.check(is_local, f"sitemap.xml: URL must use the Cedarwave HTTPS origin: {location}")
            self.check(target is not None and target.is_file(), f"sitemap.xml: URL has no local page: {location}")

    def validate_claims_and_tracking(self, pages: list[Path]) -> None:
        claim_matches = 0
        for name in ("index.html", "roofmates.html"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for label, pattern in UNSUPPORTED_ROOFMATES_CLAIMS.items():
                matches = pattern.findall(source)
                claim_matches += len(matches)
                self.check(not matches, f"{name}: unsupported Roofmates claim found: {label}")

        self.check(claim_matches == 0, f"unsupported Roofmates claim matches found: {claim_matches}")
        for page in pages:
            source = page.read_text(encoding="utf-8").casefold()
            for marker in TRACKING_MARKERS:
                self.check(marker not in source, f"{page.name}: tracking marker found: {marker}")
            self.check(not self.pages[page].external_scripts, f"{page.name}: external scripts are not allowed")

    def run(self) -> int:
        pages = self.parse_pages()
        self.validate_page_metadata(pages)
        self.validate_json_ld(pages)
        self.validate_references(pages)
        self.validate_sitemap()
        self.validate_claims_and_tracking(pages)

        if self.errors:
            print(f"Site validation failed with {len(self.errors)} error(s):", file=sys.stderr)
            for error in self.errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        print(f"PASS: {len(pages)} HTML pages parsed")
        print("PASS: every page has one nonempty title, canonical, H1, and meta description")
        print("PASS: titles, canonicals, H1s, and meta descriptions are unique")
        print(f"PASS: {self.json_ld_count} JSON-LD blocks are valid schema.org JSON")
        print(f"PASS: sitemap has {self.sitemap_count} URLs matching all indexable canonicals")
        print(f"PASS: {self.reference_count} local links and assets resolve, including fragments")
        print("PASS: Roofmates launch pages contain 0 enumerated disallowed launch-term matches")
        print("PASS: no tracking markers or external scripts found")
        return 0


if __name__ == "__main__":
    raise SystemExit(Validation().run())
