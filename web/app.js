'use strict';
const $=id=>document.getElementById(id);
const targets=[['harbor','v1'],['harbor','v2'],['cedar','v1']];
const labels={pass:'Safe to send',escalate:'Needs review',block:'Blocked',rewrite:'Fixed'};
const icons={pass:'✓',escalate:'?',block:'×',rewrite:'✦'};
const names={'harbor/v1':'Harbor · $20 limit','harbor/v2':'Harbor · $10 limit','cedar/v1':'Cedar · Approval'};
let config,report;
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
async function api(path,body,tenant='harbor'){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),path==='/api/shadow'?60000:8000);
  try{const r=await fetch(path,{method:body?'POST':'GET',signal:controller.signal,headers:{'Content-Type':'application/json','Authorization':`Bearer ${config.keys[tenant]}`},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();if(!r.ok)throw new Error(data.error||data.detail?.[0]?.msg||'Check your input.');return data;}
  finally{clearTimeout(timer);}
}
function card(result){
  const n=el('article',undefined,`decision ${result.verdict}`);
  const icon=el('div',icons[result.verdict],'result-icon');icon.setAttribute('aria-hidden','true');
  const content=el('div');const head=el('div',undefined,'decision-header');head.append(el('div',names[`${result.tenant}/${result.policy_version}`],'tenant-name'),el('span',labels[result.verdict],`badge ${result.verdict}`));content.append(head);
  let text='';
  if(result.verdict==='pass')text='Message allowed.';
  if(result.verdict==='escalate')text='Wait for a person to approve.';
  if(result.verdict==='block')text='Private information. Keep it unsent.';
  if(result.verdict==='rewrite')text=result.delivered_output||'Review the replacement.';
  content.append(el('div',text,'output'));
  const detail=el('details');detail.append(el('summary','Why?'),el('p',result.reason));if(result.proposed_output&&!result.delivered_output)detail.append(el('p',result.proposed_output));content.append(detail);n.append(icon,content);return n;
}
function celebrate(){
  if(reducedMotion.matches)return;
  const colors=['#b6da7a','#aa87f0','#f4ba74','#ee98b7'];const pieces=[];
  for(let i=0;i<30;i++){const p=el('i',undefined,'confetti-piece');p.style.setProperty('--x',`${Math.random()*100}%`);p.style.setProperty('--color',colors[i%colors.length]);p.style.setProperty('--delay',`${Math.random()*.3}s`);p.style.setProperty('--drift',`${(Math.random()-.5)*200}px`);p.style.setProperty('--rotation',`${Math.random()*700}deg`);pieces.push(p);}
  $('confetti').replaceChildren(...pieces);setTimeout(()=>$('confetti').replaceChildren(),1900);
}
async function replay({celebration=true}={}){
  if(!config){$('status').textContent='Connecting…';return;}
  const controls=[...document.querySelectorAll('.composer button,.composer input,.composer textarea,.presets button')];controls.forEach(n=>{n.disabled=true;});
  document.querySelector('.workspace').classList.add('is-checking');
  const dots=el('div',undefined,'loading-orbit');dots.setAttribute('aria-label','Checking');dots.append(el('i'),el('i'),el('i'));$('results').replaceChildren(dots);$('status').textContent='Checking…';
  try{
    const context={currency:'USD',supervisor_approved:$('approved').checked};if($('amount').value!=='')context.fee_amount=Number($('amount').value);
    const requests=Promise.all(targets.map(([tenant,version])=>api('/api/enforce',{message:$('message').value,version,context},tenant)));
    // Short presentation animation, never included in measured inference latency.
    const [results]=await Promise.all([requests,new Promise(resolve=>setTimeout(resolve,reducedMotion.matches?0:650))]);
    $('results').replaceChildren(...results.map(card));$('status').textContent='Checked ✓';
    if(celebration&&results.every(r=>r.verified&&['pass','rewrite'].includes(r.verdict)))celebrate();
    evidence().catch(()=>{});
  }catch(error){$('status').textContent=error.name==='AbortError'?'Connection timed out.':error.message;$('results').replaceChildren(el('p','Not checked. Keep it unsent.','empty'));}
  finally{document.querySelector('.workspace').classList.remove('is-checking');controls.forEach(n=>{n.disabled=false;});}
}
function metric(label,value){const n=el('div');n.append(el('small',label),el('strong',value));return n;}
const pct=value=>value===null?'—':`${Math.round(value*100)}%`;
async function evaluate(mode){
  if(!config)return;
  $('eval-btn').disabled=$('triage-btn').disabled=true;$('eval-note').textContent='Checking…';
  try{report=await api('/api/evaluate',{mode});$('metrics').replaceChildren(metric('CORRECT',`${report.correct}/${report.total}`),metric('CHANGED',pct(report.changed_pair_accuracy)),metric('NEW ERRORS',pct(report.invariant_pair_error_rate)),metric('TIME',`${report.wall_ms.toFixed(1)}ms`));
    $('eval-rows').replaceChildren(...report.rows.map(r=>{const row=el('tr');row.append(el('td',r.message),el('td',names[`${r.tenant}/${r.version}`]),el('td',labels[r.expected]),el('td',labels[r.predicted]||r.predicted,r.expected===r.predicted?'ok':'fail'));return row;}));
    $('eval-note').textContent=`${report.total} synthetic examples · ${report.cache_hits} saved results reused.`;$('download-btn').disabled=false;
    if(report.correct===report.total)celebrate();
  }catch(error){$('eval-note').textContent=error.message;}
  finally{$('eval-btn').disabled=$('triage-btn').disabled=false;}
}
async function evidence(){const {events}=await api('/api/evidence');$('events').replaceChildren(...events.slice(0,5).map(e=>{const n=el('article',undefined,'event');const left=el('div',e.policy_version==='v1'?'Harbor · $20':'Harbor · $10');left.append(el('small',new Date(e.created_at).toLocaleTimeString()));const center=el('code',e.evidence_id);n.append(left,center,el('span',labels[e.verdict],`badge ${e.verdict}`));const detail=el('details');detail.append(el('summary','Record'),el('pre',JSON.stringify(e,null,2)));n.append(detail);return n;}));}
const presets={refund:['I can refund your $15 transfer fee now.','15'],boundary:['I can refund your $10.01 transfer fee now.','10.01'],invariant:['I can refund your $5 transfer fee now.','5'],claim:['This fund offers guaranteed returns.',''],secret:['Our API key is sk-demo123456789.','']};
function choose(key){const [message,amount]=presets[key];$('message').value=message;$('amount').value=amount;$('approved').checked=false;document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('active',b.dataset.preset===key));replay();}
document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>choose(b.dataset.preset)));
$('surprise-btn').addEventListener('click',()=>{const keys=Object.keys(presets);choose(keys[Math.floor(Math.random()*keys.length)]);});
$('approved').addEventListener('change',()=>replay());
$('amount').addEventListener('change',()=>{if(/^I can refund your \$[\d.]+ transfer fee now\.$/.test($('message').value)&&$('amount').value!=='')$('message').value=`I can refund your $${$('amount').value} transfer fee now.`;document.querySelectorAll('[data-preset]').forEach(b=>b.classList.remove('active'));replay();});
$('message').addEventListener('input',()=>{document.querySelectorAll('[data-preset]').forEach(b=>b.classList.remove('active'));$('status').textContent='Edited · check again.';$('results').replaceChildren(el('p','Ready to check.','empty'));});
$('message').addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();replay();}});
$('replay-btn').addEventListener('click',()=>replay());$('eval-btn').addEventListener('click',()=>evaluate('full'));$('triage-btn').addEventListener('click',()=>evaluate('triage'));$('refresh-btn').addEventListener('click',()=>evidence().catch(()=>{}));
$('download-btn').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download=`switchboard-${report.mode}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function experiments(){
  $('models-btn').disabled=true;
  try{const data=await api('/api/experiments');
    $('model-results').replaceChildren(...data.experiments.map(r=>{
      const n=el('article',undefined,'model-card');n.append(el('h3',r.name),el('strong',`${r.correct}/${r.total} correct`),el('p',`${r.invalid_outputs} invalid · ${Math.round(r.p95_ms)} ms batch p95`,'fine-print'),el('span',r.gate.status==='shadow-ready'?'Shadow ready':'Release blocked',`badge ${r.gate.status==='shadow-ready'?'pass':'escalate'}`));
      if(r.holdout)n.append(el('p',`Unseen wording: ${r.holdout.correct}/${r.holdout.total}`,'fine-print'));
      const d=el('details');d.append(el('summary','Evidence'),el('p',r.model),el('code',r.revision),el('p',r.gate.failures.join(' · ')||'Synthetic gate passed. Independent review required.'),el('p',`Report SHA-256: ${r.report_sha256}`,'fine-print'));n.append(d);return n;
    }));if(!data.experiments.length)$('model-results').append(el('p','No completed model runs yet.','fine-print'));
  }catch(error){$('model-results').replaceChildren(el('p',error.message));}
  finally{$('models-btn').disabled=false;}
}
$('models-btn').addEventListener('click',experiments);
$('shadow-btn').addEventListener('click',async()=>{
  if(!config)return;$('shadow-btn').disabled=true;$('shadow-result').textContent='Comparing… first run loads the model.';
  try{const context={currency:'USD',supervisor_approved:$('approved').checked};if($('amount').value!=='')context.fee_amount=Number($('amount').value);
    const r=await api('/api/shadow',{message:$('message').value,version:'v2',context});
    const aiLabel={pass:'Allow',escalate:'Review',block:'Block',rewrite:'Rewrite',invalid:'Invalid answer'}[r.model_verdict]||r.model_verdict;
    $('shadow-result').textContent=r.model_verdict==='not-run'?'Private info blocked · AI skipped · Nothing sent':`AI: ${aiLabel} (unverified) · Rules: ${labels[r.rule_verdict]} · Nothing sent`;
  }catch(error){$('shadow-result').textContent=error.name==='AbortError'?'Model is still loading. Try again shortly.':error.message;}
  finally{$('shadow-btn').disabled=false;}
});
fetch('/api/demo-config').then(r=>{if(!r.ok)throw new Error('Connection unavailable.');return r.json();}).then(c=>{config=c;return replay({celebration:false});}).catch(error=>{$('status').textContent=error.message;});
