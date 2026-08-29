from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.dashboard.progress_contracts import ProgressEventType, ScanProgressEvent
from trading_ai.scanner.dashboard.progress_serialization import append_event_jsonl, read_events_jsonl

def main() -> None:
    with TemporaryDirectory() as d:
        p=Path(d)/'events.jsonl'; append_event_jsonl(p,ScanProgressEvent(ProgressEventType.HEARTBEAT,message='ok'))
        events=read_events_jsonl(p); assert len(events)==1 and events[0].event_type is ProgressEventType.HEARTBEAT
        print('Milestone 35 Phase 5 Step 2 serialization assertions passed.')
if __name__=='__main__': main()
