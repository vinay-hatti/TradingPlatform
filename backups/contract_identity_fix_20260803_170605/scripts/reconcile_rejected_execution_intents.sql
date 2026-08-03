-- Reconcile execution intents and canonical paper orders whose broker order is terminally rejected.
-- Review the SELECT output before running the UPDATE statements.
SELECT bo.broker_order_id, bo.aggregate_id, bo.status AS broker_status,
       ei.execution_intent_id, ei.state AS intent_state,
       co.state AS canonical_state, bo.last_error, bo.raw_json->'error' AS structured_error
FROM broker_orders bo
LEFT JOIN execution_intents ei ON bo.aggregate_id = 'M59-' || ei.execution_intent_id
LEFT JOIN canonical_orders co ON co.aggregate_id = bo.aggregate_id
WHERE UPPER(bo.status) IN ('REJECTED','INACTIVE')
  AND (ei.state IS DISTINCT FROM 'REJECTED' OR co.state IS DISTINCT FROM 'REJECTED');

BEGIN;
UPDATE execution_intents ei
SET state='REJECTED', version=version+1, updated_at=NOW()::text, terminal_at=NOW()::text,
    broker_json=COALESCE(broker_json,'{}'::jsonb) || jsonb_build_object('reconciled_from_broker_rejection',true)
FROM broker_orders bo
WHERE bo.aggregate_id='M59-' || ei.execution_intent_id
  AND UPPER(bo.status) IN ('REJECTED','INACTIVE')
  AND ei.state <> 'REJECTED';

UPDATE canonical_orders co
SET state='REJECTED', updated_at=NOW()::text, terminal_at=NOW()::text,
    metadata_json=COALESCE(metadata_json,'{}'::jsonb) || jsonb_build_object('reconciled_from_broker_rejection',true)
FROM broker_orders bo
WHERE co.aggregate_id=bo.aggregate_id
  AND UPPER(bo.status) IN ('REJECTED','INACTIVE')
  AND co.state <> 'REJECTED';
COMMIT;
