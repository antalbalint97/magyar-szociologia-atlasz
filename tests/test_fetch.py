"""Why a host was not crawled: the refusal message keeps three different facts apart (#12).

A site that disallows a page, a robots.txt that answers an error and a robots.txt that cannot be reached all
make the fetcher refuse, but they mean different things for coverage. No network: a mock transport answers.
"""

import httpx
import pytest

from szocatlas.fetch import FetchRefused, PoliteFetcher, RawStore
from szocatlas.models.enums import SourceType
from szocatlas.registry import CrawlPolicy

PAGE = "https://example.tk.elte.hu/some-page"


def fetcher(tmp_path, handler) -> PoliteFetcher:
    f = PoliteFetcher(RawStore(tmp_path), CrawlPolicy(min_delay_seconds=0.0), aliases={})
    f.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return f


def refusal(tmp_path, handler) -> str:
    f = fetcher(tmp_path, handler)
    with pytest.raises(FetchRefused) as e:
        f.get(PAGE, source_id="s", source_type=SourceType.PROJECT_PAGE)
    return str(e.value)


def test_a_page_the_site_disallows_says_so(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /some-page\n")
        return httpx.Response(200, text="<html></html>")

    assert refusal(tmp_path, handler) == f"robots.txt disallows {PAGE}"


def test_a_robots_txt_that_answers_a_server_error_is_not_called_a_disallow(tmp_path):
    def handler(request):
        return httpx.Response(500 if request.url.path == "/robots.txt" else 200, text="")

    msg = refusal(tmp_path, handler)
    assert "HTTP 500" in msg and "host not crawled" in msg and "disallows" not in msg


def test_a_robots_txt_that_cannot_be_reached_is_not_called_a_disallow(tmp_path):
    def handler(request):
        raise httpx.ConnectError("blocked", request=request)

    msg = refusal(tmp_path, handler)
    assert "unreachable" in msg and "ConnectError" in msg and "disallows" not in msg


def test_the_reason_holds_for_every_later_page_of_that_host(tmp_path):
    def handler(request):
        return httpx.Response(503 if request.url.path == "/robots.txt" else 200, text="")

    f = fetcher(tmp_path, handler)
    for url in (PAGE, PAGE + "-2"):
        with pytest.raises(FetchRefused, match="HTTP 503"):
            f.get(url, source_id="s", source_type=SourceType.PROJECT_PAGE)


def test_a_missing_robots_txt_allows_the_host(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="")
        return httpx.Response(200, text="<html><title>x</title></html>")

    f = fetcher(tmp_path, handler)
    page = f.get(PAGE, source_id="s", source_type=SourceType.PROJECT_PAGE)
    assert page.document.http_status == 200
