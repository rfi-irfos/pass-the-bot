"""Tests for reading a job posting from a pasted link (GitHub issue #4).
No network: pages are served by httpx.MockTransport and DNS is a fake
resolver, so the SSRF checks are exercised deterministically in CI."""

import httpx
import pytest

from app.fetch_posting import (
    MAX_RESPONSE_BYTES,
    PostingFetchError,
    extract_posting,
    fetch_posting,
    html_to_text,
    looks_like_url,
)

PUBLIC_IP = "93.184.216.34"

REQUIREMENTS_HTML = (
    "<h2>Requirements</h2><ul>"
    + "".join(f"<li><p>Requirement number {i} with Python and SQL experience</p></li>" for i in range(8))
    + "</ul>"
)


def _public_resolver(host, port):
    return [PUBLIC_IP]


def _transport(pages: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return pages.get(str(request.url), httpx.Response(404))

    return httpx.MockTransport(handler)


def _html(body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> httpx.Response:
    return httpx.Response(status, headers={"content-type": content_type}, text=body)


# --- looks_like_url ---------------------------------------------------------


def test_looks_like_url_accepts_a_single_link_with_whitespace():
    assert looks_like_url("  https://jobs.example.com/123?ref=x \n")


def test_looks_like_url_rejects_posting_text_containing_a_link():
    assert not looks_like_url("We hire! Apply at https://jobs.example.com/123")
    assert not looks_like_url("ftp://example.com/job")


# --- html_to_text -----------------------------------------------------------


def test_html_to_text_turns_list_items_into_bullet_lines():
    text = html_to_text("<h2>Requirements</h2><ul><li><p>Python</p></li><li>SQL</li></ul><p>Done</p>")
    assert text.splitlines() == ["Requirements", "- Python", "- SQL", "Done"]


def test_html_to_text_skips_scripts_and_decodes_entities():
    text = html_to_text("<p>R&amp;D&nbsp;team</p><script>var x = 1;</script>")
    assert text == "R&D team"


# --- extraction tiers ---------------------------------------------------------


def test_extracts_jsonld_job_posting_with_entity_encoded_script_type():
    """HelloWork writes type="application/ld&#x2B;json"; a regex on the raw
    attribute would miss it."""
    page = (
        '<html><script type="application/ld&#x2B;json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Data Analyst",'
        '"hiringOrganization":{"@type":"Organization","name":"ACME"},'
        f'"description":{_json_str(REQUIREMENTS_HTML)}}}'
        "</script></html>"
    )
    title, company, method, text = extract_posting(page)
    assert (title, company, method) == ("Data Analyst", "ACME", "jsonld")
    assert text.startswith("Data Analyst\nRequirements\n- Requirement number 0")


def test_extracts_jsonld_job_posting_nested_in_graph():
    page = (
        '<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},'
        f'{{"@type":"JobPosting","title":"Nurse","description":{_json_str(REQUIREMENTS_HTML)}}}]}}'
        "</script>"
    )
    title, _, method, _ = extract_posting(page)
    assert (title, method) == ("Nurse", "jsonld")


def test_extracts_posting_from_next_data_and_ignores_i18n_strings():
    """Rippling: no JSON-LD, the posting is an HTML string in __NEXT_DATA__
    next to UI translation strings that must not leak into the posting."""
    import json

    data = {
        "props": {
            "pageProps": {
                "_nextI18Next": {"store": {"tips": "<p>" + "Record your video in a quiet room. " * 20 + "</p>"}},
                "apiData": {"jobPost": {"description": {"role": REQUIREMENTS_HTML}}},
            }
        }
    }
    page = (
        "<html><head><title>Marketing Manager | Camlin Careers</title>"
        '<meta property="og:site_name" content="Rippling Recruiting"></head>'
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'
    )
    title, company, method, text = extract_posting(page)
    assert (title, company, method) == ("Marketing Manager", "Camlin", "app_state")
    assert "- Requirement number 3" in text
    assert "quiet room" not in text


def test_falls_back_to_visible_page_text_without_navigation():
    words = " ".join(f"word{i}" for i in range(200))
    page = f"<html><nav>Home Jobs Login</nav><main><h1>Welder</h1><p>{words}</p></main></html>"
    title, _, method, text = extract_posting(page)
    assert method == "page_text"
    assert text.startswith("Welder\nword0")
    assert "Login" not in text


def test_page_text_drops_link_lists_of_other_jobs():
    """Greenhouse (Gong): below a sales posting sat a table of links to
    every other open job, which turned "Senior Backend Engineer (Python)"
    into a Python requirement for an Account Executive."""
    words = " ".join(f"word{i}" for i in range(200))
    others = "".join(
        f'<tr><td><a href="/jobs/{i}"><p>Senior Backend Engineer (Python)</p></a></td></tr>'
        for i in range(5)
    )
    page = f"<html><main><h1>Account Executive</h1><p>{words}</p><table>{others}</table></main></html>"
    _, _, method, text = extract_posting(page)
    assert method == "page_text"
    assert "Python" not in text


def test_js_only_page_is_unreadable():
    """Brown-Forman: an empty Nuxt shell with no posting content."""
    page = '<html><body><div id="__nuxt"></div><script>window.__NUXT__={}</script></body></html>'
    with pytest.raises(PostingFetchError) as exc:
        extract_posting(page)
    assert exc.value.code == "unreadable"


# --- fetching + SSRF ------------------------------------------------------------


def test_fetch_posting_follows_a_redirect_and_reports_the_source():
    page = f'<script type="application/ld+json">{{"@type":"JobPosting","title":"Cook","description":{_json_str(REQUIREMENTS_HTML)}}}</script>'
    transport = _transport({
        "https://jobs.example.com/a": httpx.Response(302, headers={"location": "/b"}),
        "https://jobs.example.com/b": _html(page),
    })
    source = fetch_posting("https://jobs.example.com/a", resolver=_public_resolver, transport=transport)
    assert source.url == "https://jobs.example.com/b"
    assert source.host == "jobs.example.com"
    assert source.method == "jsonld"
    assert source.to_dict()["chars"] == len(source.text)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "fdaa::1", "::ffff:192.168.0.1"])
def test_rejects_hosts_resolving_to_non_public_addresses(address):
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://internal.example.com/job", resolver=lambda h, p: [address], transport=_transport({}))
    assert exc.value.code == "unsafe_url"


@pytest.mark.parametrize("url", ["https://user:pw@jobs.example.com/", "https://jobs.example.com:8080/", "file:///etc/passwd"])
def test_rejects_credentials_odd_ports_and_non_http_schemes(url):
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting(url, resolver=_public_resolver, transport=_transport({}))
    assert exc.value.code == "unsafe_url"


def test_rejects_redirect_to_a_private_address():
    def resolver(host, port):
        return ["10.0.0.1"] if host == "evil.internal" else [PUBLIC_IP]

    transport = _transport({"https://jobs.example.com/a": httpx.Response(302, headers={"location": "http://evil.internal/"})})
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://jobs.example.com/a", resolver=resolver, transport=transport)
    assert exc.value.code == "unsafe_url"


def test_rejects_oversized_and_non_html_responses():
    big = _html("x" * (MAX_RESPONSE_BYTES + 1))
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://jobs.example.com/big", resolver=_public_resolver, transport=_transport({"https://jobs.example.com/big": big}))
    assert exc.value.code == "too_large"

    pdf = _html("%PDF", content_type="application/pdf")
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://jobs.example.com/pdf", resolver=_public_resolver, transport=_transport({"https://jobs.example.com/pdf": pdf}))
    assert exc.value.code == "not_html"


def test_missing_or_removed_posting_is_gone():
    for status in (404, 410):
        transport = _transport({"https://jobs.example.com/old": _html("gone", status=status)})
        with pytest.raises(PostingFetchError) as exc:
            fetch_posting("https://jobs.example.com/old", resolver=_public_resolver, transport=transport)
        assert exc.value.code == "gone"


def test_redirect_from_a_job_to_its_board_overview_is_gone():
    """Greenhouse sends an expired job's URL to the company's job list
    (/gongio/jobs/123 -> /gongio?error=true) with status 200."""
    words = " ".join(f"word{i}" for i in range(200))
    transport = _transport({
        "https://boards.example.com/acme/jobs/123": httpx.Response(
            302, headers={"location": "/acme?error=true"}
        ),
        "https://boards.example.com/acme?error=true": _html(f"<main><p>{words}</p></main>"),
    })
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://boards.example.com/acme/jobs/123", resolver=_public_resolver, transport=transport)
    assert exc.value.code == "gone"


def test_redirect_to_a_longer_path_is_followed_normally():
    transport = _transport({
        "https://jobs.example.com/jobs/123": httpx.Response(
            301, headers={"location": "/de/jobs/123-buchhalter"}
        ),
        "https://jobs.example.com/de/jobs/123-buchhalter": _html(
            f"<main><p>{' '.join(f'word{i}' for i in range(200))}</p>{REQUIREMENTS_HTML}</main>"
        ),
    })
    source = fetch_posting("https://jobs.example.com/jobs/123", resolver=_public_resolver, transport=transport)
    assert "Requirement number 3" in source.text

def test_other_http_error_status_is_unreachable():
    transport = _transport({"https://jobs.example.com/err": _html("oops", status=500)})
    with pytest.raises(PostingFetchError) as exc:
        fetch_posting("https://jobs.example.com/err", resolver=_public_resolver, transport=transport)
    assert exc.value.code == "unreachable"


def test_expired_notice_on_a_listing_page_is_gone():
    others = "".join(f"<li>Other job {i} with a long description of duties and tasks here</li>" for i in range(40))
    page = (
        "<main><h1>118 Buchhalter Jobs</h1><p>Der Job Buchhalter bei der Firma X ist leider "
        f"nicht mehr verfügbar.</p><ul>{others}</ul></main>"
    )
    with pytest.raises(PostingFetchError) as exc:
        extract_posting(page)
    assert exc.value.code == "gone"


def test_expired_phrase_deep_inside_a_real_posting_is_ignored():
    filler = " ".join(["Wir suchen eine engagierte Person für unser Team in Graz."] * 40)
    page = f"<main><h1>Buchhalter</h1><p>{filler}</p><p>Alte Stellen sind nicht mehr verfügbar.</p></main>"
    _, _, method, _ = extract_posting(page)
    assert method == "page_text"


def _json_str(value: str) -> str:
    import json

    return json.dumps(value)
