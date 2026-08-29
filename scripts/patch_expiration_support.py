from pathlib import Path

def patch_scanner():
    p = Path("src/trading_ai/daily/scanner.py")
    t = p.read_text(encoding="utf-8")
    imp = "from trading_ai.daily.expiry_selector import StandardFridayExpirySelector\n"
    anchor = "from trading_ai.daily.models import DailyCandidate\n"
    if imp not in t:
        t = t.replace(anchor, anchor + imp)
    if "self.expiry_selector" not in t:
        t = t.replace(
            "        self.end = end\n",
            "        self.end = end\n        self.expiry_selector = StandardFridayExpirySelector()\n",
            1,
        )
    if "expiry_selection = self.expiry_selector.select(" not in t:
        t = t.replace(
            "        return DailyCandidate(\n",
            "        expiry_selection = self.expiry_selector.select(\n"
            "            valuation_date=self.end,\n"
            "            target_dte=self.pricing_dte,\n"
            "        )\n\n"
            "        return DailyCandidate(\n",
            1,
        )
    t = t.replace(
        '            expiry=f"{self.pricing_dte}DTE_PROXY",\n',
        "            expiry=expiry_selection.expiration_iso,\n"
        "            expiry_source=expiry_selection.source,\n",
    )
    t = t.replace(
        '            dte=int(greeks["dte"]),\n',
        "            dte=int(expiry_selection.actual_dte),\n",
        1,
    )
    p.write_text(t, encoding="utf-8")

def patch_recommender():
    p = Path("src/trading_ai/daily/recommender.py")
    t = p.read_text(encoding="utf-8")
    if "expiry_source=" not in t:
        t = t.replace(
            "            dte=int(candidate.dte),\n",
            "            dte=int(candidate.dte),\n"
            '            expiry_source=getattr(candidate, "expiry_source", "STANDARD_FRIDAY_PROXY"),\n',
            1,
        )
    if "standard-Friday proxy" not in t:
        marker = '        elif candidate.signal == "PUT":\n            notes.append("Bearish options candidate.")\n'
        if marker in t:
            t = t.replace(
                marker,
                marker
                + '        if getattr(candidate, "expiry_source", "") == "STANDARD_FRIDAY_PROXY":\n'
                + '            notes.append("Expiration is a standard-Friday proxy; verify the listed contract with the broker.")\n',
            )
    p.write_text(t, encoding="utf-8")

def patch_report(path_string, live):
    p = Path(path_string)
    t = p.read_text(encoding="utf-8")
    if '"expiry_source",' not in t:
        t = t.replace(
            '            "expiry",\n            "dte",\n',
            '            "expiry",\n            "expiry_source",\n            "dte",\n',
        )
        t = t.replace(
            '            "expiry",\n            "option_price",\n',
            '            "expiry",\n            "expiry_source",\n            "option_price",\n',
        )
    obj = "t" if live else "c"
    if f'"expiry_source": {obj}.expiry_source' not in t:
        t = t.replace(
            f'                "expiry": {obj}.expiry,\n',
            f'                "expiry": {obj}.expiry,\n'
            f'                "expiry_source": {obj}.expiry_source,\n',
            1,
        )
    if '("Expiration", "expiry")' not in t:
        t = t.replace(
            '("Strike", "strike"),',
            '("Strike", "strike"), ("Expiration", "expiry"), '
            '("DTE", "dte"), ("Expiry Source", "expiry_source"),',
            1,
        )
    p.write_text(t, encoding="utf-8")

def patch_cli():
    p = Path("scripts/run_daily_scan.py")
    t = p.read_text(encoding="utf-8")
    t = t.replace("Expiry Proxy", "Expiration")
    if "Expiry Source" not in t:
        t = t.replace(
            'print(f" Expiration : {c.expiry}")',
            'print(f" Expiration : {c.expiry}")\n'
            '    print(f" Expiry Source : {c.expiry_source}")',
        )
        t = t.replace(
            'print(f"   Expiration     : {candidate.expiry}")',
            'print(f"   Expiration     : {candidate.expiry}")\n'
            '    print(f"   Expiry Source  : {candidate.expiry_source}")',
        )
    if "t.expiry" not in t and 'print(f" Strike : ${t.strike:.2f}")' in t:
        t = t.replace(
            'print(f" Strike : ${t.strike:.2f}")',
            'print(f" Strike : ${t.strike:.2f}")\n'
            '    print(f" Expiration : {t.expiry}")\n'
            '    print(f" Expiry Source : {t.expiry_source}")',
        )
    if "trade.expiry" not in t and 'print(f"   Strike      : ${trade.strike:.2f}")' in t:
        t = t.replace(
            'print(f"   Strike      : ${trade.strike:.2f}")',
            'print(f"   Strike      : ${trade.strike:.2f}")\n'
            '    print(f"   Expiration  : {trade.expiry}")\n'
            '    print(f"   Expiry Src  : {trade.expiry_source}")',
        )
    p.write_text(t, encoding="utf-8")

def main():
    patch_scanner()
    patch_recommender()
    patch_report("src/trading_ai/daily/trade_reporter.py", True)
    patch_report("src/trading_ai/daily/reporter.py", False)
    patch_cli()
    print("Expiration support applied.")

if __name__ == "__main__":
    main()
