import csv

from trading_ai.walkforward.report import WalkForwardReport


def main():

    summary = "reports/walkforward/summary.csv"

    with open(summary, "r") as f:
        rows = list(csv.DictReader(f))

    path = WalkForwardReport().generate(
        rows,
        path="reports/walkforward/report.html",
    )

    print(f"Walk-forward report created: {path}")


if __name__ == "__main__":
    main()
