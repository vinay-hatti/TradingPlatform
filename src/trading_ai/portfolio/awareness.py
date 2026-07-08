import csv
from pathlib import Path


class PortfolioAwareness:

    def __init__(
        self,
        positions_file="data/portfolio/current_positions.csv",
        max_symbol_positions=1,
        max_sector_positions=3,
        concentration_penalty=15.0,
        duplicate_penalty=25.0,
    ):
        self.positions_file = Path(positions_file)
        self.max_symbol_positions = int(max_symbol_positions)
        self.max_sector_positions = int(max_sector_positions)
        self.concentration_penalty = float(concentration_penalty)
        self.duplicate_penalty = float(duplicate_penalty)
        self.positions = self.load_positions()

    def load_positions(self):

        if not self.positions_file.exists():
            return []

        with open(self.positions_file, "r") as f:
            return list(csv.DictReader(f))

    def symbol_count(self, symbol):

        symbol = str(symbol).upper()

        return sum(
            1
            for p in self.positions
            if str(p.get("symbol", "")).upper() == symbol
        )

    def sector_count(self, sector):

        sector = str(sector)

        return sum(
            1
            for p in self.positions
            if str(p.get("sector", "")) == sector
        )

    def exposure_summary(self):

        by_symbol = {}
        by_sector = {}

        for p in self.positions:
            symbol = str(p.get("symbol", "")).upper()
            sector = str(p.get("sector", "Unknown"))

            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
            by_sector[sector] = by_sector.get(sector, 0) + 1

        return {
            "positions": len(self.positions),
            "by_symbol": by_symbol,
            "by_sector": by_sector,
        }

    def evaluate(
        self,
        symbol,
        sector="Unknown",
    ):
        symbol = str(symbol).upper()
        sector = str(sector or "Unknown")

        notes = []
        penalty = 0.0
        allowed = True

        symbol_count = self.symbol_count(symbol)
        sector_count = self.sector_count(sector)

        if symbol_count >= self.max_symbol_positions:
            penalty += self.duplicate_penalty
            notes.append(
                f"Existing position in {symbol}; duplicate exposure penalty applied."
            )

        if sector_count >= self.max_sector_positions:
            penalty += self.concentration_penalty
            notes.append(
                f"Sector exposure high for {sector}; concentration penalty applied."
            )

        return {
            "allowed": allowed,
            "penalty": penalty,
            "notes": notes,
            "symbol_count": symbol_count,
            "sector_count": sector_count,
        }
