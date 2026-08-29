from pathlib import Path


def main():

    files = [
        Path("data/paper/orders.json"),
        Path("data/paper/positions.json"),
        Path("data/paper/cash.json"),
    ]

    for file in files:
        if file.exists():
            file.unlink()
            print(f"Deleted {file}")

    print("Paper trading state reset.")


if __name__ == "__main__":
    main()
