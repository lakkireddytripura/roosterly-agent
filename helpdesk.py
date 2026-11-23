"""Thin helpdesk client: rate limit, 429/503 retry, 409 handling. Keys come from the environment."""
import os
import random
import time

import requests


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"{status}: {body[:300]}")
        self.status, self.body = status, body


class AlreadyHandled(Exception):
    pass


class Helpdesk:
    MIN_INTERVAL = 0.25  # 4 requests/second, below the 5/s limit

    def __init__(self):
        self.base = os.environ["HELPDESK_URL"].rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {os.environ['HELPDESK_KEY']}",
            "X-Candidate-Email": os.environ["HELPDESK_EMAIL"],
        })
        if os.environ.get("HELPDESK_NAME"):
            self.s.headers["X-Candidate-Name"] = os.environ["HELPDESK_NAME"]
        self._last = 0.0

    def _throttle(self):
        wait = self.MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def call(self, method, path, json=None, params=None, tries=8):
        for attempt in range(tries):
            self._throttle()
            try:
                r = self.s.request(method, self.base + path, json=json, params=params, timeout=20)
            except requests.RequestException:
                time.sleep(min(0.5 * 2 ** attempt, 8))
                continue
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 1)) + 0.1)
                continue
            if r.status_code == 503:  # nothing was saved, safe to retry
                time.sleep(min(0.5 * 2 ** attempt, 8) + random.random() * 0.3)
                continue
            if r.status_code == 409:
                raise AlreadyHandled(r.text)
            if r.status_code >= 400:
                raise ApiError(r.status_code, r.text)
            return r.json()
        raise ApiError(503, "retries exhausted")

    def pages(self, path, key_names, params=None):
        """Yield all items across pages, following next_cursor."""
        params = dict(params or {}, limit=10)
        while True:
            data = self.call("GET", path, params=params)
            yield from items(data, key_names)
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor:
                return
            params["cursor"] = cursor


def items(data, key_names=("tickets", "items", "examples", "data")):
    if isinstance(data, list):
        return data
    for k in key_names:
        if isinstance(data.get(k), list):
            return data[k]
    raise ValueError(f"Cannot find a list in response keys: {list(data)}")
