import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');const page=fs.readFileSync(path.join(root,'src','PerformanceLearningRefinedPage.tsx'),'utf8');const css=fs.readFileSync(path.join(root,'src','performance-learning-refined.css'),'utf8');
test('uses canonical performance learning APIs',()=>{assert.match(page,/performanceLearningApi\.report/);assert.match(page,/performanceLearningApi\.generate/);assert.match(page,/performanceLearningApi\.policies/)});
test('renders performance calibration and governance workspaces',()=>{assert.match(page,/Strategy attribution/);assert.match(page,/Probability calibration/);assert.match(page,/Learning-policy registry/)});
test('preserves human governed learning controls',()=>{assert.match(page,/No autonomous scanner or model changes/);assert.match(page,/±15% weight boundary/)});
test('uses route local responsive styling',()=>{assert.match(css,/\.pl-page/);assert.match(css,/@media\(max-width:720px\)/);assert.doesNotMatch(css,/(^|\n)aside\s*\{/)});
test('does not submit trades or broker orders',()=>{assert.doesNotMatch(page,/ibkr|submitOrder|broker.*submit/i)});
console.log('UI Milestone 9 Performance Learning assertions passed.');
