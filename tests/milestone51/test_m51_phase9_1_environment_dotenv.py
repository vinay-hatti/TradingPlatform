from trading_ai.paper_trading.operational_readiness import EnvironmentValidator


def test_environment_validator_reads_dotenv(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "src/trading_ai").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / ".env").write_text(
        "DB_USER=user\n"
        "DB_PASSWORD=pass\n"
        "DB_HOST=localhost\n"
        "DB_PORT=5432\n"
        "DB_NAME=trading\n"
        "POLYGON_API_KEY=test-key\n"
    )
    controls = EnvironmentValidator().validate(
        repo_root=tmp_path,
        require_database_url=True,
        require_polygon_key=True,
    )
    by_id = {row.control_id: row for row in controls}
    assert by_id["ENV-DATABASE-CONFIGURATION"].status == "PASS"
    assert by_id["ENV-POLYGON-CONFIGURATION"].status == "PASS"
