import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const chrome = readFileSync(new URL('../src/WorkspaceChrome.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');

test('application shell uses shared workstation chrome', () => {
  assert.match(app, /WorkspaceSidebar/);
  assert.match(app, /GlobalIntelligenceHeader/);
  assert.match(app, /WorkspaceStatusBar/);
});

test('navigation is organized by institutional workflow', () => {
  for (const label of ['Market intelligence', 'Scanning', 'Opportunities', 'Portfolio', 'Operations']) assert.match(chrome, new RegExp(label));
});

test('design tokens define semantic color and layout primitives', () => {
  for (const token of ['--ui-bg-canvas', '--ui-text-primary', '--ui-positive', '--ui-warning', '--ui-negative', '--ui-sidebar-width']) assert.match(styles, new RegExp(token));
});

test('global context ribbon exposes governed operational context', () => {
  assert.match(chrome, /Published context/);
  assert.match(chrome, /Paper governed/);
  assert.match(chrome, /platformApi\.overview/);
  assert.match(chrome, /platformApi\.readiness/);
});
