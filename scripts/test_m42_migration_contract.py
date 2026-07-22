from pathlib import Path
p=Path(__file__).resolve().parents[1]/'migrations/versions/m42ops_realtime_monitoring.py';s=p.read_text();assert "revision='m42ops'" in s and "down_revision='m40api'" in s
print('Milestone 42 migration assertions passed.')
