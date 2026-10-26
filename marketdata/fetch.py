"""HTTP 받기. 표준 라이브러리만 쓰고, 실패하면 몇 번 다시 시도한다."""
import time
import urllib.error
import urllib.request
from typing import Callable

# 기본은 이 저장소를 밝히는 평범한 헤더다. FRED는 브라우저처럼 꾸민 요청을 끊는다(2026-10-26 확인).
DEFAULT_HEADERS = {"User-Agent": "marketdata/0.1 (+https://github.com/iamsam120/market-data)", "Accept": "*/*"}
# CNN은 브라우저 헤더가 없으면 418을 돌려준다(기술검증 T-04).
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

Fetch = Callable[[str, dict[str, str] | None], str]


def http_get(url: str, headers: dict[str, str] | None = None, retries: int = 3, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"받기 실패 {url}: {last}")
