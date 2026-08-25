"""Tests for CopyManga API client."""

import pytest
import httpx
from copy2mihon.client import CopyMangaClient, normalize_base_url


def test_normalize_base_url():
    assert normalize_base_url("copymanga.tv") == "https://copymanga.tv"
    assert normalize_base_url("http://copymanga.site/") == "http://copymanga.site"
    assert normalize_base_url("  https://www.mangacopy.com/  ") == "https://www.mangacopy.com"
    assert normalize_base_url("") == "https://www.mangacopy.com"
    assert normalize_base_url(None) == "https://www.mangacopy.com"


def test_client_init_headers():
    client = CopyMangaClient(token="Token sample_token_123", base_url="api.mangacopy.com")
    assert client.token == "sample_token_123"
    assert client.base_url == "https://api.mangacopy.com"
    assert client.client.headers["authorization"] == "Token sample_token_123"
    assert client.client.headers["platform"] == "2"


def test_client_fetch_all_collected_comics_pagination(monkeypatch):
    client = CopyMangaClient(token="test_token")

    def mock_get(endpoint, params=None):
        offset = params.get("offset", 0) if params else 0
        if offset == 0:
            return httpx.Response(
                status_code=200,
                json={
                    "code": 200,
                    "results": {
                        "list": [{"comic": {"name": "Comic 1", "path_word": "c1"}}],
                        "total": 2,
                    },
                },
                request=httpx.Request("GET", endpoint),
            )
        else:
            return httpx.Response(
                status_code=200,
                json={
                    "code": 200,
                    "results": {
                        "list": [{"comic": {"name": "Comic 2", "path_word": "c2"}}],
                        "total": 2,
                    },
                },
                request=httpx.Request("GET", endpoint),
            )

    monkeypatch.setattr(client.client, "get", mock_get)

    results = client.fetch_all_collected_comics(page_size=1, delay_seconds=0)
    assert len(results) == 2
    assert results[0]["comic"]["name"] == "Comic 1"
    assert results[1]["comic"]["name"] == "Comic 2"


def test_client_fetch_all_browse_history_pagination(monkeypatch):
    client = CopyMangaClient(token="test_token")

    def mock_get(endpoint, params=None):
        return httpx.Response(
            status_code=200,
            json={
                "code": 200,
                "results": {
                    "list": [
                        {
                            "comic": {"name": "History Comic 1", "path_word": "hc1"},
                            "last_chapter_id": "uuid-1",
                            "last_chapter_name": "第1话",
                        }
                    ],
                    "total": 1,
                },
            },
            request=httpx.Request("GET", endpoint),
        )

    monkeypatch.setattr(client.client, "get", mock_get)

    results = client.fetch_all_browse_history(page_size=10, delay_seconds=0)
    assert len(results) == 1
    assert results[0]["comic"]["name"] == "History Comic 1"


def test_client_unauthorized_error_non_retryable(monkeypatch):
    client = CopyMangaClient(token="invalid_token")
    call_count = 0

    def mock_get(endpoint, params=None):
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=401,
            json={"code": 401, "message": "Invalid token"},
            request=httpx.Request("GET", endpoint),
        )

    monkeypatch.setattr(client.client, "get", mock_get)

    with pytest.raises(PermissionError):
        client.get_collect_comics_page()

    # 401 should NOT be retried (fail fast)
    assert call_count == 1


def test_client_bad_request_error_non_retryable(monkeypatch):
    client = CopyMangaClient(token="valid_token")
    call_count = 0

    def mock_get(endpoint, params=None):
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=400,
            text="Bad Request: invalid offset",
            request=httpx.Request("GET", endpoint),
        )

    monkeypatch.setattr(client.client, "get", mock_get)

    with pytest.raises(RuntimeError) as exc_info:
        client.get_collect_comics_page()

    assert "Client Error (400)" in str(exc_info.value)
    # 400 should NOT be retried (fail fast)
    assert call_count == 1


def test_client_server_error_retry_success(monkeypatch):
    client = CopyMangaClient(token="valid_token", max_retries=3)
    call_count = 0

    def mock_get(endpoint, params=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(
                status_code=502,
                request=httpx.Request("GET", endpoint),
            )
        return httpx.Response(
            status_code=200,
            json={"code": 200, "results": {"list": [], "total": 0}},
            request=httpx.Request("GET", endpoint),
        )

    monkeypatch.setattr(client.client, "get", mock_get)

    res = client.get_collect_comics_page()
    assert res["code"] == 200
    assert call_count == 3
