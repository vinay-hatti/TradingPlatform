#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_4_adapter_source_semantics_capture.json"
OUT = ROOT / "reports/m77/m77_19_4_adapter_source_semantics_capture.json"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json_atomic(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def expand_paths(cfg):
    paths = []
    for rel in cfg["required_primary_sources"]:
        p = ROOT / rel
        if p.exists():
            paths.append(p)
    for pattern in cfg["required_dependency_candidates"]:
        for p in ROOT.glob(pattern):
            if p.is_file():
                paths.append(p)
    dedup = []
    seen = set()
    for p in paths:
        rp = str(p.relative_to(ROOT))
        if rp not in seen:
            seen.add(rp)
            dedup.append(p)
    return dedup

def analyze_python(path: Path):
    text = path.read_text(errors="ignore")
    try:
        tree = ast.parse(text)
    except Exception as e:
        return {
            "parse_ok": False,
            "parse_error": repr(e),
            "sha256": sha256(path),
        }

    imports = []
    funcs = []
    classes = []
    calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute):
                parts = []
                cur = f
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                calls.add(".".join(reversed(parts)))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "kwonlyargs": [a.arg for a in node.args.kwonlyargs],
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", None),
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", None),
            })

    argparse_options = sorted(set(
        re.findall(r'add_argument\(\s*["\'](--[^"\']+)["\']', text)
    ))

    marker_lines = []
    for idx, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(k in low for k in (
            "as_of", "point_in_time", "walk_forward", "future", "shift(",
            "lead(", "price_history", "historical_underlying_replay",
            "sessionlocal", "select(", "insert(", "update(", "delete(",
            "where ", "date <=", "timestamp <=", "published_at <="
        )):
            marker_lines.append({"line": idx, "text": line[:500]})

    return {
        "parse_ok": True,
        "sha256": sha256(path),
        "imports": sorted(set(imports)),
        "top_level_functions": funcs,
        "top_level_classes": classes,
        "call_targets": sorted(calls),
        "argparse_options": argparse_options,
        "semantic_marker_lines": marker_lines[:1000],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "capture"))
    args = ap.parse_args()

    cfg = json.loads(CFG.read_text())
    files = expand_paths(cfg)
    primary = {
        rel: (ROOT / rel).exists()
        for rel in cfg["required_primary_sources"]
    }

    if args.mode == "preflight":
        print(json.dumps({
            "version": cfg["version"],
            "status": "READY",
            "primary_sources": primary,
            "discovered_file_count": len(files),
            "capture_root": cfg["capture_root"],
            "automatic_replay_execution": False,
            "database_writes": False,
            "production_authority_effect": False,
        }, indent=2))
        return

    if not all(primary.values()):
        missing = [k for k, v in primary.items() if not v]
        raise SystemExit(f"M77.19.4 blocked: missing primary sources: {missing}")

    capture_root = ROOT / cfg["capture_root"]
    source_root = capture_root / "source"
    if capture_root.exists():
        shutil.rmtree(capture_root)
    source_root.mkdir(parents=True, exist_ok=True)

    manifest_files = []
    for src in files:
        rel = src.relative_to(ROOT)
        dst = source_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        item = {
            "path": str(rel),
            "captured_path": str(dst.relative_to(ROOT)),
            "sha256": sha256(src),
            "size_bytes": src.stat().st_size,
        }
        if src.suffix == ".py":
            item["python_analysis"] = analyze_python(src)
        manifest_files.append(item)

    manifest = {
        "version": cfg["version"],
        "status": "READY",
        "capture_root": str(capture_root),
        "files": manifest_files,
        "primary_sources": primary,
        "source_file_count": len(manifest_files),
        "governance": cfg["capture_policy"],
        "next_step": cfg["next_step"],
        "production_authority_effect": False,
    }
    write_json_atomic(capture_root / "manifest.json", manifest)

    bundle = ROOT / "research_data/m77_19_4/M77_19_4_SourceSemanticsBundle.tar.gz"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    if bundle.exists():
        bundle.unlink()
    with tarfile.open(bundle, "w:gz") as tf:
        tf.add(capture_root, arcname="m77_19_4_source_semantics_capture")

    manifest["bundle_path"] = str(bundle)
    manifest["bundle_sha256"] = sha256(bundle)
    write_json_atomic(capture_root / "manifest.json", manifest)
    write_json_atomic(OUT, manifest)

    print(json.dumps({
        "version": cfg["version"],
        "status": "READY",
        "source_file_count": len(manifest_files),
        "bundle_path": str(bundle),
        "bundle_sha256": manifest["bundle_sha256"],
        "primary_sources": primary,
        "next_step": cfg["next_step"],
        "database_writes": False,
        "production_authority_effect": False,
    }, indent=2))

if __name__ == "__main__":
    main()
