from types import SimpleNamespace
from trading_ai.daily.scanner import DailyScanner


def scanner(mode='automatic', lo=14, hi=90, targets=4, cap=3):
    value = DailyScanner.__new__(DailyScanner)
    value.expiration_mode = mode
    value.minimum_dte = lo
    value.maximum_dte = hi
    value.maximum_expirations_per_symbol = targets
    value.maximum_trades_per_expiration = cap
    value.pricing_dte = 30
    return value


def main():
    assert scanner()._target_dtes() == [14, 39, 65, 90]
    assert scanner('short')._target_dtes() == [14, 16, 19, 21]
    assert scanner('swing')._target_dtes() == [22, 30, 37, 45]
    assert scanner('medium')._target_dtes() == [46, 56, 65, 75]
    assert scanner('fixed')._target_dtes() == [30]

    value = scanner(cap=2)
    candidates = {
        'A': SimpleNamespace(ai_score=99, expiry='2026-08-21'),
        'B': SimpleNamespace(ai_score=98, expiry='2026-08-21'),
        'C': SimpleNamespace(ai_score=97, expiry='2026-08-21'),
        'D': SimpleNamespace(ai_score=96, expiry='2026-09-18'),
    }
    value.scan_symbol = lambda symbol: candidates[symbol]
    ranked = value.scan(['A', 'B', 'C', 'D'])
    assert [item.ai_score for item in ranked] == [99, 98, 96]
    print('Milestone 43 DTE horizon policy assertions passed.')


if __name__ == '__main__':
    main()
