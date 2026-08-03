from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "payload" / "scripts" / "platform_launcher.py"
spec = importlib.util.spec_from_file_location("platform_launcher", module_path)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "pyproject.toml").write_text("[project]\nname='test'\nversion='0'\n")
    launcher = module.PlatformLauncher(root)
    services = {
        "backend": module.ServiceState("backend", 123, True, module.BACKEND_URL, "/tmp/backend.log", module.utc_now()),
    }
    launcher._write_state(services)
    payload = json.loads(launcher.state_path.read_text())
    assert payload["services"]["backend"]["managed"] is True
    assert payload["services"]["backend"]["url"] == module.BACKEND_URL

assert module.BACKEND_PORT == 8000
assert module.FRONTEND_PORT == 5173
assert "scripts/run_m40_production_api.py" in module.PlatformLauncher(Path.cwd())._backend_command(False)
print("Platform launcher assertions passed.")
