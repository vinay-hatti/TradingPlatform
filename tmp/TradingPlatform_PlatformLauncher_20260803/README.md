# TradingPlatform Platform Launcher

Adds a safe local launcher for the FastAPI backend and Vite workstation.

## Daily use

```bash
cd /Users/vinay.hatti/TradingPlatform
./start_platform.sh
```

The launcher:

- checks PostgreSQL when `DATABASE_URL` is available;
- reuses healthy services already running;
- starts the backend at `127.0.0.1:8000` when missing;
- starts the workstation at `127.0.0.1:5173` when missing;
- waits for both health checks;
- opens the workstation in the default browser;
- stores logs under `logs/platform_launcher`;
- stores launcher-managed PIDs under `.runtime`.

## Commands

```bash
./start_platform.sh
./start_platform.sh --no-browser
./stop_platform.sh
./platform_status.sh
uv run python scripts/platform_launcher.py restart
uv run python scripts/platform_launcher.py logs --service backend --lines 200
uv run python scripts/platform_launcher.py logs --service frontend --lines 200
```

The stop command terminates only services started and recorded by this launcher. It does not terminate unrelated processes already using the configured ports.
