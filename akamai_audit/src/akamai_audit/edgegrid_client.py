from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests
from akamai.edgegrid import EdgeGridAuth, EdgeRc
from requests.exceptions import RequestException


@dataclass
class EdgeGridClient:
    base_url: str
    session: requests.Session
    account_switch_key: str

    @classmethod
    def from_edgerc(
        cls,
        edgerc_path: str,
        section: str,
        account_switch_key: str,
        timeout_seconds: int = 60,
    ) -> "EdgeGridClient":
        rc = EdgeRc(edgerc_path)
        host = rc.get(section, "host")

        session = requests.Session()
        session.auth = EdgeGridAuth.from_edgerc(rc, section)
        session.headers.update({"Accept": "application/json"})
        session.request = _with_timeout(session.request, timeout_seconds)

        return cls(base_url=f"https://{host}", session=session, account_switch_key=account_switch_key)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = self._with_account_switch_key(params)
        return self._request_with_retry(
            method="GET",
            url=f"{self.base_url}{path}",
            params=query,
        )

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> Any:
        query = self._with_account_switch_key(params)
        return self._request_with_retry(
            method="POST",
            url=f"{self.base_url}{path}",
            params=query,
            json=payload,
        )

    def _with_account_switch_key(self, params: dict[str, Any] | None) -> dict[str, Any]:
        query = dict(params or {})
        query.setdefault("accountSwitchKey", self.account_switch_key)
        return query

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> Any:
        backoff_factor = 1.0
        attempt = 0

        while attempt < max_retries:
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"Rate limited (429). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    attempt += 1
                    continue

                response.raise_for_status()
                return response.json() if response.text else {}
            except RequestException as e:
                if response.status_code >= 500:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"Server error ({response.status_code}). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    attempt += 1
                    continue
                raise

        raise RequestException(f"Max retries ({max_retries}) exceeded for {method} {url}")


def _with_timeout(request_func, timeout_seconds: int):
    def wrapped(method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", timeout_seconds)
        return request_func(method, url, **kwargs)

    return wrapped
