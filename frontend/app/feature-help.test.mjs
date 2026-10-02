import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const compiled=ts.transpileModule(readFileSync(new URL('./feature-help.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const module={exports:{}};
new Function('require','module','exports',compiled)(createRequire(import.meta.url),module,module.exports);
const {FeatureHelp,describeFeature}=module.exports;
const render=(weight,extra={})=>renderToStaticMarkup(React.createElement(FeatureHelp,{term:'paragraph_word_fraction',rawFeature:'paragraph_word_fraction',label:'Paragraph word fraction',weight,...extra}));
test('weight sign is explicit even for tiny, zero and unavailable coefficients',()=>{
 assert.match(render(.0000001),/Weight \+/);assert.match(render(.0000001),/score up/);
 assert.match(render(-.2),/Weight −/);assert.match(render(-.2),/score down/);
 assert.match(render(0),/Weight 0/);assert.match(render(undefined),/Weight unavailable/);
});
test('names expand through a native keyboard-accessible disclosure',()=>{
 const html=render(.2);assert.match(html,/<details[^>]*><summary>/);
 assert.match(html,/total word occurrences/);assert.match(html,/weight × change in standardized feature value/);
});
test('missingness, unknown features and untrusted labels are handled explicitly',()=>{
 assert.match(describeFeature('page_similarity',true),/weight applies to missingness/);
 assert.match(describeFeature('future_feature'),/No description is available/);
 assert.match(render(-.2,{label:'<script>bad</script>'}),/&lt;script&gt;/);
});
