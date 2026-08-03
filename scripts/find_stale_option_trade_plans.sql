-- Review only: identifies trade plans and execution intents whose legs lack exact option identities.
SELECT trade_plan_id, symbol, state, version, legs_json
FROM trade_plans
WHERE state IN ('VALIDATED','APPROVED','PAPER_READY')
  AND EXISTS (SELECT 1 FROM jsonb_array_elements(legs_json::jsonb) leg WHERE COALESCE(NULLIF(BTRIM(leg->>'option_symbol'),''),'')='');

SELECT execution_intent_id, symbol, state, version, legs_json
FROM execution_intents
WHERE state NOT IN ('FILLED','CANCELLED','REJECTED','EXPIRED')
  AND EXISTS (SELECT 1 FROM jsonb_array_elements(legs_json::jsonb) leg WHERE COALESCE(NULLIF(BTRIM(leg->>'option_symbol'),''),'')='');
