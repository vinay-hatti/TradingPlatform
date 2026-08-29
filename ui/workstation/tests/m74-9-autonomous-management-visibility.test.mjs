import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const src=fs.readFileSync(path.join(here,'../src/PortfolioIntelligenceRefinedPage.tsx'),'utf8');
const css=fs.readFileSync(path.join(here,'../src/portfolio-intelligence-refined.css'),'utf8');
test('M74.9 exposes explicit autonomous and manual management states',()=>{
  assert.match(src,/AUTO MANAGED/);
  assert.match(src,/MANUAL MANAGEMENT REQUIRED/);
  assert.match(src,/AUTO MANAGEMENT DEGRADED/);
  assert.match(src,/You must manually manage this position through closure/);
});
test('M74.9 derives AUTO from runtime governance evidence',()=>{
  assert.match(src,/automationMode === 'FULLY_AUTOMATIC'/);
  assert.match(src,/managerActive/);
  assert.match(src,/activeExitCount > 0/);
  assert.match(src,/canonicalLineage/);
  assert.match(src,/dynamicPositionManagementApi\.instructions\(\)/);
});
test('M74.9 provides filterable, non-color-only management visibility',()=>{
  assert.match(src,/Management status/);
  assert.match(src,/Auto managed/);
  assert.match(src,/Manual required/);
  assert.match(src,/Automation degraded/);
  assert.match(css,/\.pi-management-badge\.auto/);
  assert.match(css,/\.pi-management-badge\.manual/);
  assert.match(css,/\.pi-management-badge\.degraded/);
});
