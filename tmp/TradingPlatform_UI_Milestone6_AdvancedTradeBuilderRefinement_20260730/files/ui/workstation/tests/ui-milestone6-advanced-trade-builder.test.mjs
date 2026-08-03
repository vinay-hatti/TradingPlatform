import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const page=fs.readFileSync(path.join(root,'src','AdvancedTradeBuilderRefinedPage.tsx'),'utf8');
const css=fs.readFileSync(path.join(root,'src','advanced-trade-builder-refined.css'),'utf8');
test('uses canonical opportunity and trade builder APIs',()=>{assert.match(page,/opportunityApi\.list/);assert.match(page,/tradeBuilderApi\.build/);assert.match(page,/tradeBuilderApi\.transition/)});
test('preserves optimistic workflow governance',()=>{assert.match(page,/expected_opportunity_version/);assert.match(page,/plan\.version/);assert.match(page,/PAPER_READY/)});
test('provides payoff risk greeks and sizing views',()=>{assert.match(page,/PayoffPreview/);assert.match(page,/Net Greeks/);assert.match(page,/Use risk budget/);assert.match(page,/Reward \/ risk/)});
test('does not submit orders directly',()=>{assert.doesNotMatch(page,/submitOrder|placeOrder|brokerApi/);assert.match(page,/No direct broker submission/)});
test('supports responsive three pane layout',()=>{assert.match(css,/grid-template-columns:minmax\(280px,340px\)/);assert.match(css,/@media\(max-width:900px\)/)});
