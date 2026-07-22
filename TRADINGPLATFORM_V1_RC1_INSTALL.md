# TradingPlatform v1.0 RC1 Installation

## 1. Back up the current repository

```bash
cd /Users/vinay.hatti
cp -R TradingPlatform TradingPlatform_pre_v1_rc1_backup
```

## 2. Extract the RC1 archive

The archive contains a complete synchronized `TradingPlatform` directory. Replace the current tree or compare it with the backup before switching.

## 3. Synchronize dependencies

```bash
cd /Users/vinay.hatti/TradingPlatform
uv sync
```

## 4. Validate and apply migrations

```bash
uv run alembic heads
uv run alembic upgrade head
uv run alembic current
```

Expected head: `m42ops`.

## 5. Build the workstation

```bash
cd ui/workstation
npm install
npm run typecheck
npm run test
npm run build
cd ../..
```

## 6. Run RC1 validation

```bash
uv run python scripts/validate_v1_rc1.py
```

## 7. Start the command center

```bash
uv run python scripts/run_m42_command_center.py --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` and API documentation at `http://127.0.0.1:8000/docs`.
