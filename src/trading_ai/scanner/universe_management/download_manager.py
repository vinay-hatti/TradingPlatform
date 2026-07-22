from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


@dataclass(frozen=True)
class DownloadResult:
    content: bytes
    source_url: str
    fetched_at: datetime
    from_cache: bool
    warning: str = ""


class ResilientDownloadManager:
    def __init__(self, cache_dir: str | Path = "data/cache/universe", retries: int = 2,
                 timeout_seconds: int = 30, backoff_seconds: float = 1.0) -> None:
        self.cache_dir = Path(cache_dir)
        self.retries = max(0, retries)
        self.timeout_seconds = timeout_seconds
        self.backoff_seconds = max(0.0, backoff_seconds)

    def _context(self) -> ssl.SSLContext:
        if certifi is not None:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()

    def fetch(self, urls: tuple[str, ...], cache_name: str) -> DownloadResult:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / cache_name
        errors: list[str] = []
        for url in urls:
            for attempt in range(self.retries + 1):
                try:
                    request = Request(url, headers={"User-Agent": "TradingPlatform/35.1"})
                    with urlopen(request, timeout=self.timeout_seconds, context=self._context()) as response:
                        content = response.read()
                    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
                    tmp.write_bytes(content)
                    tmp.replace(cache_path)
                    return DownloadResult(content, url, datetime.now(timezone.utc), False)
                except (URLError, HTTPError, TimeoutError, ssl.SSLError) as exc:
                    errors.append(f"{url} attempt {attempt + 1}: {exc}")
                    if attempt < self.retries:
                        time.sleep(self.backoff_seconds * (attempt + 1))
        if cache_path.exists():
            return DownloadResult(
                cache_path.read_bytes(),
                str(cache_path),
                datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc),
                True,
                warning="Live download failed; cached universe source used. " + " | ".join(errors),
            )
        raise RuntimeError("All universe downloads failed and no cache exists. " + " | ".join(errors))
