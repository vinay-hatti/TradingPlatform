"""Milestone 69 institutional option valuation and mispricing intelligence.
Revision ID: m69_001
Revises: m68_001
"""
from alembic import op
import sqlalchemy as sa
revision='m69_001'; down_revision='m68_001'; branch_labels=None; depends_on=None

def upgrade():
 op.create_table('institutional_option_valuation_snapshots',sa.Column('snapshot_id',sa.String(128),primary_key=True),sa.Column('contract_recommendation_id',sa.String(128),nullable=False),sa.Column('opportunity_id',sa.String(128),nullable=False),sa.Column('symbol',sa.String(32),nullable=False),sa.Column('classification',sa.String(48),nullable=False),sa.Column('market_mid',sa.Float(),nullable=False),sa.Column('fair_value',sa.Float(),nullable=False),sa.Column('mispricing_pct',sa.Float(),nullable=False),sa.Column('edge_score',sa.Float(),nullable=False),sa.Column('confidence',sa.Float(),nullable=False),sa.Column('stability_index',sa.Float(),nullable=False),sa.Column('state_hash',sa.String(128),nullable=False),sa.Column('snapshot_timestamp',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False),sa.UniqueConstraint('contract_recommendation_id','state_hash',name='uq_m69_contract_state'))
 for n,c in [('ix_m69_val_opportunity','opportunity_id'),('ix_m69_val_symbol','symbol'),('ix_m69_val_edge','edge_score')]:op.create_index(n,'institutional_option_valuation_snapshots',[c])
 op.create_table('institutional_option_valuation_publications',sa.Column('publication_id',sa.String(128),primary_key=True),sa.Column('publication_name',sa.String(128),nullable=False,unique=True),sa.Column('status',sa.String(32),nullable=False),sa.Column('contract_count',sa.Integer(),nullable=False),sa.Column('underpriced_count',sa.Integer(),nullable=False),sa.Column('overpriced_count',sa.Integer(),nullable=False),sa.Column('published_at',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False))
 op.create_table('institutional_option_edge_ledger',sa.Column('ledger_id',sa.String(128),primary_key=True),sa.Column('contract_recommendation_id',sa.String(128),nullable=False),sa.Column('opportunity_id',sa.String(128),nullable=False),sa.Column('state_hash',sa.String(128),nullable=False),sa.Column('observed_at',sa.String(64),nullable=False),sa.Column('payload_json',sa.JSON(),nullable=False))
 op.create_index('ix_m69_edge_contract','institutional_option_edge_ledger',['contract_recommendation_id'])
def downgrade():
 op.drop_index('ix_m69_edge_contract',table_name='institutional_option_edge_ledger');op.drop_table('institutional_option_edge_ledger');op.drop_table('institutional_option_valuation_publications')
 for n in ('ix_m69_val_edge','ix_m69_val_symbol','ix_m69_val_opportunity'):op.drop_index(n,table_name='institutional_option_valuation_snapshots')
 op.drop_table('institutional_option_valuation_snapshots')
