"""Reads a job posting from a pasted link (GitHub issue #4).

Users paste job links into the posting field as often as the posting text
itself. The engine only understands text, so a link has to be turned into
the posting's text before run_pipeline sees it. That is a web-service
concern (network access, SSRF protection), which is why it lives here and
not in src/passthebot.

Extraction is tiered, from most to least structured:

1. JSON-LD: most job boards embed a schema.org JobPosting object for
   Google Jobs (Recruitee, Ashby, HelloWork, ...). Its description is the
   posting itself, without navigation or cookie banners.
2. App state: client-rendered boards (e.g. Rippling, Next.js) ship the
   posting as HTML strings inside an embedded __NEXT_DATA__ /
   __NUXT_DATA__ JSON blob.
3. Page text: the visible text of <main>/<article>/<body>.

A page that renders its content only in the browser (an empty JS shell)
yields none of these and raises PostingFetchError("unreadable") -- the user
is told to paste the text instead. There is deliberately no headless
browser on the backend (memory/attack surface on a small Fly machine).

Known V1 limitation: the SSRF check resolves the hostname once and httpx
resolves it again when connecting, so a DNS-rebinding host could in theory
answer differently the second time. Redirect targets are re-validated per
hop, and the backend has no credentials or internal services worth
reaching beyond what the private-range block already covers.
"""

from __future__ import annotations

import html as html_lib
import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlsplit

import httpx

MAX_RESPONSE_BYTES = 3 * 1024 * 1024
TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 3
MIN_DESCRIPTION_WORDS = 30
MIN_APP_STATE_CHARS = 200
MIN_PAGE_TEXT_WORDS = 150

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<(?:p|li|ul|ol|div|br|h[1-6]|strong|b|span)\b", re.IGNORECASE)
# Path segments of an embedded-JSON string that indicate posting content,
# as opposed to UI copy (e.g. Rippling's _nextI18Next translation strings).
_APP_STATE_KEY_HINTS = (
    "description", "responsibilit", "requirement", "qualification",
    "jobpost", "jobposting", "posting", "vacancy",
)
_APP_STATE_SCRIPT_IDS = {"__NEXT_DATA__", "__NUXT_DATA__"}

_BLOCK_TAGS = {
    "p", "div", "br", "ul", "ol", "tr", "table", "section", "article",
    "header", "footer", "main", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "hr", "dl", "dt", "dd",
}
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
# Link text is skipped too: on page text, links are menus and lists of
# other open jobs, never the posting's own requirements.
_PAGE_CHROME_TAGS = {"nav", "header", "footer", "form", "aside", "a"}


class PostingFetchError(Exception):
    """A pasted link could not be turned into posting text. `code` is one
    of: unsafe_url, unreachable, gone, timeout, too_large, not_html,
    unreadable."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass
class PostingSource:
    url: str
    host: str
    title: str | None
    company: str | None
    method: str  # "jsonld" | "app_state" | "page_text"
    text: str

    def to_dict(self) -> dict:
        return {**asdict(self), "chars": len(self.text)}


def looks_like_url(text: str) -> bool:
    """True if the whole posting field is a single http(s) link."""
    return bool(_URL_RE.match(text.strip()))


# --- HTML -> text -----------------------------------------------------------


class _TextExtractor(HTMLParser):
    """Turns HTML into line-structured plain text the engine can read:
    list items become "- item" lines and block elements start new lines, so
    passthebot.normalizer finds headings and bullets exactly as it would in
    pasted text."""

    def __init__(self, skip_page_chrome: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._skip_tags = _SKIP_TAGS | (_PAGE_CHROME_TAGS if skip_page_chrome else set())
        # True between <li> and its first text: boards wrap list items as
        # <li><p>...</p></li>, and the <p> must not push the text onto a
        # line of its own, away from its "- " bullet marker.
        self._bullet_open = False

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "li":
            self.parts.append("\n- ")
            self._bullet_open = True
        elif tag in _BLOCK_TAGS and not self._bullet_open:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in ("br", "hr") and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if not self._skip_depth and (tag in _BLOCK_TAGS or tag == "li") and not self._bullet_open:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)
            if data.strip():
                self._bullet_open = False


def html_to_text(markup: str, skip_page_chrome: bool = False) -> str:
    parser = _TextExtractor(skip_page_chrome=skip_page_chrome)
    parser.feed(markup)
    parser.close()
    lines = []
    for raw_line in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", raw_line.replace("\xa0", " ")).strip()
        if line in ("", "-"):
            continue
        lines.append(line)
    return "\n".join(lines)


# --- page structure ---------------------------------------------------------


class _PageScanner(HTMLParser):
    """One pass over the page: collects JSON-LD and app-state script bodies,
    the <title>/og: metadata, and the raw HTML of <main>/<article>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.app_state: list[str] = []
        self.title: str | None = None
        self.meta: dict[str, str] = {}
        self._script_kind: str | None = None
        self._script_buf: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attr = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script":
            # attribute values arrive entity-decoded, so HelloWork's
            # type="application/ld&#x2B;json" reads as application/ld+json
            script_type = attr.get("type", "").strip().lower()
            if script_type == "application/ld+json":
                self._script_kind = "jsonld"
            elif attr.get("id") in _APP_STATE_SCRIPT_IDS:
                self._script_kind = "app_state"
            else:
                self._script_kind = None
            self._script_buf = []
        elif tag == "title" and self.title is None:
            self._in_title = True
        elif tag == "meta":
            key = attr.get("property") or attr.get("name")
            if key and attr.get("content"):
                self.meta.setdefault(key.lower(), attr["content"].strip())

    def handle_endtag(self, tag):
        if tag == "script" and self._script_kind:
            target = self.jsonld if self._script_kind == "jsonld" else self.app_state
            target.append("".join(self._script_buf))
            self._script_kind = None
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._script_kind:
            self._script_buf.append(data)
        elif self._in_title:
            self.title = ((self.title or "") + data).strip() or None


def _iter_json_objects(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_json_objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_json_objects(value)


def _is_job_posting(obj: dict) -> bool:
    kind = obj.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(isinstance(k, str) and k.lower() == "jobposting" for k in kinds)


def _description_to_text(description: str) -> str:
    # Some boards double-escape the HTML inside JSON-LD ("&lt;p&gt;...").
    if "<" not in description and "&lt;" in description:
        description = html_lib.unescape(description)
    return html_to_text(description)


def _org_name(org) -> str | None:
    if isinstance(org, dict):
        name = org.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
    if isinstance(org, str) and org.strip():
        return org.strip()
    return None


def _from_jsonld(scripts: list[str]) -> tuple[str | None, str | None, str] | None:
    for raw in scripts:
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in _iter_json_objects(data):
            if not _is_job_posting(obj) or not isinstance(obj.get("description"), str):
                continue
            body = _description_to_text(obj["description"])
            if len(body.split()) < MIN_DESCRIPTION_WORDS:
                continue
            title = obj.get("title") if isinstance(obj.get("title"), str) else None
            text = f"{title.strip()}\n{body}" if title and title.strip() else body
            return (title.strip() if title else None), _org_name(obj.get("hiringOrganization")), text
    return None


def _from_app_state(scripts: list[str]) -> str | None:
    chunks: list[str] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}".lower())
        elif isinstance(node, list):
            for value in node:
                walk(value, path)
        elif isinstance(node, str) and _HTML_TAG_RE.search(node):
            if "i18n" in path or not any(hint in path for hint in _APP_STATE_KEY_HINTS):
                return
            text = html_to_text(node)
            if len(text) >= MIN_APP_STATE_CHARS and text not in chunks:
                chunks.append(text)

    for raw in scripts:
        try:
            walk(json.loads(raw.strip()), "")
        except (json.JSONDecodeError, ValueError):
            continue
    return "\n\n".join(chunks) if chunks else None


def _from_page_text(page_html: str) -> str | None:
    match = re.search(r"<(main|article)\b.*?</\1>", page_html, re.IGNORECASE | re.DOTALL)
    text = html_to_text(match.group(0) if match else page_html, skip_page_chrome=True)
    return text if len(text.split()) >= MIN_PAGE_TEXT_WORDS else None


# Job boards often keep serving an expired posting's URL with 200 and a
# notice plus a list of other jobs. Only the top of the page is checked, so a
# phrase further down in a real posting can't trigger it.
_EXPIRED_NOTICE = re.compile(
    r"nicht mehr (?:verfügbar|online|aktiv|besetzbar)|bereits besetzt"
    r"|no longer (?:available|accepting applications|active|open)"
    r"|(?:position|job|posting|role) (?:has been filled|is closed|has expired)"
    r"|n'est plus disponible|plus disponible|offre (?:a )?expirée",
    re.IGNORECASE,
)
EXPIRED_NOTICE_WINDOW = 1500


def _looks_expired(text: str) -> bool:
    return bool(_EXPIRED_NOTICE.search(text[:EXPIRED_NOTICE_WINDOW]))


def _split_page_title(page_title: str | None, site_name: str | None) -> tuple[str | None, str | None]:
    """Page titles of non-JSON-LD boards usually read "Job title | Company
    Careers" while og:site_name names the ATS vendor (e.g. "Rippling
    Recruiting"), so the company is taken from the title's suffix when
    there is one."""
    if not page_title or " | " not in page_title:
        return page_title, site_name
    title, _, suffix = page_title.partition(" | ")
    company = re.sub(r"\s+(careers|jobs|karriere|stellenangebote)$", "", suffix.strip(), flags=re.IGNORECASE)
    return title.strip() or page_title, company or site_name


def extract_posting(page_html: str) -> tuple[str | None, str | None, str, str]:
    """Returns (title, company, method, text) or raises
    PostingFetchError("unreadable")."""
    scanner = _PageScanner()
    scanner.feed(page_html)
    scanner.close()

    from_jsonld = _from_jsonld(scanner.jsonld)
    if from_jsonld:
        title, company, text = from_jsonld
        return title, company, "jsonld", text

    page_title, site_name = _split_page_title(
        scanner.meta.get("og:title") or scanner.title, scanner.meta.get("og:site_name")
    )

    app_text = _from_app_state(scanner.app_state)
    if app_text and _looks_expired(app_text):
        raise PostingFetchError("gone")
    if app_text:
        text = f"{page_title}\n{app_text}" if page_title else app_text
        return page_title, site_name, "app_state", text

    page_text = _from_page_text(page_html)
    if page_text and _looks_expired(page_text):
        raise PostingFetchError("gone")
    if page_text:
        return page_title, site_name, "page_text", page_text

    raise PostingFetchError("unreadable")


# --- safe fetching ----------------------------------------------------------

Resolver = Callable[[str, int], list[str]]


def _system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _validate_url(url: str, resolver: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PostingFetchError("unsafe_url")
    if parts.username or parts.password:
        raise PostingFetchError("unsafe_url")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise PostingFetchError("unsafe_url") from exc
    if port not in (80, 443):
        raise PostingFetchError("unsafe_url")
    try:
        addresses = resolver(parts.hostname, port)
    except (OSError, UnicodeError) as exc:
        raise PostingFetchError("unreachable") from exc
    if not addresses:
        raise PostingFetchError("unreachable")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified or not ip.is_global
        ):
            raise PostingFetchError("unsafe_url")


def fetch_html(
    url: str,
    resolver: Resolver = _system_resolver,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, str]:
    """GETs `url` with SSRF protection, following up to MAX_REDIRECTS
    redirects by hand so every hop is re-validated. Returns (final_url,
    html)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en,de;q=0.9,fr;q=0.8",
    }
    with httpx.Client(
        follow_redirects=False, timeout=TIMEOUT_SECONDS, headers=headers, transport=transport
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_url(url, resolver)
            try:
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise PostingFetchError("unreachable")
                        url = urljoin(url, location)
                        continue
                    if response.status_code in (404, 410):
                        raise PostingFetchError("gone", f"HTTP {response.status_code}")
                    if response.status_code >= 400:
                        raise PostingFetchError("unreachable", f"HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and "html" not in content_type:
                        raise PostingFetchError("not_html")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise PostingFetchError("too_large")
                    encoding = response.encoding or "utf-8"
                    return url, bytes(body).decode(encoding, errors="replace")
            except httpx.TimeoutException as exc:
                raise PostingFetchError("timeout") from exc
            except httpx.HTTPError as exc:
                raise PostingFetchError("unreachable") from exc
    raise PostingFetchError("unreachable", "too many redirects")


def _redirected_to_overview(url: str, final_url: str) -> bool:
    """True when a redirect led from a job page up to one of its parent
    paths on the same host (e.g. /acme/jobs/123 -> /acme). Job boards do this
    when a posting has expired, and answer with 200 and the list of other
    jobs."""
    start, end = urlsplit(url), urlsplit(final_url)
    if start.hostname != end.hostname:
        return False
    start_path, end_path = start.path.rstrip("/"), end.path.rstrip("/")
    return start_path != end_path and (start_path + "/").startswith(end_path + "/")

def fetch_posting(
    url: str,
    resolver: Resolver = _system_resolver,
    transport: httpx.BaseTransport | None = None,
) -> PostingSource:
    url = url.strip()
    final_url, page_html = fetch_html(url, resolver=resolver, transport=transport)
    if _redirected_to_overview(url, final_url):
        raise PostingFetchError("gone", "redirected to overview")
    title, company, method, text = extract_posting(page_html)
    return PostingSource(
        url=final_url,
        host=urlsplit(final_url).hostname or "",
        title=title,
        company=company,
        method=method,
        text=text,
    )
