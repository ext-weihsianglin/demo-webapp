import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const source = readFileSync(new URL('./fidelity-assessment.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}}).outputText;
const module = {exports:{}};
new Function('require', 'module', 'exports', compiled)(createRequire(import.meta.url), module, module.exports);
const { FidelityAssessment } = module.exports;

test('rejected assessment shows flagged block and reason as escaped text', () => {
  const html = renderToStaticMarkup(React.createElement(FidelityAssessment, {assessment:{status:'rejected', reason:'source_relative_check', findings:[{block_id:'b000087',verdict:'unsupported',category:'Language change',reason:'<script>unsupported</script>',source_ids:[]}]}}));
  assert.match(html, /Fidelity concerns/);
  assert.match(html, /b000087/);
  assert.match(html, /draft is retained/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
test('unavailable assessment is explicit and does not imply a pass', () => {
  const html = renderToStaticMarkup(React.createElement(FidelityAssessment, {assessment:{status:'unavailable',reason:'judge_provider_error',findings:[]}}));
  assert.match(html, /assessment incomplete/);
  assert.match(html, /judge_provider_error/);
  assert.doesNotMatch(html, /No fidelity issues flagged/);
});
