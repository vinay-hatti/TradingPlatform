import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
const root = new URL('../src/', import.meta.url).pathname;
function files(dir){return readdirSync(dir).flatMap(n=>{const p=join(dir,n);return statSync(p).isDirectory()?files(p):['.tsx','.ts','.jsx','.js'].includes(extname(p))?[p]:[]})}
test('Daily Scanner omits Market Ingestion UI',()=>{
 const source=files(root).map(p=>readFileSync(p,'utf8')).join('\n');
 assert.equal(source.includes('Market Ingestion'),false);
});
test('Daily Scanner omits governed ingestion pre-scan control',()=>{
 const source=files(root).map(p=>readFileSync(p,'utf8')).join('\n');
 assert.equal(source.includes('Run governed ingestion before scanning'),false);
});
