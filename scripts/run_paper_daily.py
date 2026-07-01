import subprocess
import sys


def run(cmd):

    print()
    print("Running:", " ".join(cmd))

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():

    run([sys.executable, "scripts/optimize_portfolio.py"])
    run([sys.executable, "scripts/paper_trade_from_optimizer.py"])
    run([sys.executable, "scripts/mark_paper_positions.py"])
    run([sys.executable, "scripts/paper_status.py"])

    print()
    print("Paper daily workflow complete.")


if __name__ == "__main__":
    main()
