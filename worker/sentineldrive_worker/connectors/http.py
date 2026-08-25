from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping

from sentineldrive_worker.connectors.contracts import ConnectorError


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        charset = "utf-8"
        content_type = self.headers.get("content-type") or self.headers.get("Content-Type") or ""
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                charset = part.split("=", 1)[1].strip() or charset
        return self.body.decode(charset, errors="replace")


class HttpClient:
    def get(
        self,
        url: str,
        *,
        query: Mapping[str, object | None] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse:
        request_url = build_url(url, query)
        request = urllib.request.Request(request_url, headers=dict(headers or {}), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    url=response.geturl(),
                    status_code=response.status,
                    headers={key: value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            return HttpResponse(
                url=exc.geturl(),
                status_code=exc.code,
                headers={key: value for key, value in exc.headers.items()},
                body=body,
            )
        except urllib.error.URLError as exc:
            raise ConnectorError(f"HTTP 请求失败（{request_url}）：{exc.reason}") from exc


def build_url(url: str, query: Mapping[str, object | None] | None = None) -> str:
    if not query:
        return url
    filtered = {key: value for key, value in query.items() if value is not None}
    separator = "&" if urllib.parse.urlparse(url).query else "?"
    return f"{url}{separator}{urllib.parse.urlencode(filtered)}"
