import subprocess
import sys


def main():

    commands = [
        [sys.executable, "scripts/optimize_portfolio.py"],
        [sys.executable, "scripts/build_dashboard.py"],
    ]

    for cmd in commands:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    print()
    print("Dashboard ready: reports/dashboard.html")


if __name__ == "__main__":
    main()
