from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.universe_management.download_manager import ResilientDownloadManager


def main():
    with TemporaryDirectory() as directory:
        cache = Path(directory) / "sample.txt"
        cache.write_bytes(b"cached")
        manager = ResilientDownloadManager(directory, retries=0, timeout_seconds=1)
        result = manager.fetch(("https://127.0.0.1:1/unavailable",), "sample.txt")
        assert result.content == b"cached"
        assert result.from_cache is True
        assert "cached universe source used" in result.warning
    print("Step 2 cache fallback assertions passed.")

if __name__ == "__main__": main()
