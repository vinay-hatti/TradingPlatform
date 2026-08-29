from datetime import date

from trading_ai.trend_intelligence.forecast_repository import _business_day_age as forecast_age
from trading_ai.trend_intelligence.institutional_repository import _business_day_age as institutional_age


def main():
    assert forecast_age(date(2026, 7, 24), date(2026, 7, 28)) == 2
    assert institutional_age(date(2026, 7, 24), date(2026, 7, 28)) == 2
    assert forecast_age(date(2026, 7, 28), date(2026, 7, 28)) == 0
    assert forecast_age(date(2026, 7, 25), date(2026, 7, 27)) == 1
    print("Milestone 53 trend snapshot freshness assertions passed.")


if __name__ == "__main__":
    main()
