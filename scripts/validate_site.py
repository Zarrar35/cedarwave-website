#!/usr/bin/env python3
"""Validate Cedarwave's static site without third-party dependencies."""

from __future__ import annotations

import json
import hashlib
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
    "Events": re.compile(r"\bevents?\b", re.IGNORECASE),
    "Pools": re.compile(r"\bpools?\b", re.IGNORECASE),
    "Chat or conversations": re.compile(r"\b(?:chats?|conversations?)\b", re.IGNORECASE),
    "chores": re.compile(r"\bchores?\b", re.IGNORECASE),
    "groceries": re.compile(r"\bgroceries\b", re.IGNORECASE),
    "maintenance or Safety Center": re.compile(r"\b(?:maintenance|safety\s+center)\b", re.IGNORECASE),
    "fit check": re.compile(r"\bfit\s+check\b", re.IGNORECASE),
    "compatibility or alignment score": re.compile(
        r"\b(?:(?:compatibility|alignment|match)\s+(?:percentage|score|result)s?"
        r"|\d{1,3}\s*(?:%|percent)\s+(?:match|compatible|fit|aligned))\b",
        re.IGNORECASE,
    ),
    "introductions": re.compile(r"\bintroductions?\b", re.IGNORECASE),
    "identity verification": re.compile(r"\b(?:identity\s+verified|verified\s+identity|identity\s+verification)\b", re.IGNORECASE),
    "lease or tenancy documents": re.compile(r"\b(?:lease|tenancy|rental)\s+(?:agreements?|documents?|signing|uploads?)\b", re.IGNORECASE),
    "Finder": re.compile(r"\bfinder\b", re.IGNORECASE),
    "Premium": re.compile(r"\bpremium\b", re.IGNORECASE),
    "affirmative money movement": re.compile(
        r"\broofmates\s+(?:moves?|sends?|holds?|transfers?)\s+(?:roommate\s+)?(?:money|funds)\b",
        re.IGNORECASE,
    ),
    "affirmative tenancy change": re.compile(
        r"\broofmates\s+(?:creates?|changes?|authorizes?|establishes?)\s+(?:a\s+)?(?:lease|tenancy|sublet|ownership(?:\s+right)?)\b",
        re.IGNORECASE,
    ),
    "messaging action": re.compile(r"\b(?:send|message)\s+messages?\b", re.IGNORECASE),
    "identity verification action": re.compile(
        r"\b(?:verify|confirm|validate|prove)\s+"
        r"(?:(?:(?:your|a|the)\s+)?identity|who\s+you\s+are)\b",
        re.IGNORECASE,
    ),
    "lease signing action": re.compile(
        r"\b(?:sign|execute|upload|create|generate)\s+(?:(?:a|the|your)\s+)?"
        r"(?:lease|tenancy|rental)(?:\s+(?:agreement|contract))?\b",
        re.IGNORECASE,
    ),
    "direct roommate payment": re.compile(
        r"\bdirect\s+roommate\s+payments?\b",
        re.IGNORECASE,
    ),
    "in-app roommate payment": re.compile(
        r"\b(?:pay|send|transfer|move|route|remit)\s+"
        r"(?:(?:money|funds|cash)\s+to\s+)?"
        r"(?:(?:a|the|your)\s+)?roommates?\s+"
        r"(?:(?:directly|right)\s+)?(?:in|inside|through|with|using|via)\s+"
        r"(?:(?:the|this)\s+)?(?:roofmates|app)\b",
        re.IGNORECASE,
    ),
}
REQUIRED_ROOFMATES_TRUTHS = (
    "Household membership alone does not expose every expense.",
    "does not hold or transfer roommate funds",
    "does not create or change a lease, tenancy, or ownership right",
)
REQUIRED_INDEX_TRUTHS = (
    "with explicit participant boundaries and no money movement.",
)
TRACKING_PATTERNS = {
    "google-analytics": re.compile(r"google-analytics", re.IGNORECASE),
    "googletagmanager": re.compile(r"googletagmanager", re.IGNORECASE),
    "gtag(": re.compile(r"\bgtag\s*\(", re.IGNORECASE),
    "facebook.com/tr": re.compile(r"facebook\.com/tr", re.IGNORECASE),
    "connect.facebook.net": re.compile(r"connect\.facebook\.net", re.IGNORECASE),
    "segment.com/analytics": re.compile(r"segment\.com/analytics", re.IGNORECASE),
    "plausible.io/js": re.compile(r"plausible\.io/js", re.IGNORECASE),
    "posthog": re.compile(r"\bposthog\b", re.IGNORECASE),
    "mixpanel": re.compile(r"\bmixpanel\b", re.IGNORECASE),
    "sendBeacon": re.compile(r"\bsend\s*beacon\b", re.IGNORECASE),
}
LAUNCH_BAND_HEADING_CONTRAST = re.compile(
    r"\.launch-band\s+h2\s*\{[^}]*\bcolor:\s*var\(--ink\)\s*;",
    re.DOTALL,
)
EXPECTED_PREVIEW_ACCESSIBLE_NAME = (
    "Illustrative Roofmates launch preview showing a shared expense, "
    "participant-scoped balance, and Home, Wallet, House, and You destinations"
)
RETIRED_SCREENSHOT_PATH = "assets/roofmates-phone-ios.png"
RETIRED_SCREENSHOT_SHA256 = "8752f835453bfff550d7374e6484829d15c26c322abe719de26965895237cdca"
RETIRED_SCREENSHOT_SIZE = 463_994
REQUIRED_NORMAL_TEXT_CONTRAST = {
    ".pill": ("#1c2721", "#e3eadb", None),
    ".launch-preview__notice": ("#a83217", "#f6eddf", ".launch-preview"),
    ".button--product:hover": ("#fffaf2", "#a7381b", None),
    ".button--wine:hover": ("#fffaf2", "#641f38", None),
}
VOID_HTML_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def compact(value: str) -> str:
    return " ".join(value.split())


@dataclass(frozen=True)
class CSSRule:
    selector: str
    declarations: dict[str, tuple[str, bool]]
    specificity: tuple[int, int, int]
    order: int


def _selector_specificity(selector: str) -> tuple[int, int, int]:
    ids = len(re.findall(r"#[a-zA-Z_][\w-]*", selector))
    classes = len(re.findall(r"\.[a-zA-Z_][\w-]*", selector))
    attributes = len(re.findall(r"\[[^]]+\]", selector))
    pseudo_classes = len(re.findall(r"(?<!:):[a-zA-Z_][\w-]*(?:\([^)]*\))?", selector))
    without_non_elements = re.sub(
        r"#[a-zA-Z_][\w-]*|\.[a-zA-Z_][\w-]*|\[[^]]+\]|:{1,2}[a-zA-Z_][\w-]*(?:\([^)]*\))?",
        " ",
        selector,
    )
    elements = len(re.findall(r"(?:^|[\s>+~])(?:[a-zA-Z][\w-]*|\*)", without_non_elements))
    pseudo_elements = len(re.findall(r"::[a-zA-Z_][\w-]*", selector))
    return ids, classes + attributes + pseudo_classes, elements + pseudo_elements


def parse_css_rules(stylesheet: str) -> list[CSSRule]:
    rules: list[CSSRule] = []
    without_comments = re.sub(r"/\*.*?\*/", "", stylesheet, flags=re.DOTALL)
    for order, match in enumerate(re.finditer(r"([^{}]+)\{([^{}]*)\}", without_comments)):
        selector_source, block = match.groups()
        declarations: dict[str, tuple[str, bool]] = {}
        for declaration in block.split(";"):
            if ":" not in declaration:
                continue
            name, value = declaration.split(":", 1)
            important = bool(re.search(r"!\s*important\s*$", value, re.IGNORECASE))
            normalized_value = re.sub(r"!\s*important\s*$", "", value, flags=re.IGNORECASE).strip().lower()
            declarations[name.strip().lower()] = (normalized_value, important)
        if not declarations:
            continue
        for selector in selector_source.split(","):
            normalized_selector = compact(selector)
            if not normalized_selector or normalized_selector.startswith("@"):
                continue
            rules.append(
                CSSRule(
                    selector=normalized_selector,
                    declarations=declarations,
                    specificity=_selector_specificity(normalized_selector),
                    order=order,
                ),
            )
    return rules


def _last_selector_compound(selector: str) -> str:
    depth = 0
    quote: str | None = None
    start = 0
    for index, character in enumerate(selector):
        if quote is not None:
            if character == quote and (index == 0 or selector[index - 1] != "\\"):
                quote = None
            continue
        if depth and character in {"'", '"'}:
            quote = character
        elif character == "[":
            depth += 1
        elif character == "]" and depth:
            depth -= 1
        elif depth == 0 and (character.isspace() or character in {">", "+", "~"}):
            start = index + 1
    return selector[start:].strip()


def _compound_tokens(selector: str) -> tuple[set[str], set[str], set[str]]:
    compound = _last_selector_compound(selector)
    ids = set(re.findall(r"#([a-zA-Z_][\w-]*)", compound))
    classes = set(re.findall(r"\.([a-zA-Z_][\w-]*)", compound))
    for _, value in re.findall(
        r"\[\s*class\s*~=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
        compound,
        flags=re.IGNORECASE,
    ):
        classes.add(value)
    for value in re.findall(
        r"\[\s*class\s*~=\s*([a-zA-Z_][\w-]*)(?:\s+[is])?\s*\]",
        compound,
        flags=re.IGNORECASE,
    ):
        classes.add(value)
    for _, value in re.findall(
        r"\[\s*class\s*=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
        compound,
        flags=re.IGNORECASE,
    ):
        classes.update(value.split())
    for _, value in re.findall(
        r"\[\s*id\s*=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
        compound,
        flags=re.IGNORECASE,
    ):
        ids.add(value)
    pseudos = set(re.findall(r"(?<!:):([a-zA-Z_][\w-]*)", compound))
    return ids, classes, pseudos


def _selector_applies_to_target(candidate: str, target: str) -> bool:
    target_ids, target_classes, target_pseudos = _compound_tokens(target)
    candidate_ids, candidate_classes, candidate_pseudos = _compound_tokens(candidate)
    return (
        target_ids.issubset(candidate_ids)
        and target_classes.issubset(candidate_classes)
        and target_pseudos.issubset(candidate_pseudos)
    )


def css_declarations(stylesheet: str, selector: str) -> dict[str, str]:
    winners: dict[str, tuple[tuple[int, tuple[int, int, int], int], str]] = {}
    for rule in parse_css_rules(stylesheet):
        if not _selector_applies_to_target(rule.selector, selector):
            continue
        for name, (value, important) in rule.declarations.items():
            precedence = (int(important), rule.specificity, rule.order)
            if name not in winners or precedence >= winners[name][0]:
                winners[name] = (precedence, value)
    return {name: value for name, (_, value) in winners.items()}


def css_element_declarations(
    rules: list[CSSRule],
    tag: str,
    element_id: str,
    classes: set[str],
) -> dict[str, str]:
    winners: dict[str, tuple[tuple[int, tuple[int, int, int], int], str]] = {}
    for rule in rules:
        compound = _last_selector_compound(rule.selector)
        if re.search(r"(?<!:):[a-zA-Z_][\w-]*", compound):
            continue
        required_ids = set(re.findall(r"#([a-zA-Z_][\w-]*)", compound))
        required_classes = set(re.findall(r"\.([a-zA-Z_][\w-]*)", compound))
        supported_attributes: list[str] = []
        for match in re.finditer(
            r"\[\s*class\s*~=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
            compound,
            flags=re.IGNORECASE,
        ):
            required_classes.add(match.group(2))
            supported_attributes.append(match.group(0))
        for match in re.finditer(
            r"\[\s*class\s*~=\s*([a-zA-Z_][\w-]*)(?:\s+[is])?\s*\]",
            compound,
            flags=re.IGNORECASE,
        ):
            required_classes.add(match.group(1))
            supported_attributes.append(match.group(0))
        for match in re.finditer(
            r"\[\s*class\s*=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
            compound,
            flags=re.IGNORECASE,
        ):
            required_classes.update(match.group(2).split())
            supported_attributes.append(match.group(0))
        for match in re.finditer(
            r"\[\s*id\s*=\s*(['\"])([^'\"]+)\1(?:\s+[is])?\s*\]",
            compound,
            flags=re.IGNORECASE,
        ):
            required_ids.add(match.group(2))
            supported_attributes.append(match.group(0))
        without_supported_attributes = compound
        for attribute in supported_attributes:
            without_supported_attributes = without_supported_attributes.replace(attribute, "")
        if "[" in without_supported_attributes or "]" in without_supported_attributes:
            continue
        stripped = re.sub(
            r"#[a-zA-Z_][\w-]*|\.[a-zA-Z_][\w-]*|::?[a-zA-Z_][\w-]*",
            "",
            without_supported_attributes,
        )
        required_tag = stripped.strip().casefold()
        if required_ids and required_ids != {element_id}:
            continue
        if not required_classes.issubset(classes):
            continue
        if required_tag and required_tag != "*" and required_tag != tag:
            continue
        for name, (value, important) in rule.declarations.items():
            precedence = (int(important), rule.specificity, rule.order)
            if name not in winners or precedence >= winners[name][0]:
                winners[name] = (precedence, value)
    return {name: value for name, (_, value) in winners.items()}


def _declaration_values(block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for declaration in block.split(";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        values[name.strip().casefold()] = re.sub(
            r"!\s*important\s*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip().casefold()
    return values


def _css_values_hide_content(values: dict[str, str]) -> bool:
    if values.get("display") == "none" or values.get("visibility") == "hidden":
        return True
    opacity = values.get("opacity")
    if opacity is not None:
        try:
            opacity_value = float(opacity[:-1]) / 100 if opacity.endswith("%") else float(opacity)
        except ValueError:
            return True
        if opacity_value <= 0.01:
            return True
    clip = re.sub(r"[\s,]+", "", values.get("clip", ""))
    if clip and clip not in {"auto", "none"}:
        return True
    clip_path = re.sub(r"\s+", "", values.get("clip-path", ""))
    if clip_path and clip_path != "none":
        return True
    width = values.get("width", "")
    height = values.get("height", "")
    if (
        values.get("overflow") in {"hidden", "clip"}
        and re.fullmatch(r"(?:0|1(?:\.0+)?)px", width)
        and re.fullmatch(r"(?:0|1(?:\.0+)?)px", height)
    ):
        return True
    return False


def relative_luminance(color: str) -> float:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError(f"unsupported color: {color}")
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in json_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in json_strings(child)]
    return []


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
    claim_surfaces: list[str] = field(default_factory=list)
    named_roles: list[tuple[str, str]] = field(default_factory=list)
    role_sources: list[tuple[str, str, tuple[str, ...]]] = field(default_factory=list)
    id_text_parts: dict[str, list[str]] = field(default_factory=dict)


class SiteHTMLParser(HTMLParser):
    def __init__(self, path: Path, css_rules: list[CSSRule] | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.page = PageData(path)
        self._css_rules = css_rules or []
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._h1_depth = 0
        self._h1_parts: list[str] = []
        self._json_depth = 0
        self._json_parts: list[str] = []
        self._ignored_elements: list[str] = []
        self._visibility_stack: list[tuple[str, bool, str | None]] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs}
        tag = tag.lower()
        style = (values.get("style") or "").casefold()
        inline_values = _declaration_values(style)
        element_id = values.get("id") or ""
        classes = {part for part in (values.get("class") or "").split() if part}
        css_values = css_element_declarations(self._css_rules, tag, element_id, classes)
        hidden = (
            self._hidden_depth > 0
            or tag in {"template", "noscript"}
            or "hidden" in values
            or (values.get("aria-hidden") or "").casefold() == "true"
            or "display:none" in style.replace(" ", "")
            or "visibility:hidden" in style.replace(" ", "")
            or _css_values_hide_content(inline_values)
            or _css_values_hide_content(css_values)
        )
        if tag not in VOID_HTML_ELEMENTS:
            active_id = element_id or None
            self._visibility_stack.append((tag, hidden, active_id))
            if hidden:
                self._hidden_depth += 1

        if tag == "html":
            self.page.html_lang = values.get("lang")
        if element_id:
            self.page.ids.add(element_id)
            self.page.id_text_parts.setdefault(element_id, [])

        if tag == "title":
            self._title_depth += 1
            self._title_parts = []
        elif tag == "h1":
            self._h1_depth += 1
            self._h1_parts = []
        elif tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._json_depth += 1
            self._json_parts = []
        elif tag in {"script", "style"}:
            self._ignored_elements.append(tag)

        if not hidden:
            for attribute in ("aria-label", "alt", "title"):
                value = values.get(attribute)
                if value:
                    self.page.claim_surfaces.append(compact(value))
            role = compact(values.get("role") or "").casefold()
            if role:
                direct_name = compact(values.get("aria-label") or values.get("alt") or "")
                labelledby = tuple((values.get("aria-labelledby") or "").split())
                self.page.role_sources.append((role, direct_name, labelledby))

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
            content = values.get("content") or ""
            if content:
                self.page.claim_surfaces.append(compact(content))

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
        if self._visibility_stack and self._visibility_stack[-1][0] == tag:
            _, hidden, _ = self._visibility_stack.pop()
            if hidden:
                self._hidden_depth -= 1
        if self._ignored_elements and self._ignored_elements[-1] == tag:
            self._ignored_elements.pop()
            return
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
        if not self._ignored_elements and compact(data):
            for _, _, active_id in self._visibility_stack:
                if active_id:
                    self.page.id_text_parts.setdefault(active_id, []).append(data)
        if self._title_depth:
            self._title_parts.append(data)
        if self._h1_depth:
            self._h1_parts.append(data)
        if self._json_depth:
            self._json_parts.append(data)
        elif not self._ignored_elements and self._hidden_depth == 0 and compact(data):
            self.page.claim_surfaces.append(compact(data))

    def resolve_accessible_names(self) -> None:
        for role, direct_name, labelledby in self.page.role_sources:
            referenced_name = compact(
                " ".join(
                    " ".join(self.page.id_text_parts.get(identifier, []))
                    for identifier in labelledby
                ),
            )
            accessible_name = direct_name or referenced_name
            self.page.named_roles.append((role, accessible_name))
            if referenced_name:
                self.page.claim_surfaces.append(referenced_name)


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.pages: dict[Path, PageData] = {}
        self.reference_count = 0
        self.json_ld_count = 0
        self.sitemap_count = 0
        self.stylesheet = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.css_rules = parse_css_rules(self.stylesheet)

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
            parser = SiteHTMLParser(page, self.css_rules)
            try:
                parser.feed(page.read_text(encoding="utf-8"))
                parser.close()
                parser.resolve_accessible_names()
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
            self.check(
                data.viewports == ["width=device-width, initial-scale=1"],
                f"{page.name}: viewport must be exactly width=device-width, initial-scale=1",
            )
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
                self.pages[page].claim_surfaces.extend(compact(value) for value in json_strings(parsed))
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
                        parser = SiteHTMLParser(target, self.css_rules)
                        parser.feed(target.read_text(encoding="utf-8"))
                        parser.close()
                        parser.resolve_accessible_names()
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
            data = self.pages[ROOT / name]
            semantic_text = compact(" ".join(data.claim_surfaces))
            for label, pattern in UNSUPPORTED_ROOFMATES_CLAIMS.items():
                matches = pattern.findall(semantic_text)
                claim_matches += len(matches)
                self.check(not matches, f"{name}: unsupported Roofmates claim found: {label}")

            self.check(
                data.named_roles == [("img", EXPECTED_PREVIEW_ACCESSIBLE_NAME)],
                f"{name}: launch preview must expose one exact img role and accessible name",
            )

        self.check(claim_matches == 0, f"unsupported Roofmates claim matches found: {claim_matches}")
        index_source = compact(" ".join(self.pages[ROOT / "index.html"].claim_surfaces))
        for truth in REQUIRED_INDEX_TRUTHS:
            self.check(truth in index_source, f"index.html: required launch boundary is missing: {truth}")
        roofmates_source = compact(" ".join(self.pages[ROOT / "roofmates.html"].claim_surfaces))
        for truth in REQUIRED_ROOFMATES_TRUTHS:
            self.check(truth in roofmates_source, f"roofmates.html: required launch boundary is missing: {truth}")
        stylesheet = self.stylesheet
        self.check(
            bool(LAUNCH_BAND_HEADING_CONTRAST.search(stylesheet)),
            "styles.css: launch-status heading must use the light --ink token",
        )
        retired_asset = ROOT / RETIRED_SCREENSHOT_PATH
        self.check(not retired_asset.exists(), f"retired screenshot must be absent: {RETIRED_SCREENSHOT_PATH}")
        for candidate in ROOT.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                if candidate.stat().st_size != RETIRED_SCREENSHOT_SIZE:
                    continue
                digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except OSError as error:
                self.errors.append(f"unable to inspect asset digest: {candidate.relative_to(ROOT)}: {error}")
                continue
            self.check(
                digest != RETIRED_SCREENSHOT_SHA256,
                f"retired screenshot content is not allowed under any filename: {candidate.relative_to(ROOT)}",
            )
        for name in ("index.html", "roofmates.html"):
            references = [raw_url for _, raw_url in self.pages[ROOT / name].references]
            self.check(
                RETIRED_SCREENSHOT_PATH not in references,
                f"{name}: retired screenshot reference is not allowed",
            )
        self.check(
            RETIRED_SCREENSHOT_PATH not in stylesheet,
            "styles.css: retired screenshot reference is not allowed",
        )
        for selector, (
            expected_foreground,
            expected_background,
            background_selector,
        ) in REQUIRED_NORMAL_TEXT_CONTRAST.items():
            declarations = css_declarations(stylesheet, selector)
            foreground = declarations.get("color", "")
            background = declarations.get("background", declarations.get("background-color", ""))
            if background_selector is not None:
                background_declarations = css_declarations(stylesheet, background_selector)
                background = background_declarations.get(
                    "background",
                    background_declarations.get("background-color", ""),
                )
            self.check(
                foreground == expected_foreground and background == expected_background,
                f"styles.css: {selector} must retain its reviewed foreground/background pair",
            )
            try:
                ratio = contrast_ratio(foreground, background)
            except ValueError:
                ratio = 0
            self.check(ratio >= 4.5, f"styles.css: {selector} normal-text contrast is {ratio:.2f}:1")
        tracking_sources = list(pages)
        tracking_sources.extend(
            candidate
            for candidate in sorted(ROOT.rglob("*"))
            if candidate.is_file() and candidate.suffix.casefold() in {".js", ".mjs", ".cjs"}
        )
        for source_path in tracking_sources:
            source = source_path.read_text(encoding="utf-8")
            for marker, pattern in TRACKING_PATTERNS.items():
                self.check(
                    not pattern.search(source),
                    f"{source_path.relative_to(ROOT)}: tracking marker found: {marker}",
                )
        for page in pages:
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
