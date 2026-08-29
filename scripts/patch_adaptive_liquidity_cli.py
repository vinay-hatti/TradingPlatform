from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def main():
    scanner_path = ROOT / "src/trading_ai/daily/scanner.py"
    scanner = scanner_path.read_text()
    if "liquidity_data_mode=" not in scanner:
        scanner = scanner.replace(
            "        volume_weight=0.15,\n",
            "        volume_weight=0.15,\n        liquidity_data_mode=\"adaptive\",\n",
            1,
        )
    if "liquidity_data_mode=str(liquidity_data_mode)" not in scanner:
        scanner = scanner.replace(
            "                    volume_weight=float(volume_weight),\n",
            "                    volume_weight=float(volume_weight),\n"
            "                    liquidity_data_mode=str(liquidity_data_mode),\n",
            1,
        )
    scanner_path.write_text(scanner)

    cli_path = ROOT / "scripts/run_daily_scan.py"
    cli = cli_path.read_text()
    if "--liquidity-data-mode" not in cli:
        match = re.search(
            r'(?m)^(?P<i>\s*)parser\.add_argument\("--option-volume-weight".*?\)\s*$',
            cli,
        )
        if not match:
            raise RuntimeError("option-volume-weight argument not found")
        i = match.group("i")
        replacement = match.group(0) + "\n" + i + (
            'parser.add_argument("--liquidity-data-mode", '
            'choices=["adaptive", "strict"], default="adaptive")'
        )
        cli = cli[:match.start()] + replacement + cli[match.end():]
    if "liquidity_data_mode=args.liquidity_data_mode" not in cli:
        cli = cli.replace(
            "        volume_weight=args.option_volume_weight,\n",
            "        volume_weight=args.option_volume_weight,\n"
            "        liquidity_data_mode=args.liquidity_data_mode,\n",
            1,
        )
    cli_path.write_text(cli)
    print("Adaptive liquidity CLI integration applied.")

if __name__ == "__main__":
    main()
