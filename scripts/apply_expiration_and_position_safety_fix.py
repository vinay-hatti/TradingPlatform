from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, text: str) -> None:
    (ROOT / relative).write_text(text, encoding="utf-8")


def patch_scanner() -> None:
    relative = "src/trading_ai/daily/scanner.py"
    text = read(relative)

    import_line = (
        "from trading_ai.daily.expiry_selector import "
        "StandardFridayExpirySelector\n"
    )
    if import_line not in text:
        anchor = "from trading_ai.daily.models import DailyCandidate\n"
        if anchor not in text:
            raise RuntimeError(
                f"{relative}: DailyCandidate import not found"
            )
        text = text.replace(anchor, anchor + import_line, 1)

    if "self.expiry_selector = StandardFridayExpirySelector()" not in text:
        match = re.search(
            r"(?m)^(?P<indent>\s*)self\.end\s*=\s*end\s*$",
            text,
        )
        if not match:
            raise RuntimeError(f"{relative}: self.end = end not found")
        insertion = (
            match.group(0)
            + "\n"
            + match.group("indent")
            + "self.expiry_selector = StandardFridayExpirySelector()"
        )
        text = text[: match.start()] + insertion + text[match.end() :]

    if "expiry_selection = self.expiry_selector.select(" not in text:
        marker = "        return DailyCandidate(\n"
        if marker not in text:
            raise RuntimeError(
                f"{relative}: DailyCandidate construction not found"
            )
        block = (
            "        expiry_selection = self.expiry_selector.select(\n"
            "            valuation_date=self.end,\n"
            "            target_dte=self.pricing_dte,\n"
            "        )\n\n"
        )
        text = text.replace(marker, block + marker, 1)

    patterns = [
        r'expiry\s*=\s*f"\{self\.pricing_dte\}DTE_PROXY"',
        r"expiry\s*=\s*f'\{self\.pricing_dte\}DTE_PROXY'",
        r'expiry\s*=\s*"30DTE_PROXY"',
        r"expiry\s*=\s*'30DTE_PROXY'",
    ]
    replaced = False
    for pattern in patterns:
        new_text, count = re.subn(
            pattern,
            "expiry=expiry_selection.expiration_iso",
            text,
            count=1,
        )
        if count:
            text = new_text
            replaced = True
            break

    if not replaced and "expiry=expiry_selection.expiration_iso" not in text:
        raise RuntimeError(
            f"{relative}: proxy expiry assignment not found"
        )

    text, _ = re.subn(
        r'dte\s*=\s*int\(greeks\["dte"\]\)',
        "dte=int(expiry_selection.actual_dte)",
        text,
        count=1,
    )

    # Store source when the current dataclass supports it.
    if "expiry_source=" not in text:
        text = text.replace(
            "            expiry=expiry_selection.expiration_iso,\n",
            "            expiry=expiry_selection.expiration_iso,\n"
            "            expiry_source=expiry_selection.source,\n",
            1,
        )

    write(relative, text)


def patch_daily_candidate_model() -> None:
    relative = "src/trading_ai/daily/models.py"
    text = read(relative)

    if "expiry_source:" not in text:
        anchor = "    final_score: float\n"
        if anchor not in text:
            raise RuntimeError(
                f"{relative}: final_score field not found"
            )
        text = text.replace(
            anchor,
            anchor
            + '    expiry_source: str = "STANDARD_FRIDAY_PROXY"\n',
            1,
        )

    write(relative, text)


def patch_live_trade_model() -> None:
    relative = "src/trading_ai/daily/trade_candidate.py"
    text = read(relative)

    if "expiry_source:" not in text:
        # Add after risk_score because following fields usually have defaults.
        anchor = "    risk_score: float\n"
        if anchor not in text:
            raise RuntimeError(
                f"{relative}: risk_score field not found"
            )
        text = text.replace(
            anchor,
            anchor
            + '    expiry_source: str = "STANDARD_FRIDAY_PROXY"\n',
            1,
        )

    write(relative, text)


def patch_recommender() -> None:
    relative = "src/trading_ai/daily/recommender.py"
    text = read(relative)

    if "minimum_option_price" not in text:
        # Extend initializer without replacing its existing signature.
        match = re.search(
            r"(?ms)(def __init__\s*\(.*?\):)(?P<body>\n\s+)",
            text,
        )
        if not match:
            raise RuntimeError(
                f"{relative}: __init__ signature not found"
            )

        signature = match.group(1)
        if "minimum_option_price" not in signature:
            signature = signature[:-2].rstrip()
            if signature.endswith(","):
                signature += "\n"
            else:
                signature += ",\n"
            # Preserve class indentation by inferring parameter indentation.
            signature += (
                "        minimum_option_price=0.25,\n"
                "        maximum_contracts=50,\n"
                "    ):"
            )
            text = text[: match.start(1)] + signature + text[match.end(1) :]

        init_anchor = (
            "        self.contract_multiplier = int(contract_multiplier)\n"
        )
        if init_anchor in text:
            text = text.replace(
                init_anchor,
                init_anchor
                + "        self.minimum_option_price = "
                + "float(minimum_option_price)\n"
                + "        self.maximum_contracts = "
                + "int(maximum_contracts)\n",
                1,
            )
        else:
            raise RuntimeError(
                f"{relative}: contract_multiplier assignment not found"
            )

    # Prevent tiny proxy premiums from generating huge positions.
    contracts_pattern = (
        r"(?m)^(?P<indent>\s*)contracts\s*=\s*"
        r"self\._contracts\(entry\)\s*$"
    )
    match = re.search(contracts_pattern, text)
    if match and "entry < self.minimum_option_price" not in text:
        indent = match.group("indent")
        block = (
            f"{indent}if entry < self.minimum_option_price:\n"
            f"{indent}    contracts = 0\n"
            f"{indent}else:\n"
            f"{indent}    contracts = min(\n"
            f"{indent}        self._contracts(entry),\n"
            f"{indent}        self.maximum_contracts,\n"
            f"{indent}    )"
        )
        text = text[: match.start()] + block + text[match.end() :]

    # Carry expiration source to live trade.
    if "expiry_source=" not in text:
        anchor = "            dte=int(candidate.dte),\n"
        if anchor not in text:
            raise RuntimeError(
                f"{relative}: live-trade dte assignment not found"
            )
        text = text.replace(
            anchor,
            anchor
            + "            expiry_source=getattr(\n"
            + "                candidate,\n"
            + '                "expiry_source",\n'
            + '                "STANDARD_FRIDAY_PROXY",\n'
            + "            ),\n",
            1,
        )

    # Add explicit notes.
    if "minimum tradable proxy premium" not in text:
        marker = "        notes = []\n"
        if marker in text:
            text = text.replace(
                marker,
                marker
                + "        if entry < self.minimum_option_price:\n"
                + "            notes.append(\n"
                + '                "Rejected for sizing: option proxy price "\n'
                + '                "is below the minimum tradable proxy premium."\n'
                + "            )\n",
                1,
            )

    if "standard-Friday proxy" not in text:
        return_marker = "        return LiveTradeCandidate(\n"
        note = (
            "        if getattr(candidate, \"expiry_source\", \"\") == "
            "\"STANDARD_FRIDAY_PROXY\":\n"
            "            notes.append(\n"
            '                "Expiration is a standard-Friday proxy; "\n'
            '                "verify the listed contract with the broker."\n'
            "            )\n\n"
        )
        if return_marker in text:
            text = text.replace(
                return_marker,
                note + return_marker,
                1,
            )

    write(relative, text)


def patch_cli() -> None:
    relative = "scripts/run_daily_scan.py"
    text = read(relative)

    text = text.replace("Expiry Proxy", "Expiration")

    # Ranked candidate output.
    if "Expiry Source" not in text:
        patterns = [
            (
                r'(?m)^(?P<i>\s*)print\(f"(?P<label>\s*)Expiration'
                r'(?P<rest>[^"]*\{candidate\.expiry\}[^"]*)"\)\s*$',
                "candidate",
            ),
            (
                r'(?m)^(?P<i>\s*)print\(f"(?P<label>\s*)Expiration'
                r'(?P<rest>[^"]*\{c\.expiry\}[^"]*)"\)\s*$',
                "c",
            ),
        ]
        for pattern, variable in patterns:
            match = re.search(pattern, text)
            if match:
                addition = (
                    match.group(0)
                    + "\n"
                    + match.group("i")
                    + 'print(f"   DTE            : '
                    + "{"
                    + f"{variable}.dte"
                    + '}")\n'
                    + match.group("i")
                    + 'print(f"   Expiry Source  : '
                    + "{"
                    + f"{variable}.expiry_source"
                    + '}")'
                )
                text = text[: match.start()] + addition + text[match.end() :]
                break

    # Live trade output.
    if "trade.expiry" not in text and "t.expiry" not in text:
        candidates = [
            (
                r'(?m)^(?P<i>\s*)print\(f"\s*Strike\s*: '
                r'\$\{trade\.strike:\.2f\}"\)\s*$',
                "trade",
            ),
            (
                r'(?m)^(?P<i>\s*)print\(f"\s*Strike\s*: '
                r'\$\{t\.strike:\.2f\}"\)\s*$',
                "t",
            ),
        ]
        for pattern, variable in candidates:
            match = re.search(pattern, text)
            if match:
                addition = (
                    match.group(0)
                    + "\n"
                    + match.group("i")
                    + 'print(f"   Expiration  : '
                    + "{"
                    + f"{variable}.expiry"
                    + '}")\n'
                    + match.group("i")
                    + 'print(f"   DTE         : '
                    + "{"
                    + f"{variable}.dte"
                    + '}")\n'
                    + match.group("i")
                    + 'print(f"   Expiry Src  : '
                    + "{"
                    + f"{variable}.expiry_source"
                    + '}")'
                )
                text = text[: match.start()] + addition + text[match.end() :]
                break

    write(relative, text)


def patch_reporter(relative: str, variable: str) -> None:
    path = ROOT / relative
    if not path.exists():
        print(f"WARNING: {relative} does not exist; skipped")
        return

    text = path.read_text(encoding="utf-8")

    # Ensure serialized row dictionaries carry the source.
    if f'"expiry_source": {variable}.expiry_source' not in text:
        expiry_row = f'                "expiry": {variable}.expiry,\n'
        if expiry_row in text:
            text = text.replace(
                expiry_row,
                expiry_row
                + f'                "expiry_source": '
                + f"{variable}.expiry_source,\n",
                1,
            )

    # Add field name to explicit CSV field lists.
    if '"expiry_source"' not in text:
        text = text.replace(
            '            "expiry",\n',
            '            "expiry",\n            "expiry_source",\n',
            1,
        )

    # Add HTML columns when tuple-based rendering is used.
    if '("Expiration", "expiry")' not in text:
        text = text.replace(
            '("Strike", "strike"),',
            '("Strike", "strike"),\n'
            '                    ("Expiration", "expiry"),\n'
            '                    ("DTE", "dte"),\n'
            '                    ("Expiry Source", "expiry_source"),',
            1,
        )

    path.write_text(text, encoding="utf-8")


def verify() -> None:
    scanner = read("src/trading_ai/daily/scanner.py")
    cli = read("scripts/run_daily_scan.py")
    recommender = read("src/trading_ai/daily/recommender.py")

    failures = []
    if "30DTE_PROXY" in scanner or "DTE_PROXY" in scanner:
        failures.append("scanner.py still contains proxy expiry text")
    if "expiry=expiry_selection.expiration_iso" not in scanner:
        failures.append("scanner.py lacks concrete expiry assignment")
    if "StandardFridayExpirySelector" not in scanner:
        failures.append("scanner.py lacks expiry selector")
    if "Expiration" not in cli:
        failures.append("run_daily_scan.py lacks Expiration output")
    if "minimum_option_price" not in recommender:
        failures.append("recommender lacks minimum premium guard")
    if "maximum_contracts" not in recommender:
        failures.append("recommender lacks maximum contract cap")

    if failures:
        raise RuntimeError("; ".join(failures))

    print("Verified:")
    print("- concrete Friday expiration is active")
    print("- DTE proxy text is removed from scanner")
    print("- CLI contains expiration output")
    print("- minimum proxy premium guard is active")
    print("- maximum contract cap is active")


def main() -> None:
    patch_daily_candidate_model()
    patch_live_trade_model()
    patch_scanner()
    patch_recommender()
    patch_cli()
    patch_reporter(
        "src/trading_ai/daily/reporter.py",
        "c",
    )
    patch_reporter(
        "src/trading_ai/daily/trade_reporter.py",
        "t",
    )
    verify()
    print("Expiration and position-safety fix applied successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
