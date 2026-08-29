import subprocess
import sys


def main():

    cmd = [
        sys.executable,
        "scripts/run_scanner.py",
        "--symbols",
        "AAPL,MSFT,NVDA,AMD,GOOGL,AMZN,META,TSLA",
        "--only-affordable",
        "--min-confidence",
        "A",
        "--min-days-to-expiry",
        "45",
        "--export-csv",
        "--export-json",
    ]

    result = subprocess.run(cmd)

    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
