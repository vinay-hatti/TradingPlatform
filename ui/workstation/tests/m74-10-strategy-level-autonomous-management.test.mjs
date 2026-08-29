import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const src=fs.readFileSync(new URL('../src/PortfolioIntelligenceRefinedPage.tsx',import.meta.url),'utf8');
test('superseded records are non-operational',()=>assert.match(src,/NON_OPERATIONAL_POSITION_STATES.*SUPERSEDED/));
test('multi-leg lifecycle is visible',()=>{assert.match(src,/Strategy Lifecycle/);assert.match(src,/Short-leg monitoring/);assert.match(src,/ATOMIC BAG MANAGED/);});
test('short-leg policy is explicit',()=>assert.match(src,/closes the full strategy as one BAG before assignment-risk\/expiry governance is breached/));
