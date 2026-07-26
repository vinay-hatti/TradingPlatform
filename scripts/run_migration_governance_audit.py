#!/usr/bin/env python3
"""Static Alembic and SQLAlchemy migration governance audit.

This audit intentionally requires no database connection. It prevents common
upgrade failures before deployment: oversized revision identifiers, duplicate
or orphan revisions, cycles, multiple unexpected heads, PostgreSQL identifier
truncation, and Milestone 46 persisted literals wider than their columns.
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALEMBIC_VERSION_LIMIT = 32
POSTGRES_IDENTIFIER_LIMIT = 63
ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"


@dataclass(frozen=True)
class RevisionRecord:
    revision: str
    down_revisions: tuple[str, ...]
    path: Path


def _literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _assignments(tree: ast.Module) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = _literal(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values[node.target.id] = _literal(node.value)
    return values


def load_revisions() -> list[RevisionRecord]:
    records: list[RevisionRecord] = []
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name.startswith("__"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        values = _assignments(tree)
        revision = values.get("revision")
        if not isinstance(revision, str) or not revision:
            raise AssertionError(f"{path.name}: missing literal revision identifier")
        parent = values.get("down_revision")
        if parent is None:
            parents: tuple[str, ...] = ()
        elif isinstance(parent, str):
            parents = (parent,)
        elif isinstance(parent, (tuple, list)) and all(isinstance(item, str) for item in parent):
            parents = tuple(parent)
        else:
            raise AssertionError(f"{path.name}: down_revision must be a literal string, sequence, or None")
        records.append(RevisionRecord(revision, parents, path))
    return records


def audit_graph(records: list[RevisionRecord]) -> list[str]:
    errors: list[str] = []
    by_revision: dict[str, RevisionRecord] = {}
    for record in records:
        if len(record.revision) > ALEMBIC_VERSION_LIMIT:
            errors.append(
                f"revision {record.revision!r} is {len(record.revision)} characters; "
                f"alembic_version.version_num supports {ALEMBIC_VERSION_LIMIT}"
            )
        if record.revision in by_revision:
            errors.append(
                f"duplicate revision {record.revision!r}: "
                f"{by_revision[record.revision].path.name}, {record.path.name}"
            )
        by_revision[record.revision] = record

    for record in records:
        for parent in record.down_revisions:
            if parent not in by_revision:
                errors.append(f"orphan revision {record.revision!r}: missing parent {parent!r}")

    children: dict[str, set[str]] = {key: set() for key in by_revision}
    for record in records:
        for parent in record.down_revisions:
            if parent in children:
                children[parent].add(record.revision)

    heads = sorted(key for key, value in children.items() if not value)
    if len(heads) != 1:
        errors.append(f"expected one Alembic head, found {len(heads)}: {heads}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(revision: str) -> None:
        if revision in visiting:
            errors.append(f"cycle detected at revision {revision!r}")
            return
        if revision in visited:
            return
        visiting.add(revision)
        for parent in by_revision[revision].down_revisions:
            if parent in by_revision:
                visit(parent)
        visiting.remove(revision)
        visited.add(revision)

    for revision in by_revision:
        visit(revision)
    return errors


def audit_postgres_identifiers() -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"\bname\s*=\s*['\"]([^'\"]+)['\"]")
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in pattern.findall(text):
            if len(name.encode("utf-8")) > POSTGRES_IDENTIFIER_LIMIT:
                errors.append(
                    f"{path.name}: PostgreSQL identifier {name!r} is "
                    f"{len(name.encode('utf-8'))} bytes; limit is {POSTGRES_IDENTIFIER_LIMIT}"
                )
    return errors


def audit_m46_literal_widths() -> list[str]:
    """Guard the longest values persisted by the Polygon closure migration."""
    migration = VERSIONS / "m46_002_polygon_authoritative_closure.py"
    text = migration.read_text(encoding="utf-8")
    widths = {
        "capture_status": 24,
        "quote_quality": 24,
        "strategy_fit": 40,
        "liquidity_regime": 24,
        "provenance": 48,
        "policy_version": 32,
        "outcome": 32,
    }
    values = {
        "capture_status": ["BUILDING", "READY", "PARTIAL", "FAILED"],
        "quote_quality": ["COMPLETE_QUOTE", "ONE_SIDED_QUOTE", "NO_QUOTE", "TRADE_ONLY", "STALE", "INVALID", "UNKNOWN"],
        "strategy_fit": ["LONG_PREMIUM_FAVORABLE", "LONG_PREMIUM_SELECTIVE", "SHORT_PREMIUM_SELECTIVE", "SHORT_PREMIUM_FAVORABLE", "NEUTRAL"],
        "liquidity_regime": ["DEEP", "NORMAL", "THIN", "FRAGMENTED", "STRESSED"],
        "provenance": ["POLYGON", "POLYGON_TRADES_NBBO", "MIGRATED_DATE_LEVEL", "CAPABILITY_UNAVAILABLE"],
        "policy_version": ["M46_POLYGON_V1"],
        "outcome": ["SUPPORTIVE", "CONDITIONALLY_SUPPORTIVE", "NEUTRAL", "CONFLICTED", "UNSUPPORTIVE", "UNAVAILABLE"],
    }
    errors: list[str] = []
    for column, width in widths.items():
        if not re.search(rf"Column\(['\"]{re.escape(column)}['\"],\s*sa\.String\({width}\)", text):
            errors.append(f"m46_002: expected {column} to be String({width})")
        for value in values[column]:
            if len(value) > width:
                errors.append(f"m46_002: {column} value {value!r} exceeds String({width})")
    return errors


def main() -> int:
    records = load_revisions()
    errors = audit_graph(records) + audit_postgres_identifiers() + audit_m46_literal_widths()
    if errors:
        print("Migration governance audit FAILED:")
        for error in errors:
            print(f" - {error}")
        return 1
    heads = set(record.revision for record in records)
    for record in records:
        heads.difference_update(record.down_revisions)
    print("Migration governance audit passed.")
    print(f"Revisions: {len(records)}")
    print(f"Head: {next(iter(heads))}")
    print(f"Maximum revision length: {max(len(record.revision) for record in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
