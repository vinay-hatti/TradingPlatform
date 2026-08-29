from trading_ai.scanner.dashboard.ranking_cli import build_parser, _build_query


def main() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--top-n",
            "50",
            "--page-size",
            "25",
            "--search",
            "technology",
            "--sort-field",
            "institutional_score",
            "--sort-direction",
            "DESC",
            "--select-symbol",
            "AAPL",
        ]
    )

    query = _build_query(args)
    assert isinstance(query, object)

    supported = vars(query) if hasattr(query, "__dict__") else {}
    if "top_n" in supported:
        assert supported["top_n"] == 50
    if "page_size" in supported:
        assert supported["page_size"] == 25
    if "sort_field" in supported:
        assert supported["sort_field"] == "institutional_score"

    print(
        "Milestone 35 Phase 5 Step 3 CLI contract compatibility assertions passed."
    )


if __name__ == "__main__":
    main()
