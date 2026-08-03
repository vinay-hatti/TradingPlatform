import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
const root=process.env.TARGET_ROOT||path.resolve(import.meta.dirname,'..');
const page=fs.readFileSync(path.join(root,'src/ExecutionWorkspacePage.tsx'),'utf8');const api=fs.readFileSync(path.join(root,'src/api.ts'),'utf8');const app=fs.readFileSync(path.join(root,'src/App.tsx'),'utf8');const trade=fs.readFileSync(path.join(root,'src/AdvancedTradeBuilderPage.tsx'),'utf8');const css=fs.readFileSync(path.join(root,'src/execution-workspace.css'),'utf8');
test('uses canonical execution workspace APIs',()=>{for(const s of ['/api/v1/execution-workspace','executionWorkspaceApi','routingStatus','synchronize'])assert.ok(api.includes(s))});
test('requires explicit paper confirmation and preserves governance',()=>{assert.ok(page.includes('SUBMIT PAPER INTENT'));assert.ok(page.includes('Submit to IBKR Paper'));assert.ok(page.includes('Live trading'));assert.ok(page.includes('Disabled'))});
test('connects trade builder paper-ready flow to OMS',()=>{assert.ok(trade.includes('executionWorkspaceApi.create'));assert.ok(trade.includes("#/execution-workspace"));assert.ok(trade.includes('Open execution workspace'))});
test('registers route and navigation',()=>{assert.ok(app.includes("'execution-workspace': ExecutionWorkspacePage"))});
test('uses route-local responsive styling',()=>{assert.ok(css.includes('.execution-workspace'));assert.ok(css.includes('@media'));assert.ok(!css.includes('aside{'));assert.ok(!css.includes('.content{'))});
