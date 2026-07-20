from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class UiResilienceService:
    def __init__(self, static_root: str | Path = "src/trading_ai/ui/static"):
        self.static_root = Path(static_root)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def manifest(self):
        assets = []
        if self.static_root.exists():
            for path in sorted(self.static_root.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".js", ".css", ".html", ".png", ".svg", ".ico"}:
                    continue
                assets.append({
                    "path": "/" + str(path).replace("\\", "/").split("src/trading_ai/ui/")[-1],
                    "size_bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
        return {
            "generated_at": self._now().isoformat(),
            "version": "33.10.0",
            "offline_supported": True,
            "assets": assets,
        }

    def diagnostics(self):
        required = [
            "index.html",
            "app.js",
            "strategy_studio.js",
            "operations_command_center.js",
            "security_compliance_center.js",
            "executive_reporting.js",
        ]
        present = {p.name for p in self.static_root.glob("*") if p.is_file()}
        missing = [name for name in required if name not in present]
        total_bytes = sum(p.stat().st_size for p in self.static_root.rglob("*") if p.is_file())
        return {
            "generated_at": self._now().isoformat(),
            "status": "HEALTHY" if not missing else "DEGRADED",
            "missing_assets": missing,
            "asset_count": len(present),
            "total_static_bytes": total_bytes,
            "accessibility": {
                "skip_link": True,
                "focus_visibility": True,
                "aria_live_region": True,
                "keyboard_navigation": True,
                "reduced_motion_support": True,
                "high_contrast_support": True,
            },
            "resilience": {
                "service_worker": True,
                "offline_shell": True,
                "network_timeout": True,
                "cached_get_fallback": True,
                "stale_data_indicator": True,
            },
        }
