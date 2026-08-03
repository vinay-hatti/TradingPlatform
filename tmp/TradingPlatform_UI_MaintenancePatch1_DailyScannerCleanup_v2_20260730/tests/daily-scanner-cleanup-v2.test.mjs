import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.env.TARGET_ROOT || process.cwd();
const file = path.join(root, 'src', 'pages.tsx');
const source = fs.readFileSync(file, 'utf8');

test('Daily Scanner no longer renders Market ingestion panel', () => {
  assert.equal(source.includes('<Card title="Market ingestion">'), false);
  assert.equal(source.includes('Run market ingestion</button>'), false);
});

test('Scan Controls no longer renders governed-ingestion checkbox', () => {
  assert.equal(source.includes('Run governed ingestion before scanning'), false);
});

test('Daily Scanner scan action remains wired', () => {
  assert.match(source, /<Card title="Scan controls">/);
  assert.match(source, /onClick=\{scan\}>\{config\.actionLabel\}/);
});

test('Option Scanner persisted-snapshot policy remains intact', () => {
  assert.match(source, /Published persisted snapshot/);
  assert.match(source, /refresh_mode=cache_only/);
  assert.match(source, /auto_refresh=false/);
});

test('Scanner backend functions remain present', () => {
  assert.match(source, /scannerApi\.scan/);
  assert.match(source, /scannerApi\.refresh/);
});
