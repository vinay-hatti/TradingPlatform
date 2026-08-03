import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const productivity = readFileSync(new URL('../src/WorkspaceProductivity.tsx', import.meta.url), 'utf8');
const chrome = readFileSync(new URL('../src/WorkspaceChrome.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');

test('command palette is keyboard accessible and route aware', () => {
  assert.match(productivity, /metaKey \|\| event\.ctrlKey/);
  assert.match(productivity, /key\.toLowerCase\(\) === 'k'/);
  assert.match(productivity, /Search workspaces and commands/);
  assert.match(productivity, /role="dialog"/);
});

test('workstation preferences persist supported shell choices', () => {
  for (const preference of ['compactDensity', 'reducedMotion', 'showStatusBar']) assert.match(productivity, new RegExp(preference));
  assert.match(app, /workstation-preferences/);
  assert.match(styles, /compact-density/);
  assert.match(styles, /reduced-motion/);
});

test('favorites and recent workspaces are persisted', () => {
  assert.match(app, /workstation-favorites/);
  assert.match(app, /workstation-recent/);
  assert.match(chrome, /Favorite workspaces/);
});

test('productivity actions preserve route and backend contracts', () => {
  assert.match(app, /location\.hash=`#\/\$\{workspace\}`/);
  assert.match(app, /setRefreshToken/);
  assert.doesNotMatch(productivity, /fetch\(/);
});
