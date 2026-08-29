"""M68.2.1.15 certified Trade Builder readiness integrity.

Revision ID: m68_004
Revises: m68_003
"""

from alembic import op


revision = "m68_004"
down_revision = "m68_003"
branch_labels = None
depends_on = None


CONSTRAINT = "ck_m62_ready_requires_final_certification"


def upgrade() -> None:
    # NOT VALID allows the controlled recovery to reconcile pre-existing false
    # readiness without blocking installation. PostgreSQL still enforces the
    # constraint for every insert/update after this migration.
    op.execute(f"""
        ALTER TABLE institutional_option_execution_recommendations
        ADD CONSTRAINT {CONSTRAINT}
        CHECK (
            NOT ready_for_trade_builder
            OR ((
                payload_json::jsonb #>>
                  '{{trade_plan_certification,status}}' = 'PASS'
                AND payload_json::jsonb #>>
                  '{{trade_plan_certification,certification_scope}}'
                    = 'INSTITUTIONAL_OPTIONS_FINAL_PLAN'
                AND payload_json::jsonb #>>
                  '{{trade_plan_certification,execution_disposition}}'
                    = 'READY_NOW'
                AND payload_json::jsonb #>>
                  '{{trade_plan_certification,trade_builder_ready}}'
                    = 'true'
            ) IS TRUE)
        ) NOT VALID
    """)


def downgrade() -> None:
    op.execute(f"""
        ALTER TABLE institutional_option_execution_recommendations
        DROP CONSTRAINT IF EXISTS {CONSTRAINT}
    """)
