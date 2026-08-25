"""CopyManga API client for fetching bookshelf subscriptions and reading history using Token authentication."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional
import httpx

from copy2mihon.parser import extract_token

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get("COPYMANGA_BASE_URL", "https://www.mangacopy.com")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

KNOWN_DOMAINS = [
    "https://www.mangacopy.com",
    "https://www.copy4000.com",
    "https://2026copy.com",
    "https://api.mangacopy.com",
    "https://www.copymanga.site",
    "https://www.copymanga.tv",
    "https://api.copymanga.org",
    "https://copymanga.com",
]


def normalize_base_url(url: Optional[str]) -> str:
    """Normalize base URL with scheme and trimmed slashes."""
    if not url:
        return DEFAULT_BASE_URL
    clean = url.strip().rstrip("/")
    if not clean:
        return DEFAULT_BASE_URL
    if not (clean.startswith("http://") or clean.startswith("https://")):
        clean = f"https://{clean}"
    return clean


class CopyMangaClient:
    """HTTP client for CopyManga API with Token authentication and resilient retry handling."""

    def __init__(
        self,
        token: str,
        base_url: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.token = extract_token(token)
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self._init_client()

    def _init_client(self) -> None:
        """Initialize or recreate the httpx client."""
        req_headers = {
            "user-agent": DEFAULT_USER_AGENT,
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "platform": "2",
            "authorization": f"Token {self.token}",
        }
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=req_headers,
            proxy=self.proxy,
            timeout=self.timeout,
            follow_redirects=True,
        )

    def set_token(self, token: str) -> None:
        """Update authorization token."""
        self.token = extract_token(token)
        self.client.headers["authorization"] = f"Token {self.token}"

    def _get_with_retry(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform a GET request, retrying only on network drops, timeouts, 429s, or 5xx server errors."""
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.get(endpoint, params=params)

                # 1. Deterministic Non-Retryable Client Errors (401, 403, 404)
                if resp.status_code == 401:
                    raise PermissionError("Unauthorized (401): 拷贝漫画 Token 无效或已过期。")
                if resp.status_code == 403:
                    raise PermissionError(f"Forbidden (403): 访问被拒绝，请检查 Token 或 IP 限制。")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Not Found (404): 接口不存在: {endpoint}")

                # 2. Rate limiting (429) -> Retry with Retry-After header
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    sleep_sec = float(retry_after) if retry_after and retry_after.isdigit() else attempt * 2.0
                    logger.warning(f"Rate limited (429). Sleeping {sleep_sec}s before retry ({attempt}/{self.max_retries})...")
                    time.sleep(sleep_sec)
                    continue

                # 3. Server Errors (5xx) -> Retry with backoff
                if resp.status_code in (500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"Server Error ({resp.status_code})",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()

                # Parse JSON payload
                try:
                    data = json.loads(resp.content.decode("utf-8"))
                except Exception:
                    data = resp.json()

                # 4. API Business-Level Error Handling (Deterministic, do not retry unless transient)
                if isinstance(data, dict) and data.get("code") != 200 and data.get("code") is not None:
                    code = data.get("code")
                    msg = data.get("message", "Unknown error")
                    if code == 401:
                        raise PermissionError(f"Unauthorized (401): {msg}")
                    # Business error (e.g. invalid parameter) -> Raise directly without retrying
                    raise RuntimeError(f"API Error ({code}): {msg}")

                return data

            except (PermissionError, FileNotFoundError, RuntimeError):
                # Non-retryable errors -> Re-raise immediately
                raise

            except (httpx.TransportError, httpx.NetworkError, httpx.RemoteProtocolError) as net_err:
                # Connection dropped / TCP reset -> Recreate connection pool and backoff
                last_exception = net_err
                logger.warning(
                    f"Network error on {endpoint} ({attempt}/{self.max_retries}): {net_err}. Reconnecting..."
                )
                if attempt < self.max_retries:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self._init_client()
                    time.sleep(min(attempt * 1.5, 6.0))

            except httpx.TimeoutException as timeout_err:
                # Timeout -> Wait and retry without rebuilding client
                last_exception = timeout_err
                logger.warning(
                    f"Timeout on {endpoint} ({attempt}/{self.max_retries}): {timeout_err}. Retrying..."
                )
                if attempt < self.max_retries:
                    time.sleep(min(attempt * 1.5, 6.0))

            except httpx.HTTPStatusError as http_err:
                # 5xx Server errors -> Wait and retry
                last_exception = http_err
                logger.warning(
                    f"HTTP status error on {endpoint} ({attempt}/{self.max_retries}): {http_err}. Retrying..."
                )
                if attempt < self.max_retries:
                    time.sleep(min(attempt * 1.5, 6.0))

            except Exception as other_err:
                last_exception = other_err
                logger.warning(
                    f"Unexpected error on {endpoint} ({attempt}/{self.max_retries}): {other_err}."
                )
                if attempt < self.max_retries:
                    time.sleep(min(attempt * 1.5, 6.0))

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request to {endpoint} failed after {self.max_retries} attempts.")

    def _paginate(
        self,
        fetch_page_fn: Callable[[int, int], Dict[str, Any]],
        page_size: int = 50,
        delay_seconds: float = 0.2,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Generic pagination helper for CopyManga API lists."""
        all_items: List[Dict[str, Any]] = []
        offset = 0
        total: Optional[int] = None

        while True:
            data = fetch_page_fn(offset, page_size)
            results = data.get("results", {})
            if isinstance(results, dict):
                items = results.get("list", [])
                total = results.get("total", total)
            elif isinstance(results, list):
                items = results
                total = len(items) if total is None else total
            else:
                items = []

            if not items:
                break

            all_items.extend(items)

            if progress_callback:
                progress_callback(len(all_items), total or len(all_items))

            if total is not None and len(all_items) >= total:
                break

            if len(items) < page_size:
                break

            offset += len(items)
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        return all_items

    def get_collect_comics_page(
        self,
        offset: int = 0,
        limit: int = 50,
        free_type: int = 1,
        ordering: str = "-datetime_modifier",
    ) -> Dict[str, Any]:
        """Fetch a single page of collected comics."""
        endpoint = "/api/v3/member/collect/comics"
        params = {
            "limit": limit,
            "offset": offset,
            "free_type": free_type,
            "ordering": ordering,
        }
        return self._get_with_retry(endpoint, params=params)

    def fetch_all_collected_comics(
        self,
        page_size: int = 50,
        delay_seconds: float = 0.2,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Paginate and fetch all collected comics."""
        return self._paginate(
            fetch_page_fn=lambda off, lim: self.get_collect_comics_page(offset=off, limit=lim),
            page_size=page_size,
            delay_seconds=delay_seconds,
            progress_callback=progress_callback,
        )

    def get_browse_history_page(
        self,
        offset: int = 0,
        limit: int = 50,
        free_type: int = 1,
    ) -> Dict[str, Any]:
        """Fetch a single page of reading/browsing history."""
        endpoint = "/api/kb/web/browses"
        params = {
            "limit": limit,
            "offset": offset,
            "free_type": free_type,
        }
        return self._get_with_retry(endpoint, params=params)

    def fetch_all_browse_history(
        self,
        page_size: int = 50,
        delay_seconds: float = 0.2,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Paginate and fetch all browsing/reading history."""
        return self._paginate(
            fetch_page_fn=lambda off, lim: self.get_browse_history_page(offset=off, limit=lim),
            page_size=page_size,
            delay_seconds=delay_seconds,
            progress_callback=progress_callback,
        )

    def close(self) -> None:
        """Close client connection."""
        self.client.close()

    def __enter__(self) -> "CopyMangaClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
