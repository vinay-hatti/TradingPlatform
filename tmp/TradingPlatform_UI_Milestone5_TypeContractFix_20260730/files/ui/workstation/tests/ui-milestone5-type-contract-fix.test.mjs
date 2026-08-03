import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const source=fs.readFileSync(path.join(root,'src','InstitutionalIntelligenceRefinedPage.tsx'),'utf8');
test('institutional intelligence reads score from canonical opportunity payload',()=>{
  assert.match(source,/source_payload/);
  assert.match(source,/opportunityScore\(item\)/);
  assert.doesNotMatch(source,/item\.ai_score/);
});
