from __future__ import annotations

import argparse
import re
from pathlib import Path


MARKER = "# M71.4 OPEX remains evidence-only."


def patch_service(path: Path) -> str:
    source = path.read_text()
    if MARKER in source and "opex_governance_status" in source and "HUMAN_APPROVED" in source:
        return "NOOP_ALREADY_GOVERNED"

    start = source.find("    def _intelligence(")
    if start < 0:
        raise RuntimeError("Could not locate _intelligence method")
    end = source.find("\n    def ", start + 5)
    if end < 0:
        raise RuntimeError("Could not bound _intelligence method")
    block = source[start:end]
    line_matches = list(re.finditer(r"(?m)^(?P<indent>\s*)opex\s*=.*$", block))
    inline_matches = list(
        re.finditer(
            r";\s*opex\s*=\s*_f\(meta\.get\((?P<quote>['\"])opex_score(?P=quote)\),\s*50\)\s*or\s*50(?=\n|$)",
            block,
        )
    )
    if not line_matches and not inline_matches and "opex_score" not in block:
        return "NOOP_NO_OPEX_COUPLING"
    if len(line_matches) + len(inline_matches) != 1:
        raise RuntimeError(
            "Expected exactly one recognized OPEX score assignment in "
            f"_intelligence; found line={len(line_matches)} inline={len(inline_matches)}"
        )
    match = (line_matches or inline_matches)[0]
    if line_matches:
        indent = match.group("indent")
        replacement_prefix = ""
    else:
        line_start = block.rfind("\n", 0, match.start()) + 1
        indent_match = re.match(r"\s*", block[line_start:match.start()])
        indent = indent_match.group(0)
        replacement_prefix = "\n"
    replacement = "\n".join(
        (
            f"{indent}{MARKER}  An unapproved or merely present",
            f"{indent}# opex_score must never influence autonomous position management.",
            f"{indent}opex_status=str(meta.get('opex_governance_status') or 'ABSTAIN').upper()",
            f"{indent}opex=(_f(meta.get('opex_score'),50) or 50) if opex_status=='HUMAN_APPROVED' else 50",
        )
    )
    patched_block = (
        block[: match.start()]
        + replacement_prefix
        + replacement
        + block[match.end() :]
    )
    path.write_text(source[:start] + patched_block + source[end:])
    return "PATCHED_SHADOW_FAIL_CLOSED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        default="src/trading_ai/autonomous_position_management/service.py",
    )
    args = parser.parse_args()
    target = Path(args.target)
    if not target.is_file():
        raise SystemExit(f"Missing target: {target}")
    print(patch_service(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
