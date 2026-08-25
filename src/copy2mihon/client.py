"""CopyManga API client for fetching bookshelf subscriptions and reading history using Token authentication."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import httpx

from copy2mihon.parser import extract_token

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.mangacopy.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class CopyMangaClient:
    """HTTP client for CopyManga API with Token authentication and auto-retry."""

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        proxy: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
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
        """Perform a GET request with retry on network drop or server 5xx error."""
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.get(endpoint, params=params)

                if resp.status_code == 401:
                    raise PermissionError(
                        "Unauthorized (401): Invalid or expired CopyManga token."
                    )

                if resp.status_code in (500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"Server Error ({resp.status_code})",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()

                try:
                    data = json.loads(resp.content.decode("utf-8"))
                except Exception:
                    data = resp.json()

                if isinstance(data, dict) and data.get("code") != 200 and data.get("code") is not None:
                    if data.get("code") == 401:
                        raise PermissionError(f"Unauthorized (401): {data.get('message', 'Invalid token')}")
                    raise RuntimeError(f"API Error ({data.get('code')}): {data.get('message', 'Unknown error')}")

                return data

            except PermissionError:
                raise
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Request to {endpoint} failed ({attempt}/{self.max_retries}): {e}. Retrying..."
                )
                if attempt < self.max_retries:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self._init_client()

                    backoff = min(attempt * 1.5, 6.0)
                    time.sleep(backoff)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request to {endpoint} failed after {self.max_retries} attempts.")

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
        all_items: List[Dict[str, Any]] = []
        offset = 0
        total: Optional[int] = None

        while True:
            data = self.get_collect_comics_page(offset=offset, limit=page_size)
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
        all_items: List[Dict[str, Any]] = []
        offset = 0
        total: Optional[int] = None

        while True:
            data = self.get_browse_history_page(offset=offset, limit=page_size)
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

    def close(self) -> None:
        """Close client connection."""
        self.client.close()

    def __enter__(self) -> "CopyMangaClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
