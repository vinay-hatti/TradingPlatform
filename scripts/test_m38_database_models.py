from trading_ai.database.base import Base
from trading_ai.execution_orchestration import database_models  # noqa
names=set(Base.metadata.tables)
assert {'execution_orchestration_orders','execution_orchestration_events','execution_orchestration_runs'} <= names
print('Milestone 38 database model assertions passed.')
