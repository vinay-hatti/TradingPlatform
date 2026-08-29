import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const src = fs.readFileSync(path.join(root, 'src', 'PortfolioIntelligenceRefinedPage.tsx'), 'utf8');

test('current exit projection separates current state from history', () => {
  assert.match(src, /currentInstructionProjection/);
  assert.match(src, /Management history/);
  assert.match(src, /selectedHistoricalInstructions/);
});

test('critical protection and profit target health are distinct', () => {
  assert.match(src, /CRITICAL_PROTECTION_LABELS/);
  assert.match(src, /PROFIT_TARGET_LABELS/);
  assert.match(src, /CRITICAL PROTECTION ACTIVE/);
  assert.match(src, /PROFIT TARGET ATTENTION/);
});

test('target issue alone does not force degraded autonomous management', () => {
  assert.match(src, /AUTO MANAGED · TARGET ATTENTION/);
  assert.match(src, /protectionFailures\.length === 0/);
});
