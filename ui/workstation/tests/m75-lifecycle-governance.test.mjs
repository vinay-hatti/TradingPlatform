import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(new URL('../src/PortfolioIntelligenceRefinedPage.tsx', import.meta.url),'utf8');

test('terminal positions project as lifecycle finalized without active exits',()=>{
  assert.match(src,/LIFECYCLE FINALIZED/);
  assert.match(src,/activeExitCount: 0/);
});

test('expanded terminal state set is non-operational',()=>{
  for(const state of ['EXPIRED','ASSIGNED','STOPPED','TERMINAL','ARCHIVED']) assert.ok(src.includes(state));
});
