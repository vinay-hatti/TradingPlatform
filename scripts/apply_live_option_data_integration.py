from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def patch_models():
    model_specs = {
        "src/trading_ai/daily/models.py": "    final_score: float\n",
        "src/trading_ai/daily/trade_candidate.py": "    risk_score: float\n",
    }
    fields = (
        '    contract_ticker: str = ""\n'
        '    bid: float = 0.0\n'
        '    ask: float = 0.0\n'
        '    last_price: float = 0.0\n'
        '    price_source: str = ""\n'
        '    option_data_source: str = ""\n'
        '    quote_timestamp: str = ""\n'
        '    open_interest: int = 0\n'
        '    option_volume: int = 0\n'
        '    spread_pct: float = 0.0\n'
    )
    for relative, anchor in model_specs.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if "contract_ticker:" not in text:
            if anchor not in text:
                raise RuntimeError(
                    f"{relative}: insertion point not found"
                )
            text = text.replace(
                anchor,
                anchor + fields,
                1,
            )
        path.write_text(text, encoding="utf-8")


def patch_scanner():
    path = ROOT / "src/trading_ai/daily/scanner.py"
    text = path.read_text(encoding="utf-8")

    imports = (
        "from datetime import date, timedelta\n"
        "from trading_ai.options.live_contract_selector import (\n"
        "    LiveContractSelectionPolicy,\n"
        "    LiveOptionContractSelector,\n"
        ")\n"
        "from trading_ai.options.live_snapshot import "
        "LiveOptionDataError\n"
    )
    if "LiveOptionContractSelector" not in text:
        text = text.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n" + imports,
            1,
        )

    if "option_data_mode=" not in text:
        anchor = "        maximum_otm_pct=None,\n"
        text = text.replace(
            anchor,
            anchor
            + '        option_data_mode="live",\n'
            + "        maximum_option_spread_pct=0.35,\n"
            + "        minimum_option_open_interest=0,\n"
            + "        minimum_option_volume=0,\n",
            1,
        )

    if "self.option_data_mode" not in text:
        anchor = "        self.end = end\n"
        text = text.replace(
            anchor,
            anchor
            + "        self.option_data_mode = "
            + "str(option_data_mode).lower()\n"
            + '        if self.option_data_mode not in '
            + '{"live", "auto", "proxy"}:\n'
            + '            raise ValueError("option_data_mode must be '
            + 'live, auto, or proxy")\n',
            1,
        )

    if "self.live_selector" not in text:
        marker = "        self.strike_selector = (\n"
        block = (
            "        self.live_selector = None\n"
            '        if self.option_data_mode in {"live", "auto"}:\n'
            "            self.live_selector = "
            "LiveOptionContractSelector(\n"
            "                policy=LiveContractSelectionPolicy(\n"
            "                    target_abs_delta=float("
            "configured_target_delta),\n"
            "                    maximum_spread_pct=float("
            "maximum_option_spread_pct),\n"
            "                    minimum_open_interest=int("
            "minimum_option_open_interest),\n"
            "                    minimum_volume=int("
            "minimum_option_volume),\n"
            "                )\n"
            "            )\n"
        )
        text = text.replace(marker, block + marker, 1)

    start = text.find(
        "        option_price = self.pricing.option_price("
    )
    end = text.find(
        "        if not self._passes_greek_filters(greeks):",
        start,
    )
    if start < 0 or end < 0:
        raise RuntimeError(
            "scanner.py pricing block was not found"
        )

    block = '''        target_expiration = (
            date.fromisoformat(self.end[:10])
            + timedelta(days=self.pricing_dte)
        )
        contract_ticker = ""
        bid = ask = last_price = 0.0
        price_source = "BLACK_SCHOLES_PROXY"
        option_data_source = "PROXY"
        quote_timestamp = ""
        open_interest = option_volume = 0
        spread_pct = 0.0
        live_error = None

        if self.live_selector is not None:
            try:
                live = self.live_selector.select(
                    underlying=symbol,
                    signal=signal,
                    target_expiration=target_expiration,
                    target_strike=strike,
                    as_of=date.today(),
                )
                strike = live.strike
                expiry = live.expiration_date
                option_price = live.entry_price
                greeks = {
                    "delta": live.delta,
                    "gamma": live.gamma,
                    "theta": live.theta,
                    "vega": live.vega,
                    "rho": live.rho,
                    "volatility": live.implied_volatility,
                    "dte": live.dte,
                }
                contract_ticker = live.contract_ticker
                bid = live.bid
                ask = live.ask
                last_price = live.last_price
                price_source = live.price_source
                option_data_source = live.data_source
                quote_timestamp = live.quote_timestamp
                open_interest = live.open_interest
                option_volume = live.volume
                spread_pct = live.spread_pct
            except LiveOptionDataError as exc:
                live_error = exc
                if self.option_data_mode == "live":
                    raise

        if self.live_selector is None or live_error is not None:
            expiry = f"{self.pricing_dte}DTE_PROXY"
            option_price = self.pricing.option_price(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=self.pricing_dte,
            )
            greeks = self.pricing.greeks(
                signal=signal,
                spot=close,
                strike=strike,
                hv20=hv20,
                dte=self.pricing_dte,
            )
            if live_error is not None:
                option_data_source = "PROXY_FALLBACK"
                price_source = (
                    "BLACK_SCHOLES_PROXY: " + str(live_error)
                )

'''
    text = text[:start] + block + text[end:]
    text = text.replace(
        '            expiry=f"{self.pricing_dte}DTE_PROXY",\n',
        "            expiry=expiry,\n",
        1,
    )

    if "contract_ticker=contract_ticker" not in text:
        anchor = "            final_score=float(legacy_score),\n"
        fields = (
            "            contract_ticker=contract_ticker,\n"
            "            bid=float(bid),\n"
            "            ask=float(ask),\n"
            "            last_price=float(last_price),\n"
            "            price_source=price_source,\n"
            "            option_data_source=option_data_source,\n"
            "            quote_timestamp=quote_timestamp,\n"
            "            open_interest=int(open_interest),\n"
            "            option_volume=int(option_volume),\n"
            "            spread_pct=float(spread_pct),\n"
        )
        text = text.replace(
            anchor,
            anchor + fields,
            1,
        )

    path.write_text(text, encoding="utf-8")


def patch_recommender():
    path = ROOT / "src/trading_ai/daily/recommender.py"
    text = path.read_text(encoding="utf-8")
    if "contract_ticker=getattr" not in text:
        anchor = (
            "            risk_score=float(candidate.risk_score),\n"
        )
        fields = (
            '            contract_ticker=getattr('
            'candidate, "contract_ticker", ""),\n'
            '            bid=float(getattr(candidate, "bid", 0.0)),\n'
            '            ask=float(getattr(candidate, "ask", 0.0)),\n'
            '            last_price=float(getattr('
            'candidate, "last_price", 0.0)),\n'
            '            price_source=getattr('
            'candidate, "price_source", ""),\n'
            '            option_data_source=getattr('
            'candidate, "option_data_source", ""),\n'
            '            quote_timestamp=getattr('
            'candidate, "quote_timestamp", ""),\n'
            '            open_interest=int(getattr('
            'candidate, "open_interest", 0)),\n'
            '            option_volume=int(getattr('
            'candidate, "option_volume", 0)),\n'
            '            spread_pct=float(getattr('
            'candidate, "spread_pct", 0.0)),\n'
        )
        text = text.replace(anchor, anchor + fields, 1)

    if "Live contract:" not in text:
        anchor = "        notes = []\n"
        text = text.replace(
            anchor,
            anchor
            + '        if getattr(candidate, "contract_ticker", ""):\n'
            + '            notes.append('
            + 'f"Live contract: {candidate.contract_ticker}.")\n'
            + '            notes.append('
            + 'f"Entry source: {candidate.price_source}; quote time: '
            + '{candidate.quote_timestamp or \'unavailable\'}.")\n'
            + "        else:\n"
            + '            notes.append('
            + '"Synthetic proxy data; not a live listed contract.")\n',
            1,
        )
    path.write_text(text, encoding="utf-8")


def patch_cli():
    path = ROOT / "scripts/run_daily_scan.py"
    text = path.read_text(encoding="utf-8")

    if "--option-data-mode" not in text:
        anchor = (
            '    parser.add_argument("--pricing-dte", '
            'type=int, default=30)\n'
        )
        text = text.replace(
            anchor,
            anchor
            + '    parser.add_argument("--option-data-mode", '
            + 'choices=["live", "auto", "proxy"], default="live")\n'
            + '    parser.add_argument("--max-option-spread-pct", '
            + 'type=float, default=0.35)\n'
            + '    parser.add_argument("--min-option-open-interest", '
            + 'type=int, default=0)\n'
            + '    parser.add_argument("--min-option-volume", '
            + 'type=int, default=0)\n',
            1,
        )

    if "option_data_mode=args.option_data_mode" not in text:
        anchor = "        end=args.end,\n"
        text = text.replace(
            anchor,
            anchor
            + "        option_data_mode=args.option_data_mode,\n"
            + "        maximum_option_spread_pct="
            + "args.max_option_spread_pct,\n"
            + "        minimum_option_open_interest="
            + "args.min_option_open_interest,\n"
            + "        minimum_option_volume="
            + "args.min_option_volume,\n",
            1,
        )

    if "Option Data" not in text:
        anchor = (
            '    print(f"Minimum Score   : {args.min_score}")\n'
        )
        text = text.replace(
            anchor,
            anchor
            + '    print(f"Option Data     : '
            + '{args.option_data_mode}")\n',
            1,
        )

    if "candidate.contract_ticker" not in text:
        anchor = (
            '    print(f"   Strike         : '
            '${candidate.strike:.2f}")\n'
        )
        text = text.replace(
            anchor,
            anchor
            + '    print(f"   Contract       : '
            + '{candidate.contract_ticker or \'PROXY\'}")\n'
            + '    print(f"   Expiration     : '
            + '{candidate.expiry}")\n'
            + '    print(f"   Bid / Ask      : '
            + '${candidate.bid:.2f} / ${candidate.ask:.2f}")\n'
            + '    print(f"   Price Source   : '
            + '{candidate.price_source}")\n'
            + '    print(f"   Data Source    : '
            + '{candidate.option_data_source}")\n'
            + '    print(f"   Quote Time     : '
            + '{candidate.quote_timestamp or \'unavailable\'}")\n',
            1,
        )
        text = text.replace(
            '    print(f"   Expiry Proxy   : '
            '{candidate.expiry}")\n',
            "",
        )

    if "trade.contract_ticker" not in text:
        anchor = (
            '    print(f"   Strike      : ${trade.strike:.2f}")\n'
        )
        text = text.replace(
            anchor,
            anchor
            + '    print(f"   Contract    : '
            + '{trade.contract_ticker or \'PROXY\'}")\n'
            + '    print(f"   Expiration  : {trade.expiry}")\n'
            + '    print(f"   Bid / Ask   : '
            + '${trade.bid:.2f} / ${trade.ask:.2f}")\n'
            + '    print(f"   Price Src   : '
            + '{trade.price_source}")\n'
            + '    print(f"   Quote Time  : '
            + '{trade.quote_timestamp or \'unavailable\'}")\n',
            1,
        )

    path.write_text(text, encoding="utf-8")


def patch_reporter(relative):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    fields = [
        "contract_ticker",
        "bid",
        "ask",
        "last_price",
        "price_source",
        "option_data_source",
        "quote_timestamp",
        "open_interest",
        "option_volume",
        "spread_pct",
    ]
    for field in fields:
        if f'"{field}",' not in text:
            text = text.replace(
                '            "expiry",\n',
                '            "expiry",\n'
                + f'            "{field}",\n',
                1,
            )
    path.write_text(text, encoding="utf-8")


def verify():
    scanner = (
        ROOT / "src/trading_ai/daily/scanner.py"
    ).read_text(encoding="utf-8")
    cli = (
        ROOT / "scripts/run_daily_scan.py"
    ).read_text(encoding="utf-8")

    checks = {
        "live selector in scanner":
            "LiveOptionContractSelector" in scanner,
        "live option mode":
            "option_data_mode" in scanner,
        "contract ticker output":
            "candidate.contract_ticker" in cli,
        "option-data CLI flag":
            "--option-data-mode" in cli,
    }
    failed = False
    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        failed = failed or not passed
    if failed:
        raise RuntimeError(
            "Live option integration verification failed"
        )


def main():
    patch_models()
    patch_scanner()
    patch_recommender()
    patch_cli()
    patch_reporter(
        "src/trading_ai/daily/reporter.py"
    )
    patch_reporter(
        "src/trading_ai/daily/trade_reporter.py"
    )
    verify()
    print("Live option contract data integration applied.")


if __name__ == "__main__":
    main()
