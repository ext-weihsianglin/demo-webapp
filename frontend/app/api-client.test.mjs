import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source = readFileSync(new URL('./api-client.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020 } }).outputText;
const { readApiResponse } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('proxy failures produce a useful error instead of a JSON parser exception', async () => {
  await assert.rejects(readApiResponse(new Response('Internal Server Error', { status: 500 })),
                       /API temporarily unavailable.*HTTP 500/);
});
test('valid API success is preserved', async () => {
  assert.deepEqual(await readApiResponse(new Response('{"status":"running"}')), { status:'running' });
});
test('structured backend error retains status and summary', async () => {
  await assert.rejects(readApiResponse(new Response('{"detail":{"status":"fidelity_rejected","summary":"No draft applied."}}', {status:422})),
                       /fidelity_rejected: No draft applied\./);
});
