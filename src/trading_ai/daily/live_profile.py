import json
from pathlib import Path


class LiveProfileLoader:

    def __init__(
        self,
        path="reports/walkforward/live_profile.json",
    ):
        self.path = Path(path)

    def load(self):

        if not self.path.exists():
            return {
                "profile": "default",
                "min_delta": 0.0,
                "max_delta": 1.0,
                "min_vega": 0.0,
                "max_vega": 999.0,
                "max_theta": 999.0,
                "pricing_dte": 30,
                "risk_free_rate": 0.04,
            }

        with open(self.path, "r") as f:
            return json.load(f)
