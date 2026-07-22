from pathlib import Path
text=(Path(__file__).resolve().parents[1]/'src/trading_ai/ui/workstation.py').read_text()
assert 'index.html' in text and 'StaticFiles' in text and '/{full_path:path}' in text
launcher=(Path(__file__).resolve().parents[1]/'scripts/run_m41_workstation.py').read_text()
assert 'create_production_app' in launcher and 'mount_workstation' in launcher
print('Milestone 41 backend mount assertions passed.')
