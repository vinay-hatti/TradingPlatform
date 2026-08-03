import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const page = fs.readFileSync(new URL('../src/OptionScannerWorkspace.tsx', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');

test('scanner uses persisted backend APIs without provider calls', () => {
  assert.match(page, /scannerApi\.runs/);
  assert.match(page, /scannerApi\.results/);
  assert.match(page, /scannerApi\.scan/);
  assert.doesNotMatch(page, /yfinance|polygon\.io|RESTClient/);
});
test('scanner provides command center, filters, grid, drawer and diagnostics', () => {
  for (const token of ['os-kpis','os-filters','os-grid-panel','os-intelligence','os-diagnostics']) assert.match(page, new RegExp(token));
});
test('presets and favorites are locally persisted', () => {
  assert.match(page, /trading-ai-option-scanner-presets/);
  assert.match(page, /trading-ai-option-scanner-favorites/);
  assert.match(page, /localStorage/);
});
test('quick actions connect to downstream workflow routes', () => {
  assert.match(page, /#\/opportunities/);
  assert.match(page, /#\/intelligence/);
  assert.match(page, /#\/trade-builder/);
});
test('responsive institutional layout is present', () => {
  assert.match(css, /grid-template-columns:236px/);
  assert.match(css, /@media\(max-width:1280px\)/);
  assert.match(css, /@media\(max-width:820px\)/);
});
