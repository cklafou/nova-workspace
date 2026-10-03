/* Runtime controls use body state. Every action is acknowledged by the server. */
window.mountNovaControl = function(root) {
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  root.classList.add('nc-control');
  const heading=el('div',null,'ncr-heading'), state=el('strong','Connecting…'), detail=el('p','Waiting for Nova’s runtime.');
  heading.append(state,detail);root.append(heading);
  const controls=el('div',null,'ncr-actions'), facts=el('div',null,'ncr-facts'), tasks=el('div',null,'ncr-tasks');
  root.append(controls,facts,el('h3','Work and verification'),tasks);
  const evidence=el('div',null,'ncr-evidence');root.append(el('h3','Recent outcomes'),evidence);
  const notice=el('p','', 'ncr-notice');root.append(notice);
  async function post(url,body={}) {
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'Request failed');return d;
  }
  function button(text, action, parent=controls) {
    const b=el('button',text,'nc-action');b.type='button';parent.append(b);
    b.onclick=async()=>{b.disabled=true;notice.textContent='';try{await action();await refresh();}catch(e){notice.textContent=e.message;}finally{b.disabled=false;}};
    return b;
  }
  button('Services and restart',()=>window.ensureWidget('services'));
  button('Stop current work',async()=>{const d=await post('/stop');notice.textContent=d.stopped?'Work stopped. Progress is retained.':'Stop requested; some work is still stopping.';});
  button('Pause autonomy',()=>post('/api/runtime/pause'));
  button('Resume autonomy',()=>post('/api/runtime/resume'));
  button('Take VM control',()=>post('/api/computer/handoff',{owner:'human'}));
  button('Return VM control',()=>post('/api/computer/handoff',{owner:'nova'}));
  button('Retry memory writes',()=>post('/api/runtime/retry-memory'));
  button('Recover memory from records',async()=>{const d=await post('/api/runtime/recover-memory');notice.textContent=d.records_considered+' records checked for indexing. Original records are preserved.';});
  let busy=false;
  async function refresh() {
    if(busy)return;busy=true;
    try{
      const response=await fetch('/api/runtime/state');if(!response.ok)throw Error('Runtime unavailable');const d=await response.json();
      const expanded=new Set([...root.querySelectorAll('details[open][data-key]')].map(n=>n.dataset.key));
      const active=d.operations||[];
      state.textContent=active.length?'Working · '+active.map(x=>x.label).join(', '):d.paused?'Stopped':d.autonomy_enabled?'Autonomy ready':'Autonomy paused';
      detail.textContent=(d.focus?'Focus '+d.focus:'No active focus')+' · '+d.budget_seconds+' second wake budget';
      facts.replaceChildren();
      const counts=c=>{const labels={pending:'waiting',leased:'in progress',failed:'need attention',done:'completed'};return Object.entries(c||{}).filter(([,v])=>v).map(([k,v])=>v+' '+(labels[k]||k)).join(' · ')||'Nothing waiting';};
      for(const [label,value] of [
        ['VM control',d.computer?.owner==='human'?'You':'Nova'],
        ['Events',counts(d.events?.counts)],
        ['Memory',d.memory?.ready?(d.memory.text_count+' text · '+d.memory.visual_count+' visual'):'Unavailable'],
        ['Memory writes',counts(d.memory_queue?.counts)]]) {
        const card=el('div',null,'ncr-fact');card.append(el('span',label),el('strong',value));facts.append(card);
      }
      const errors=[d.memory?.last_error,...(d.memory_queue?.errors||[]).map(x=>x.error),...(d.events?.errors||[]).map(x=>x.error),...active.flatMap(x=>x.cleanup_errors||[])].filter(Boolean);
      if(errors.length)facts.append(el('p',errors.join(' · '),'ncr-error'));
      tasks.replaceChildren();
      const open=(d.tasks||[]).filter(t=>!['done','abandoned'].includes(t.status));
      if(!open.length)tasks.append(el('p','No open tasks.'));
      for(const t of open){
        const card=el('article',null,'ncr-task');card.append(el('strong',t.id+' · '+t.title));
        card.append(el('p',t.waiting_on||'Last scheduling decision: '+(t.scheduling?.state||t.status)+' — '+(t.scheduling?.reason||'Awaiting scheduling')));
        if(t.verification)card.append(el('p','Verification: '+t.verification.state));
        if(t.verification?.checks?.length){
          const checks=el('details');checks.dataset.key='check:'+t.id;checks.append(el('summary','Verification details'),el('pre',JSON.stringify(t.verification.checks,null,2)));card.append(checks);
        }
        const row=el('div',null,'ncr-actions');card.append(row);
        button('Verify',()=>post('/api/queue/update',{id:t.id,action:'verify'}),row);
        if(t.status==='waiting')button('Resume task',()=>post('/api/queue/update',{id:t.id,action:'resume'}),row);
        button('Confirm completed',()=>post('/api/queue/complete',{id:t.id}),row);
        button('Acceptance checks',()=>editChecks(t),row);
        tasks.append(card);
      }
      evidence.replaceChildren();
      for(const t of (d.tasks||[]).filter(t=>t.status==='done').sort((a,b)=>(b.updated||'').localeCompare(a.updated||'')).slice(0,4)){
        const item=el('details',null,'ncr-task');item.dataset.key='task:'+t.id;item.append(el('summary',t.id+' · '+t.title+' · '+(t.verification?.state||'historical completion')));
        item.append(el('p',t.result||'No result recorded.'));if(t.verification)item.append(el('pre',JSON.stringify(t.verification,null,2)));evidence.append(item);
      }
      for(const receipt of (d.receipts||[]).slice(-8).reverse()){
        const outcome=receipt.outcome, item=el('details',null,'ncr-task');
        item.dataset.key='receipt:'+(outcome?.operation_id||receipt.ts+receipt.tool);
        item.append(el('summary',receipt.tool+' · '+(outcome?.status||'unknown (legacy receipt)')));
        item.append(el('pre',outcome?(outcome.stdout||outcome.stderr||receipt.result_head||'No text output'):receipt.result_head||'No structured outcome'));evidence.append(item);
      }
      root.querySelectorAll('details[data-key]').forEach(n=>{n.open=expanded.has(n.dataset.key);});
    }catch(e){state.textContent='Disconnected';detail.textContent=e.message;}finally{busy=false;}
  }
  function editChecks(task){
    const dialog=el('dialog',null,'ncr-dialog');dialog.append(el('h2','Acceptance checks · '+task.id),el('p','Commands run with an argument list and a working directory. File checks can require content or a matching hash.'));
    const input=el('textarea');input.value=JSON.stringify(task.acceptance||[],null,2);input.setAttribute('aria-label','Acceptance checks JSON');dialog.append(input);
    const row=el('div',null,'ncr-actions');dialog.append(row);
    const error=el('p','', 'ncr-error');error.setAttribute('role','alert');dialog.append(error);
    button('Save',async()=>{try{await post('/api/queue/update',{id:task.id,acceptance:JSON.parse(input.value)});dialog.close();}catch(e){error.textContent=e.message;}},row);
    button('Close',()=>dialog.close(),row);
    dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  }
  refresh();const timer=setInterval(()=>{if(!document.hidden&&root.getClientRects().length)refresh();},4000);
  window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
};
