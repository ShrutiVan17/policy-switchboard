'use strict';
const $ = id => document.getElementById(id);
let config, report;
const targets = [['harbor','v1'],['harbor','v2'],['cedar','v1']];
const labels={pass:'Safe to send',escalate:'Needs review',block:'Blocked',rewrite:'Fixed'};
const policyNames={'harbor/v1':'Harbor · Previous rules','harbor/v2':'Harbor · New rules','cedar/v1':'Cedar · Different company'};
function el(tag, text, cls) { const n = document.createElement(tag); if(text !== undefined) n.textContent=text; if(cls) n.className=cls; return n; }
async function api(path, body, tenant='harbor') {
  const response = await fetch(path, {method:body ? 'POST':'GET', headers:{'Content-Type':'application/json','Authorization':`Bearer ${config.keys[tenant]}`}, ...(body ? {body:JSON.stringify(body)}:{})});
  const result = await response.json(); if(!response.ok) throw new Error(result.error || result.detail?.[0]?.msg || 'Please check the message and refund details.'); return result;
}
function card(result) {
  const item=el('article',undefined,'decision'); const head=el('div',undefined,'decision-header');
  const name=el('div',policyNames[`${result.tenant}/${result.policy_version}`],'tenant-name');
  head.append(name,el('span',labels[result.verdict],`badge ${result.verdict}`));
  const limit=result.tenant==='cedar'?'Every refund needs approval.':`Refunds over $${result.policy_version==='v1'?20:10} need approval.`;
  let reason=result.reason;
  if(reason==='Message matches supported policy checks.') reason='This message is allowed by the demo rules.';
  if(reason==='Supervisor approval is required under this policy version.') reason='Ask a supervisor before promising this refund.';
  item.append(head,el('p',limit,'policy-summary'),el('p',reason));
  item.append(el('div',result.delivered_output ? `Message allowed: “${result.delivered_output}”` : result.proposed_output ? `Keep the original unsent. Suggested message for review: “${result.proposed_output}”`:'Keep this message unsent. No replacement is approved.','output'));
  return item;
}
async function replay() {
  const controls=[...document.querySelectorAll('.composer button, .composer input, .composer textarea')];
  controls.forEach(c=>{c.disabled=true;});
  $('results').replaceChildren(el('p','Checking the company rules…','empty'));
  $('status').textContent='Checking your message…';
  try {
    const context={currency:'USD',supervisor_approved:$('approved').checked};
    if($('amount').value!=='') context.fee_amount=Number($('amount').value);
    const results=await Promise.all(targets.map(([tenant,version])=>api('/api/enforce',{message:$('message').value,version,context},tenant)));
    $('results').replaceChildren(...results.map(card));
    $('status').textContent=`Checked all ${results.length} rule sets. Results are saved.`;
    await evidence();
  } catch(err) { $('status').textContent=`Replay failed: ${err.message}. Output withheld.`; $('results').replaceChildren(el('p','Replay failed. Outputs withheld.','empty')); }
  finally { controls.forEach(c=>{c.disabled=false;}); }
}
function metric(label,value,note){const n=el('div');n.append(el('small',label),el('strong',value),el('span',note));return n;}
const pct=x=>x===null?'N/A':`${(x*100).toFixed(1)}%`;
async function evaluate(mode) {
  $('eval-btn').disabled=$('triage-btn').disabled=true;
  $('eval-note').textContent='Checking the example messages…';
  try {
    report=await api('/api/evaluate',{mode});
    $('metrics').replaceChildren(metric('CORRECT ANSWERS',`${report.correct}/${report.total}`,'Fictional examples checked'),metric('RULE CHANGES HANDLED',pct(report.changed_pair_accuracy),`${report.changed_pairs} answers that should change`),metric('NEW MISTAKES',pct(report.invariant_pair_error_rate),`${report.invariant_pairs} answers that should stay correct`),metric('TIME TAKEN',`${report.wall_ms.toFixed(1)} ms`,`${report.cache_hits} saved results reused`));
    $('eval-rows').replaceChildren(...report.rows.map(r=>{const row=el('tr'); const ok=r.expected===r.predicted; row.append(el('td',r.message),el('td',policyNames[`${r.tenant}/${r.version}`]),el('td',labels[r.expected]),el('td',labels[r.predicted]||r.predicted),el('td',ok?'✓ Correct':'✕ Incorrect',ok?'ok':'fail'));return row;}));
    $('eval-note').textContent=`${mode==='triage'?'Changed-rule check finished. Run all 72 examples before considering a release.':'All examples checked.'} This is a small test of built-in rules, not proof of trained AI accuracy or real-world compliance. Cost savings have not been measured.`;
    $('download-btn').disabled=false;
  } catch(err) {$('eval-note').textContent=`Evaluation failed: ${err.message}`;}
  finally {$('eval-btn').disabled=$('triage-btn').disabled=false;}
}
async function evidence(){
  const {events}=await api('/api/evidence');
  $('events').replaceChildren(...events.slice(0,8).map(e=>{const n=el('article',undefined,'event');const left=el('div',`Harbor / ${e.policy_version}`);left.append(el('small',new Date(e.created_at).toLocaleTimeString()));const center=el('div');center.append(el('code',e.evidence_id),el('small',`Policy ${e.policy_hash.slice(0,12)} · ${e.engine_revision}`));n.append(left,center,el('span',e.verdict.toUpperCase(),`badge ${e.verdict}`));const detail=el('details');detail.append(el('summary','Inspect decision evidence'),el('pre',JSON.stringify(e,null,2)));n.append(detail);return n;}));
  if(!events.length) $('events').append(el('p','No Harbor evidence records yet.','empty'));
}
const presets={boundary:['I can refund your $10.01 transfer fee now.','10.01'],invariant:['I can refund your $5 transfer fee now.','5'],claim:['This fund offers guaranteed returns.',''],secret:['Our API key is sk-demo123456789.','']};
document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{const [message,amount]=presets[b.dataset.preset];$('message').value=message;$('amount').value=amount;$('approved').checked=false;replay();}));
$('replay-btn').addEventListener('click',replay);$('eval-btn').addEventListener('click',()=>evaluate('full'));$('triage-btn').addEventListener('click',()=>evaluate('triage'));$('refresh-btn').addEventListener('click',()=>evidence().catch(e=>{$('status').textContent=e.message;}));
$('download-btn').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download=`policy-switchboard-${report.mode}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
fetch('/api/demo-config').then(r=>{if(!r.ok)throw new Error('Configuration unavailable');return r.json();}).then(c=>{config=c;return replay();}).catch(e=>{$('status').textContent=`Service unavailable: ${e.message}`;});
fetch('/api/health').then(r=>r.json()).then(h=>{$('framework-note').textContent=`Active API: ${h.api_framework||'Python standard-library fallback'}. Message checking uses built-in rules. No trained model is active.`;}).catch(()=>{$('framework-note').textContent='API status unavailable.';});
