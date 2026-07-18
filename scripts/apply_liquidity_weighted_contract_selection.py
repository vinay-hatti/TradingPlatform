from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

LIVE_FIELDS = [
    '    contract_ticker: str = ""',
    "    bid: float = 0.0",
    "    ask: float = 0.0",
    "    last_price: float = 0.0",
    '    price_source: str = ""',
    '    option_data_source: str = ""',
    '    quote_timestamp: str = ""',
    "    open_interest: int = 0",
    "    option_volume: int = 0",
    "    spread_pct: float = 0.0",
]

SCORE_FIELDS = [
    "    contract_selection_score: float = 0.0",
    "    liquidity_score: float = 0.0",
    "    delta_selection_score: float = 0.0",
    "    expiration_selection_score: float = 0.0",
    "    strike_selection_score: float = 0.0",
    "    spread_selection_score: float = 0.0",
    "    open_interest_selection_score: float = 0.0",
    "    volume_selection_score: float = 0.0",
]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, text: str) -> None:
    (ROOT / relative).write_text(text, encoding="utf-8")


def insert_dataclass_fields(
    relative: str,
    *,
    anchor_candidates: list[str],
) -> None:
    text = read(relative)

    missing = [
        field
        for field in LIVE_FIELDS + SCORE_FIELDS
        if field.split(":", 1)[0].strip()
        not in text
    ]
    if not missing:
        return

    anchor = next(
        (candidate for candidate in anchor_candidates if candidate in text),
        None,
    )
    if anchor is None:
        raise RuntimeError(
            f"{relative}: could not locate a safe dataclass insertion point"
        )

    block = "\n".join(
        field
        for field in LIVE_FIELDS + SCORE_FIELDS
        if field.split(":", 1)[0].strip() not in text
    ) + "\n"

    text = text.replace(anchor, anchor + block, 1)
    write(relative, text)


def patch_models() -> None:
    insert_dataclass_fields(
        "src/trading_ai/daily/models.py",
        anchor_candidates=[
            "    final_score: float\n",
            "    dte: int\n",
        ],
    )
    insert_dataclass_fields(
        "src/trading_ai/daily/trade_candidate.py",
        anchor_candidates=[
            "    risk_score: float\n",
            "    volatility: float\n",
        ],
    )


def ensure_live_integration_present() -> None:
    scanner = read("src/trading_ai/daily/scanner.py")
    missing = []

    if "LiveOptionContractSelector" not in scanner:
        missing.append("LiveOptionContractSelector")
    if "option_data_mode" not in scanner:
        missing.append("option_data_mode")
    if "contract_ticker" not in scanner:
        missing.append("contract_ticker propagation")

    if missing:
        raise RuntimeError(
            "Live-option integration is not active in scanner.py. "
            "Install and apply live_option_contract_data_dropin.zip first. "
            "Missing: " + ", ".join(missing)
        )


def patch_scanner() -> None:
    relative = "src/trading_ai/daily/scanner.py"
    text = read(relative)

    # Safer defaults
    text = re.sub(
        r"maximum_option_spread_pct\s*=\s*0\.35",
        "maximum_option_spread_pct=0.25",
        text,
        count=1,
    )
    text = re.sub(
        r"minimum_option_open_interest\s*=\s*0",
        "minimum_option_open_interest=100",
        text,
        count=1,
    )
    text = re.sub(
        r"minimum_option_volume\s*=\s*0",
        "minimum_option_volume=10",
        text,
        count=1,
    )

    if "open_interest_weight=" not in text:
        match = re.search(
            r"(?m)^(?P<i>\s*)minimum_option_volume\s*=\s*10,\s*$",
            text,
        )
        if not match:
            raise RuntimeError(
                f"{relative}: could not locate minimum_option_volume parameter"
            )
        indent = match.group("i")
        addition = (
            match.group(0)
            + "\n"
            + indent + "delta_weight=0.25,\n"
            + indent + "expiration_weight=0.15,\n"
            + indent + "strike_weight=0.10,\n"
            + indent + "spread_weight=0.15,\n"
            + indent + "open_interest_weight=0.20,\n"
            + indent + "volume_weight=0.15,"
        )
        text = text[:match.start()] + addition + text[match.end():]

    policy_anchor = re.search(
        r"(?m)^(?P<i>\s*)minimum_volume\s*=\s*int\(minimum_option_volume\),\s*$",
        text,
    )
    if policy_anchor and "open_interest_weight=float(" not in text:
        i = policy_anchor.group("i")
        addition = (
            policy_anchor.group(0)
            + "\n"
            + i + "delta_weight=float(delta_weight),\n"
            + i + "expiration_weight=float(expiration_weight),\n"
            + i + "strike_weight=float(strike_weight),\n"
            + i + "spread_weight=float(spread_weight),\n"
            + i + "open_interest_weight=float(open_interest_weight),\n"
            + i + "volume_weight=float(volume_weight),"
        )
        text = (
            text[:policy_anchor.start()]
            + addition
            + text[policy_anchor.end():]
        )

    init_anchor = re.search(
        r"(?m)^(?P<i>\s*)spread_pct\s*=\s*0\.0\s*$",
        text,
    )
    if init_anchor and "contract_selection_score = 0.0" not in text:
        i = init_anchor.group("i")
        additions = "\n".join(
            [
                i + "contract_selection_score = 0.0",
                i + "liquidity_score = 0.0",
                i + "delta_selection_score = 0.0",
                i + "expiration_selection_score = 0.0",
                i + "strike_selection_score = 0.0",
                i + "spread_selection_score = 0.0",
                i + "open_interest_selection_score = 0.0",
                i + "volume_selection_score = 0.0",
            ]
        )
        text = (
            text[:init_anchor.end()]
            + "\n"
            + additions
            + text[init_anchor.end():]
        )

    capture_anchor = re.search(
        r"(?m)^(?P<i>\s*)spread_pct\s*=\s*live\.spread_pct\s*$",
        text,
    )
    if capture_anchor and "live.score.total_score" not in text:
        i = capture_anchor.group("i")
        additions = "\n".join(
            [
                i + "contract_selection_score = live.score.total_score",
                i + "liquidity_score = live.score.liquidity_score",
                i + "delta_selection_score = live.score.delta_score",
                i + "expiration_selection_score = live.score.expiration_score",
                i + "strike_selection_score = live.score.strike_score",
                i + "spread_selection_score = live.score.spread_score",
                i + "open_interest_selection_score = live.score.open_interest_score",
                i + "volume_selection_score = live.score.volume_score",
            ]
        )
        text = (
            text[:capture_anchor.end()]
            + "\n"
            + additions
            + text[capture_anchor.end():]
        )

    candidate_anchor = re.search(
        r"(?m)^(?P<i>\s*)spread_pct\s*=\s*float\(spread_pct\),\s*$",
        text,
    )
    if candidate_anchor and "contract_selection_score=float(" not in text:
        i = candidate_anchor.group("i")
        additions = "\n".join(
            [
                i + "contract_selection_score=float(contract_selection_score),",
                i + "liquidity_score=float(liquidity_score),",
                i + "delta_selection_score=float(delta_selection_score),",
                i + "expiration_selection_score=float(expiration_selection_score),",
                i + "strike_selection_score=float(strike_selection_score),",
                i + "spread_selection_score=float(spread_selection_score),",
                i + "open_interest_selection_score=float(open_interest_selection_score),",
                i + "volume_selection_score=float(volume_selection_score),",
            ]
        )
        text = (
            text[:candidate_anchor.end()]
            + "\n"
            + additions
            + text[candidate_anchor.end():]
        )

    write(relative, text)


def patch_recommender() -> None:
    relative = "src/trading_ai/daily/recommender.py"
    text = read(relative)

    anchor = re.search(
        r"(?m)^(?P<i>\s*)spread_pct\s*=\s*float\(getattr\(candidate,\s*"
        r'"spread_pct",\s*0\.0\)\),\s*$',
        text,
    )
    if anchor and "contract_selection_score=float(getattr(" not in text:
        i = anchor.group("i")
        names = [
            "contract_selection_score",
            "liquidity_score",
            "delta_selection_score",
            "expiration_selection_score",
            "strike_selection_score",
            "spread_selection_score",
            "open_interest_selection_score",
            "volume_selection_score",
        ]
        additions = "\n".join(
            i
            + f'{name}=float(getattr(candidate, "{name}", 0.0)),'
            for name in names
        )
        text = text[:anchor.end()] + "\n" + additions + text[anchor.end():]

    write(relative, text)


def patch_cli() -> None:
    relative = "scripts/run_daily_scan.py"
    text = read(relative)

    text = re.sub(
        r'(--max-option-spread-pct".*?default=)0\.35',
        r"\g<1>0.25",
        text,
        count=1,
    )
    text = re.sub(
        r'(--min-option-open-interest".*?default=)0',
        r"\g<1>100",
        text,
        count=1,
    )
    text = re.sub(
        r'(--min-option-volume".*?default=)0',
        r"\g<1>10",
        text,
        count=1,
    )

    if "--option-oi-weight" not in text:
        match = re.search(
            r'(?m)^(?P<i>\s*)parser\.add_argument\("--min-option-volume".*?\)\s*$',
            text,
        )
        if not match:
            raise RuntimeError(
                f"{relative}: minimum option volume CLI argument not found"
            )
        i = match.group("i")
        additions = "\n".join(
            [
                i + 'parser.add_argument("--option-delta-weight", type=float, default=0.25)',
                i + 'parser.add_argument("--option-expiration-weight", type=float, default=0.15)',
                i + 'parser.add_argument("--option-strike-weight", type=float, default=0.10)',
                i + 'parser.add_argument("--option-spread-weight", type=float, default=0.15)',
                i + 'parser.add_argument("--option-oi-weight", type=float, default=0.20)',
                i + 'parser.add_argument("--option-volume-weight", type=float, default=0.15)',
            ]
        )
        text = text[:match.end()] + "\n" + additions + text[match.end():]

    scanner_anchor = re.search(
        r"(?m)^(?P<i>\s*)minimum_option_volume\s*=\s*args\.min_option_volume,\s*$",
        text,
    )
    if scanner_anchor and "open_interest_weight=args.option_oi_weight" not in text:
        i = scanner_anchor.group("i")
        additions = "\n".join(
            [
                i + "delta_weight=args.option_delta_weight,",
                i + "expiration_weight=args.option_expiration_weight,",
                i + "strike_weight=args.option_strike_weight,",
                i + "spread_weight=args.option_spread_weight,",
                i + "open_interest_weight=args.option_oi_weight,",
                i + "volume_weight=args.option_volume_weight,",
            ]
        )
        text = (
            text[:scanner_anchor.end()]
            + "\n"
            + additions
            + text[scanner_anchor.end():]
        )

    write(relative, text)


def verify_dataclass_fields(relative: str) -> None:
    text = read(relative)
    required = [
        "spread_pct",
        "contract_selection_score",
        "liquidity_score",
        "open_interest_selection_score",
        "volume_selection_score",
    ]
    missing = [name for name in required if f"{name}:" not in text]
    if missing:
        raise RuntimeError(
            f"{relative}: missing fields after patch: {missing}"
        )


def verify() -> None:
    verify_dataclass_fields("src/trading_ai/daily/models.py")
    verify_dataclass_fields(
        "src/trading_ai/daily/trade_candidate.py"
    )

    selector = read(
        "src/trading_ai/options/live_contract_selector.py"
    )
    scanner = read("src/trading_ai/daily/scanner.py")
    cli = read("scripts/run_daily_scan.py")

    checks = {
        "OI weighted in selector":
            "open_interest_weight" in selector,
        "volume weighted in selector":
            "volume_weight" in selector,
        "scanner captures liquidity score":
            "live.score.liquidity_score" in scanner,
        "CLI exposes OI weight":
            "--option-oi-weight" in cli,
        "CLI exposes volume weight":
            "--option-volume-weight" in cli,
    }

    failed = False
    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        failed = failed or not passed

    if failed:
        raise RuntimeError(
            "Liquidity-weighted selection verification failed"
        )


def main() -> None:
    patch_models()
    ensure_live_integration_present()
    patch_scanner()
    patch_recommender()
    patch_cli()
    verify()
    print(
        "Liquidity-weighted live contract selection "
        "applied successfully."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
