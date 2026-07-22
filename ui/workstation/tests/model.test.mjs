import test from 'node:test';import assert from 'node:assert/strict';
const asArray=v=>Array.isArray(v)?v:Array.isArray(v?.items)?v.items:Array.isArray(v?.positions)?v.positions:Array.isArray(v?.orders)?v.orders:Array.isArray(v?.assessments)?v.assessments:Array.isArray(v?.instructions)?v.instructions:[];
test('normalizes supported artifact collections',()=>{assert.equal(asArray({positions:[1,2]}).length,2);assert.equal(asArray({orders:[1]}).length,1);assert.deepEqual(asArray({}),[])});
test('does not mutate artifacts',()=>{const v={items:[1]};asArray(v).push(2);assert.equal(v.items.length,2)});
