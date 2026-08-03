import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));const root=path.resolve(here,'../src');const page=fs.readFileSync(path.join(root,'OpportunityWorkspaceM4.tsx'),'utf8');const css=fs.readFileSync(path.join(root,'opportunity-workspace-m4.css'),'utf8');
test('uses canonical opportunity APIs',()=>{assert.match(page,/opportunityApi\.list/);assert.match(page,/opportunityApi\.events/);assert.match(page,/opportunityApi\.transition/)});
test('preserves optimistic lifecycle versioning',()=>assert.match(page,/selected\.version/));
test('provides review, comparison and downstream handoffs',()=>{assert.match(page,/Review queue/);assert.match(page,/toggleCompare/);assert.match(page,/institutional-intelligence/);assert.match(page,/trade-builder/)});
test('provides audit and analyst note surfaces',()=>{assert.match(page,/Audit timeline/);assert.match(page,/Analyst notes/);assert.match(page,/localStorage/)});
test('supports responsive three-pane workspace',()=>{assert.match(css,/grid-template-columns:300px/);assert.match(css,/@media\(max-width:800px\)/)});
