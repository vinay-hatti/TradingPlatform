import argparse
from datetime import datetime
from trading_ai.options.quality import OptionQualityScorer
from trading_ai.app.bootstrap import container
from trading_ai.backtest.config import BacktestConfig
from trading_ai.options.pricing import BlackScholesPricer


def estimate_win_probability(score, regime):

    base = 0.50 + ((score - 50.0) / 100.0)

    if regime == "VOLATILE":
        base += 0.05
    elif regime == "BULL_TREND":
        base += 0.03
    elif regime == "BEAR_TREND":
        base += 0.02

    return max(0.35, min(0.80, base))


def estimate_reward_risk(score, iv, delta):

    rr = 1.0
    rr += max(0.0, (score - 60.0) / 20.0)
    rr += max(0.0, abs(delta) - 0.30)

    if 0.20 <= iv <= 0.80:
        rr += 0.30

    return max(0.5, min(4.0, rr))


def calculate_kelly(win_prob, reward_risk):

    p = win_prob
    q = 1.0 - p
    b = max(reward_risk, 0.01)

    kelly = (b * p - q) / b

    return max(0.0, min(kelly, 0.25))


def confidence_grade(rank_score):

    if rank_score >= 95:
        return "A+"
    if rank_score >= 90:
        return "A"
    if rank_score >= 85:
        return "B+"
    if rank_score >= 80:
        return "B"
    if rank_score >= 75:
        return "C+"
    return "C"


def time_to_expiry_years(expiry, as_of_date):

    try:
        expiry_dt = datetime.strptime(str(expiry), "%Y-%m-%d")
        as_of_dt = datetime.strptime(str(as_of_date), "%Y-%m-%d")
        days = (expiry_dt - as_of_dt).days
        return max(days / 365.0, 1 / 365.0)
    except Exception:
        return 30 / 365.0

def days_to_expiry(expiry, as_of_date):

    try:
        expiry_dt = datetime.strptime(str(expiry), "%Y-%m-%d")
        as_of_dt = datetime.strptime(str(as_of_date), "%Y-%m-%d")
        return (expiry_dt - as_of_dt).days
    except Exception:
        return 30

def export_scanner_results(rows, path=None):

    import csv
    from pathlib import Path

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/scanner_results_{timestamp}.csv"

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "symbol",
                "signal",
                "strategy",
                "rank_score",
                "score",
                "confidence",
                "affordability_status",
                "recommended_position_value",
                "option_price_estimate",
                "estimated_contract_cost",
                "recommended_contracts",
                "win_probability",
                "reward_risk",
                "kelly_fraction",
                "expected_return",
                "regime",
                "price",
                "strike",
                "expiry",
                "days_to_expiry",
                "delta",
                "iv",
                "open_interest",
                "option_score",
                "probability_of_profit",
                "liquidity_score",
                "delta_score",
                "iv_score",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Scanner results exported to {path}")


def export_scanner_results_json(rows, path=None):

    import json
    from pathlib import Path

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/scanner_results_{timestamp}.json"

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)

    print(f"Scanner JSON exported to {path}")


def parse_args():

    parser = argparse.ArgumentParser(
        description="Run Trading AI scanner"
    )

    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,NVDA,AMD,GOOGL,AMZN,META,TSLA",
    )

    parser.add_argument(
        "--start",
        default="2026-01-01",
    )

    parser.add_argument(
        "--end",
        default="2026-06-01",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export scanner results to CSV",
    )

    parser.add_argument(
        "--export-json",
        action="store_true",
        help="Export scanner results to JSON",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Portfolio capital used for recommended position sizing",
    )

    parser.add_argument(
        "--only-affordable",
        action="store_true",
        help="Only show trades where recommended contracts > 0",
    )

    parser.add_argument(
        "--min-confidence",
        default=None,
        choices=["C", "C+", "B", "B+", "A", "A+"],
        help="Minimum confidence grade to show",
    )

    parser.add_argument(
        "--min-days-to-expiry",
        type=int,
        default=30,
        help="Minimum option days to expiry",
    )

    parser.add_argument(
        "--max-days-to-expiry",
        type=int,
        default=730,
        help="Maximum option days to expiry",
    )

    return parser.parse_args()


def main():

    args = parse_args()
    pricer = BlackScholesPricer()
    pricer = BlackScholesPricer()

    quality_scorer = OptionQualityScorer()

    symbols = [
        s.strip().upper()
        for s in args.symbols.split(",")
        if s.strip()
    ]

    config = BacktestConfig(
        symbols=symbols,
        start=args.start,
        end=args.end,
        min_call_score=60.0,
        min_put_score=60.0,
        min_option_price=0.50,
        min_abs_delta=0.30,
        max_abs_delta=0.70,
    )

    results = []

    for symbol in symbols:

        df = container.market.get_history(
            symbol,
            config.start,
            config.end,
        )

        df = container.pipeline.run(df)

        if df.empty:
            continue

        row = df.iloc[-1]
        ctx = row["trade_context"]

        analytics = container.market.provider.get_analytics(symbol)

        recommendation = container.strategy_engine.recommend(
            symbol,
            ctx,
            analytics,
        )

        if recommendation is None:
            continue

        if recommendation.signal == "CALL" and recommendation.score < config.min_call_score:
            continue

        if recommendation.signal == "PUT" and recommendation.score < config.min_put_score:
            continue

        if abs(recommendation.delta) < config.min_abs_delta:
            continue

        if abs(recommendation.delta) > config.max_abs_delta:
            continue

        option = recommendation.option

        if option is None:
            continue

        if option.implied_volatility <= 0:
            continue

        liquidity_bonus = min(option.open_interest / 1000.0, 10.0)

        delta_quality = 10.0 - min(
            abs(abs(recommendation.delta) - 0.45) * 20,
            10.0,
        )

        iv_bonus = 0.0
        if 0.20 <= option.implied_volatility <= 0.80:
            iv_bonus = 5.0

        option_quality = quality_scorer.score(
            option,
            recommendation.signal,
        )

        dte = days_to_expiry(
            recommendation.expiry,
            args.end,
        )

        if dte < args.min_days_to_expiry:
            continue

        if dte > args.max_days_to_expiry:
            continue

        win_probability = estimate_win_probability(
            recommendation.score,
            recommendation.regime,
        )

        reward_risk = estimate_reward_risk(
            recommendation.score,
            option.implied_volatility,
            recommendation.delta,
        )

        kelly_fraction = calculate_kelly(
            win_probability,
            reward_risk,
        )

        expected_return = (
            win_probability * reward_risk
            - (1.0 - win_probability)
        )

        expected_return_score = expected_return * 10.0

        rank_score = (
            recommendation.score
            + liquidity_bonus
            + delta_quality
            + iv_bonus
            + expected_return_score
        )

        confidence = confidence_grade(rank_score)

        time_to_expiry = time_to_expiry_years(
            recommendation.expiry,
            args.end,
        )

        option_price_estimate = pricer.price(
            spot=float(recommendation.price),
            strike=float(recommendation.strike),
            time_to_expiry=time_to_expiry,
            volatility=max(float(option.implied_volatility), 0.0001),
            option_type=recommendation.signal,
        )

        option_price_estimate = max(option_price_estimate, 0.05)

        estimated_contract_cost = option_price_estimate * 100.0

        recommended_position_value = args.capital * kelly_fraction * 0.5

        max_position_value = args.capital * 0.05

        recommended_position_value = min(
            recommended_position_value,
            max_position_value,
        )

#        recommended_contracts = int(
#            recommended_position_value / max(estimated_contract_cost, 1.0)
#        )
#
#        recommended_contracts = max(1, recommended_contracts)
        if estimated_contract_cost > recommended_position_value:
            recommended_contracts = 0
            affordability_status = "TOO_EXPENSIVE"
        else:
            recommended_contracts = int(
                recommended_position_value / max(estimated_contract_cost, 1.0)
            )
            recommended_contracts = max(1, recommended_contracts)
            affordability_status = "OK"

        results.append({
            "symbol": symbol,
            "signal": recommendation.signal,
            "strategy": recommendation.strategy,
            "rank_score": rank_score,
            "score": recommendation.score,
            "confidence": confidence,
            "win_probability": win_probability,
            "reward_risk": reward_risk,
            "kelly_fraction": kelly_fraction,
            "expected_return": expected_return,
            "regime": recommendation.regime,
            "price": recommendation.price,
            "strike": recommendation.strike,
            "expiry": recommendation.expiry,
            "days_to_expiry": dte,
            "delta": recommendation.delta,
            "iv": option.implied_volatility,
            "open_interest": option.open_interest,
            "recommended_position_value": recommended_position_value,
            "option_price_estimate": option_price_estimate,
            "estimated_contract_cost": estimated_contract_cost,
            "recommended_contracts": recommended_contracts,
            "affordability_status": affordability_status,
            "option_score": option_quality["option_score"],
            "probability_of_profit": option_quality["probability_of_profit"],
            "liquidity_score": option_quality["liquidity_score"],
            "delta_score": option_quality["delta_score"],
            "iv_score": option_quality["iv_score"],
        })

    results = sorted(
        results,
        key=lambda x: x["rank_score"],
        reverse=True,
    )

    if args.only_affordable:
        results = [
            r for r in results
            if r["affordability_status"] == "OK"
        ]

    if args.min_confidence:
        confidence_rank = {
            "C": 1,
            "C+": 2,
            "B": 3,
            "B+": 4,
            "A": 5,
            "A+": 6,
        }

        min_rank = confidence_rank[args.min_confidence]

        results = [
            r for r in results
            if confidence_rank.get(r["confidence"], 0) >= min_rank
        ]

    print()
    print("========== Scanner Results ==========")

    for r in results[:args.limit]:
        print(
            f"{r['symbol']:5} | "
            f"{r['signal']:4} | "
            f"{r['strategy']:10} | "
            f"Rank={r['rank_score']:6.2f} | "
            f"Conf={r['confidence']:2} | "
            f"Status={r['affordability_status']:13} | "
            f"Pos=${r['recommended_position_value']:8.2f} | "
            f"Opt=${r['option_price_estimate']:7.2f} | "
            f"Cost=${r['estimated_contract_cost']:8.2f} | "
            f"Qty={r['recommended_contracts']:3} | "
            f"Win={r['win_probability']:6.2%} | "
            f"OptScore={r['option_score']:6.2f} | "
            f"POP={r['probability_of_profit']:6.2%} | "
            f"Liq={r['liquidity_score']:6.2f} | "
            f"RR={r['reward_risk']:4.2f} | "
            f"Kelly={r['kelly_fraction']:5.2%} | "
            f"Score={r['score']:6.2f} | "
            f"Regime={r['regime']:12} | "
            f"Price={r['price']:8.2f} | "
            f"Strike={r['strike']:8.2f} | "
            f"Exp={r['expiry']} | "
            f"DTE={r['days_to_expiry']:4} | "
            f"Delta={r['delta']:6.2f} | "
            f"IV={r['iv']:6.2%} | "
            f"OI={r['open_interest']}"
        )

    print("=====================================")

    if args.export_csv:
        export_scanner_results(results[:args.limit])

    if args.export_json:
        export_scanner_results_json(results[:args.limit])

    print()


if __name__ == "__main__":
    main()
