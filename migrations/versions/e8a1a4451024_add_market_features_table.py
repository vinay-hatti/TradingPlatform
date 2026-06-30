from alembic import op
import sqlalchemy as sa

# REQUIRED Alembic identifiers
revision = "e8a1a4451024"
down_revision = None  # or put previous migration id if exists
branch_labels = None
depends_on = None

def upgrade():

    op.create_table(
        "market_features",

        sa.Column("symbol", sa.String(16), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),

        # Trend
        sa.Column("ema20", sa.Float),
        sa.Column("ema50", sa.Float),
        sa.Column("ema200", sa.Float),

        # Momentum
        sa.Column("rsi14", sa.Float),
        sa.Column("macd", sa.Float),
        sa.Column("macd_signal", sa.Float),

        # Volatility
        sa.Column("atr14", sa.Float),
        sa.Column("bollinger_width", sa.Float),
        sa.Column("hv20", sa.Float),

        # Volume
        sa.Column("volume_sma20", sa.Float),
        sa.Column("volume_ratio", sa.Float),

        # VWAP / Price position
        sa.Column("vwap", sa.Float),
        sa.Column("price_vs_vwap", sa.Float),

        # Regime tagging (VERY IMPORTANT)
        sa.Column("market_regime", sa.String(32)),
    )


def downgrade():
    op.drop_table("market_features")
