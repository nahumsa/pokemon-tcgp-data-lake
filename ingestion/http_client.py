from __future__ import annotations

import threading
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import (
    HEADERS,
    REQUEST_RETRY_ALLOWED_METHODS,
    REQUEST_RETRY_ATTEMPTS,
    REQUEST_RETRY_BACKOFF_FACTOR,
    REQUEST_RETRY_STATUS_CODES,
    REQUEST_TIMEOUT_SECONDS,
)

_THREAD_LOCAL = threading.local()
_RETRY_CONFIG = Retry(
    total=REQUEST_RETRY_ATTEMPTS,
    connect=REQUEST_RETRY_ATTEMPTS,
    read=REQUEST_RETRY_ATTEMPTS,
    status=REQUEST_RETRY_ATTEMPTS,
    backoff_factor=REQUEST_RETRY_BACKOFF_FACTOR,
    status_forcelist=REQUEST_RETRY_STATUS_CODES,
    allowed_methods=REQUEST_RETRY_ALLOWED_METHODS,
    respect_retry_after_header=True,
)


def _session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.mount("https://", HTTPAdapter(max_retries=_RETRY_CONFIG))
        _THREAD_LOCAL.session = session
    return session


def get(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)
    response = _session().get(url, **kwargs)
    response.raise_for_status()
    return response
