import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(name){
 const code=ts.transpileModule(readFileSync(new URL(name,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const module={exports:{}};
 new Function('require','module','exports',code)(id=>id==='./api-client'?load('./api-client.ts'):require(id),module,module.exports);
 return module.exports;
}
const {DraftReview}=load('./draft-review.tsx');
const {PromptMessagesView}=load('./prompt-viewer.tsx');
test('invalid proposals remain visible and escaped outside the page preview',()=>{
 const html=renderToStaticMarkup(React.createElement(DraftReview,{draft:{validation_warnings:[{code:'edit_not_applied',message:'Protected block',block_id:'b1'}],unapplied_edits:[{block_id:'b1',before:'Original',proposal:{after:'<script>bad()</script>'},reason:'Protected block'}],raw_model_output:'<script>bad()</script>'}}));
 assert.match(html,/Not applied to preview/);assert.match(html,/Original model response/);
 assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
test('prompt viewer shows exact sent system and user text as escaped data',()=>{
 const html=renderToStaticMarkup(React.createElement(PromptMessagesView,{messages:{model:'gpt-5-mini',prompt_id:'selected-prompt',kind:'sent',system:'Preserve source.',user:'<script>source()</script>'}}));
 assert.match(html,/Exact system instructions/);assert.match(html,/Preserve source\./);
 assert.match(html,/User prompt/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
