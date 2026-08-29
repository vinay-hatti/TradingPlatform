from pathlib import Path

def main():
    text=Path('migrations/versions/m39pos_position_monitoring.py').read_text()
    assert 'revision = "m39pos"' in text and 'down_revision = "m38exec"' in text
    assert 'position_monitoring_assessments' in text and 'position_exit_instructions' in text
    print('M39 migration contract assertions passed.')
if __name__=='__main__': main()
