from trading_ai.walkforward.splitter import WalkForwardSplitter


def main():

    splitter = WalkForwardSplitter(
        start="2026-01-01",
        end="2026-06-01",
        train_months=2,
        test_months=1,
        step_months=1,
    )

    windows = splitter.windows()

    print()
    print("========== Walk-Forward Splitter Test ==========")

    for w in windows:
        print(
            f"Window {w.index}: "
            f"Train {w.train_start} -> {w.train_end} | "
            f"Test {w.test_start} -> {w.test_end}"
        )

    print(f"Total Windows: {len(windows)}")
    print("================================================")
    print()


if __name__ == "__main__":
    main()
