import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');const page=fs.readFileSync(path.join(root,'src','MarketOverviewRefinedPage.tsx'),'utf8');const css=fs.readFileSync(path.join(root,'src','market-overview-refined.css'),'utf8');
test('uses governed Market Overview endpoints',()=>{assert.match(page,/\/api\/v1\/market-overview\/latest/);assert.match(page,/\/api\/v1\/market-overview\/refresh/)});
test('surfaces institutional command-center domains',()=>{for(const text of ['Market health & breadth','Regime matrix','Institutional participation','Volatility environment','Liquidity & participation','Opportunity map','Risk dashboard','Dealer positioning & options structure'])assert.ok(page.includes(text),text)});
test('preserves dealer-model disclosure',()=>assert.match(page,/model-derived from open interest and Greeks/));
test('uses route-local responsive styling',()=>{assert.match(css,/\.mo-page/);assert.match(css,/@media\(max-width:760px\)/);assert.doesNotMatch(css,/(^|\})\s*(aside|\.content)\s*\{/)});
test('does not trigger ingestion or scanner execution',()=>{assert.doesNotMatch(page,/run_market_ingestion|option-scanner\/run|daily-scanner\/run/)})
