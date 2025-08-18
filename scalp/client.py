import logging
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTTPError(RuntimeError):
    """Raised when an HTTP request fails"""


class HttpClient:
    """Simple HTTP client with persistent session and retry logic."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.3,
        status_forcelist: Optional[list[int]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or [429, 500, 502, 503, 504],
            allowed_methods=[
                "HEAD",
                "GET",
                "OPTIONS",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
            ],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP request and return JSON data.

        Errors during the request raise ``HTTPError``. If the response cannot
        be decoded as JSON, a dictionary describing the issue is returned.
        """
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:  # network or HTTP errors
            msg = f"HTTP error calling {url}: {exc}"
            logging.error(msg)
            raise HTTPError(msg) from exc

        try:
            return resp.json()
        except ValueError as exc:  # invalid JSON
            msg = "Invalid JSON in response"
            logging.error("%s for %s: %s", msg, url, resp.text)
            return {"success": False, "error": msg, "text": resp.text}
