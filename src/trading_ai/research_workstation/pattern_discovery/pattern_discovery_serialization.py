import json
from dataclasses import asdict
from pathlib import Path


def _jsonable(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def pattern_discovery_payload(profile):
    return _jsonable(asdict(profile))


def _write(profile, output_file):
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(pattern_discovery_payload(profile), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_pattern_discovery(profile, output_file):
    return _write(profile, output_file)


def write_similarity_report(profile, output_file):
    return _write(profile, output_file)
