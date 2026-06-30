from trading_ai.scanner.engine import ScannerEngine


def main():

    scanner = ScannerEngine()

    results = scanner.run_scan()

    print("\nTOP SETUPS:\n")

    for r in results[:10]:
        print(r)


if __name__ == "__main__":
    main()
