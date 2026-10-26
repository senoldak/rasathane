import asyncio
import random
import time
from typing import Any, Dict, Optional
import httpx

from bioseeder.config import get_settings


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter."""

    def __init__(self, rate_hz: float):
        self.rate_hz = rate_hz
        self.capacity = max(1.0, rate_hz)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_hz)

            if self.tokens < 1.0:
                sleep_time = (1.0 - self.tokens) / self.rate_hz
                await asyncio.sleep(sleep_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0


class BaseCollector:
    """Base HTTP collector with rate limiting, retries, exponential backoff, and jitter."""

    def __init__(
        self,
        base_url: str,
        rate_limit_hz: Optional[float] = None,
        max_retries: Optional[int] = None,
        timeout_sec: Optional[float] = None,
    ):
        settings = get_settings()
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = TokenBucketRateLimiter(rate_limit_hz or settings.COLLECTOR_RATE_LIMIT_HZ)
        self.max_retries = max_retries or settings.COLLECTOR_MAX_RETRIES
        self.backoff_base = settings.COLLECTOR_BACKOFF_BASE_SEC
        self.timeout = timeout_sec or settings.COLLECTOR_TIMEOUT_SEC

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        merged_headers = {"User-Agent": "biOF/0.1.0 (Biotech Financial Intelligence)"}
        if headers:
            merged_headers.update(headers)

        last_exception = None

        for attempt in range(self.max_retries + 1):
            await self.rate_limiter.acquire()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params, headers=merged_headers)

                    if response.status_code == 200:
                        return response.json()

                    # Handle Rate Limiting (429) or Transient Server Errors (5xx)
                    if response.status_code in (429, 500, 502, 503, 504):
                        retry_after = response.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            wait_time = float(retry_after)
                        else:
                            wait_time = (self.backoff_base * (2 ** attempt)) + random.uniform(0.1, 0.5)

                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_time)
                            continue

                    response.raise_for_status()

            except httpx.HTTPStatusError as exc:
                # If 403 Forbidden, try urllib fallback (Cloudflare blocks standard httpx client fingerprints)
                if exc.response.status_code == 403:
                    try:
                        import urllib.request, urllib.parse, json
                        full_url = url
                        if params:
                            full_url += ("&" if "?" in full_url else "?") + urllib.parse.urlencode(params)
                        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                        def _sync_urllib():
                            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                                return json.loads(resp.read().decode())
                        return await asyncio.to_thread(_sync_urllib)
                    except Exception:
                        pass

                # Do not retry non-retryable client errors (4xx except 429)
                if exc.response.status_code not in (429, 500, 502, 503, 504):
                    raise exc
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = (self.backoff_base * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(wait_time)
                else:
                    raise last_exception
            except httpx.RequestError as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = (self.backoff_base * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(wait_time)
                else:
                    raise last_exception

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exception}")
