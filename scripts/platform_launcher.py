from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
FRONTEND_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ServiceState:
    name: str
    pid: int | None
    managed: bool
    url: str
    log_path: str | None
    started_at: str | None


class PlatformLauncher:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.runtime_dir = self.root / ".runtime"
        self.log_dir = self.root / "logs" / "platform_launcher"
        self.state_path = self.runtime_dir / "platform_services.json"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"services": {}}
        try:
            return json.loads(self.state_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"services": {}}

    def _write_state(self, services: dict[str, ServiceState]) -> None:
        payload = {
            "root": str(self.root),
            "updated_at": utc_now(),
            "services": {name: asdict(state) for name, state in services.items()},
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.state_path)

    @staticmethod
    def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _http_ok(url: str, timeout: float = 2.0) -> tuple[bool, str]:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TradingPlatformLauncher/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return 200 <= response.status < 500, f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            return exc.code < 500, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return False, exc.__class__.__name__

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _backend_command(self, reload: bool) -> list[str]:
        command = ["uv", "run", "python", "scripts/run_m40_production_api.py", "--host", BACKEND_HOST, "--port", str(BACKEND_PORT)]
        if reload:
            command.append("--reload")
        return command

    def _frontend_command(self) -> list[str]:
        return ["npm", "run", "dev"]

    def _spawn(self, name: str, command: list[str], cwd: Path) -> ServiceState:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.log_dir / f"{name}_{timestamp}.log"
        log_handle = log_path.open("ab", buffering=0)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=cwd,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return ServiceState(
            name=name,
            pid=process.pid,
            managed=True,
            url=BACKEND_URL if name == "backend" else FRONTEND_URL,
            log_path=str(log_path),
            started_at=utc_now(),
        )

    def _wait_for(self, name: str, url: str, pid: int | None, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        detail = "not ready"
        while time.monotonic() < deadline:
            if pid and not self._pid_alive(pid):
                raise RuntimeError(f"{name} exited before becoming healthy. Check the launcher log.")
            ok, detail = self._http_ok(url, timeout=1.2)
            if ok:
                return
            time.sleep(0.5)
        raise RuntimeError(f"{name} did not become healthy within {timeout:.0f}s ({detail}).")

    def _postgres_check(self) -> tuple[bool, str]:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            env_path = self.root / ".env"
            if env_path.exists():
                for raw in env_path.read_text(errors="ignore").splitlines():
                    if raw.startswith("DATABASE_URL="):
                        database_url = raw.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not database_url:
            return False, "DATABASE_URL not found"
        try:
            result = subprocess.run(  # noqa: S603
                ["psql", database_url, "-Atqc", "SELECT 1"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() == "1", result.stderr.strip() or "connected"
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)

    def start(self, *, open_browser: bool, reload_backend: bool, timeout: float) -> int:
        print("\nTradingPlatform launcher")
        print("=" * 64)
        db_ok, db_detail = self._postgres_check()
        print(f"PostgreSQL : {'READY' if db_ok else 'CHECK'} ({db_detail})")
        if not db_ok:
            print("Backend startup will continue; inspect its log if database initialization fails.")

        previous = self._read_state().get("services", {})
        services: dict[str, ServiceState] = {}

        backend_ok, _ = self._http_ok(f"{BACKEND_URL}/openapi.json")
        if backend_ok:
            prior = previous.get("backend", {})
            services["backend"] = ServiceState(
                name="backend",
                pid=prior.get("pid") if self._pid_alive(prior.get("pid")) else None,
                managed=bool(prior.get("managed") and self._pid_alive(prior.get("pid"))),
                url=BACKEND_URL,
                log_path=prior.get("log_path"),
                started_at=prior.get("started_at"),
            )
            print(f"Backend    : READY (reusing {BACKEND_URL})")
        elif self._port_open(BACKEND_HOST, BACKEND_PORT):
            raise RuntimeError(f"Port {BACKEND_PORT} is occupied but the backend health endpoint is unavailable.")
        else:
            service = self._spawn("backend", self._backend_command(reload_backend), self.root)
            services["backend"] = service
            self._write_state(services)
            print(f"Backend    : STARTING (PID {service.pid})")
            self._wait_for("Backend", f"{BACKEND_URL}/openapi.json", service.pid, timeout)
            print(f"Backend    : READY ({BACKEND_URL})")

        frontend_ok, _ = self._http_ok(FRONTEND_URL)
        if frontend_ok:
            prior = previous.get("frontend", {})
            services["frontend"] = ServiceState(
                name="frontend",
                pid=prior.get("pid") if self._pid_alive(prior.get("pid")) else None,
                managed=bool(prior.get("managed") and self._pid_alive(prior.get("pid"))),
                url=FRONTEND_URL,
                log_path=prior.get("log_path"),
                started_at=prior.get("started_at"),
            )
            print(f"Workstation: READY (reusing {FRONTEND_URL})")
        elif self._port_open(FRONTEND_HOST, FRONTEND_PORT):
            raise RuntimeError(f"Port {FRONTEND_PORT} is occupied but the workstation is unavailable.")
        else:
            ui_root = self.root / "ui" / "workstation"
            if not (ui_root / "package.json").exists():
                raise RuntimeError(f"Workstation package not found at {ui_root}")
            service = self._spawn("frontend", self._frontend_command(), ui_root)
            services["frontend"] = service
            self._write_state(services)
            print(f"Workstation: STARTING (PID {service.pid})")
            self._wait_for("Workstation", FRONTEND_URL, service.pid, timeout)
            print(f"Workstation: READY ({FRONTEND_URL})")

        self._write_state(services)
        print("-" * 64)
        print(f"Everyday URL: {FRONTEND_URL}")
        print(f"API docs    : {BACKEND_URL}/docs")
        print(f"Logs        : {self.log_dir}")
        print("Stop        : ./stop_platform.sh")

        if open_browser:
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", FRONTEND_URL])  # noqa: S603
                else:
                    webbrowser.open(FRONTEND_URL)
            except Exception as exc:  # noqa: BLE001
                print(f"Browser could not be opened automatically: {exc}")
        return 0

    def stop(self) -> int:
        state = self._read_state()
        services = state.get("services", {})
        if not services:
            print("No launcher-managed services are recorded.")
            return 0
        for name in ("frontend", "backend"):
            service = services.get(name, {})
            pid = service.get("pid")
            managed = bool(service.get("managed"))
            if not managed or not self._pid_alive(pid):
                print(f"{name.capitalize():11}: not launcher-managed or already stopped")
                continue
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and self._pid_alive(pid):
                time.sleep(0.25)
            if self._pid_alive(pid):
                os.killpg(pid, signal.SIGKILL)
            print(f"{name.capitalize():11}: stopped PID {pid}")
        self.state_path.unlink(missing_ok=True)
        return 0

    def status(self) -> int:
        state = self._read_state().get("services", {})
        backend_ok, backend_detail = self._http_ok(f"{BACKEND_URL}/openapi.json")
        frontend_ok, frontend_detail = self._http_ok(FRONTEND_URL)
        db_ok, db_detail = self._postgres_check()
        print("TradingPlatform status")
        print("=" * 64)
        print(f"PostgreSQL : {'READY' if db_ok else 'DOWN'} ({db_detail})")
        print(f"Backend    : {'READY' if backend_ok else 'DOWN'} ({backend_detail})")
        print(f"Workstation: {'READY' if frontend_ok else 'DOWN'} ({frontend_detail})")
        for name in ("backend", "frontend"):
            item = state.get(name)
            if item:
                print(f"{name.capitalize()} PID: {item.get('pid')} · managed={item.get('managed')} · log={item.get('log_path')}")
        return 0 if backend_ok and frontend_ok else 1

    def logs(self, service: str, lines: int) -> int:
        state = self._read_state().get("services", {})
        item = state.get(service, {})
        path = item.get("log_path")
        if not path or not Path(path).exists():
            candidates = sorted(self.log_dir.glob(f"{service}_*.log"), reverse=True)
            path = str(candidates[0]) if candidates else None
        if not path:
            print(f"No {service} launcher log found.")
            return 1
        content = Path(path).read_text(errors="replace").splitlines()
        print(f"--- {path} ---")
        print("\n".join(content[-lines:]))
        return 0


def find_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    script = Path(__file__).resolve()
    candidate = script.parents[1]
    if (candidate / "pyproject.toml").exists():
        return candidate
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    raise RuntimeError("Could not locate the TradingPlatform repository root.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start, stop, and inspect the local TradingPlatform workstation.")
    parser.add_argument("command", nargs="?", choices=("start", "stop", "restart", "status", "logs"), default="start")
    parser.add_argument("--root")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reload-backend", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--service", choices=("backend", "frontend"), default="backend")
    parser.add_argument("--lines", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    launcher = PlatformLauncher(find_root(args.root))
    try:
        if args.command == "start":
            return launcher.start(open_browser=not args.no_browser, reload_backend=args.reload_backend, timeout=args.timeout)
        if args.command == "stop":
            return launcher.stop()
        if args.command == "restart":
            launcher.stop()
            return launcher.start(open_browser=not args.no_browser, reload_backend=args.reload_backend, timeout=args.timeout)
        if args.command == "status":
            return launcher.status()
        return launcher.logs(args.service, args.lines)
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Launcher error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
