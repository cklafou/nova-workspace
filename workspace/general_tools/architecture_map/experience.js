// Included inside viewer.js's closure. Uses the same snapshot, evidence and selection state.
const historyState={mode:'milestones',part:'',month:'',query:'',order:'oldest',noise:false,limit:40};
let learner={bookmarks:[],checkpoint:null};
try{learner={...learner,...JSON.parse(localStorage.getItem('nova-atlas-learning')||'{}')};}catch(_){}
if(!Array.isArray(learner.bookmarks))learner.bookmarks=[];
function persistLearner(){try{localStorage.setItem('nova-atlas-learning',JSON.stringify(learner));}catch(_){toast('Browser storage is unavailable');}}
function groupForFile(file){if(file.startsWith('nova_body/'))return file.split('/')[1];return /nova_start|NovaLauncher|NovaStart|StopNova|start_llama/.test(file)?'boundary_boot':'boundary_chat';}
function groupName(id){return groups.get(id)?.label||id.replace('nova_','').replaceAll('_',' ')+' (historical)';}
function learnDialog(title,html,kind='LEARN & EXPLORE'){$('learning-dialog-title').textContent=title;$('learning-dialog-kind').textContent=kind;$('learning-dialog-content').innerHTML=html;if(!$('learning-dialog').open)$('learning-dialog').showModal();}
function closeLearn(){if($('learning-dialog').open)$('learning-dialog').close();}
function listText(items){return '<ul>'+items.map(t=>`<li>${escape(t)}</li>`).join('')+'</ul>';}
function partButton(id,text){return `<button class="inline-part" data-open-part="${escape(id)}">${escape(text||label(id))} ↗</button>`;}
function openPart(id){closeLearn();if(state.level===4)changeLevel(3);const n=nodeRecord(id);if(!n){toast('This part is historical; it is absent from the current map');return;}if(n.group)focusGroup(n.group,id);else if(groups.has(id))focusGroup(id,id);else selectNode(id);$('workspace').scrollIntoView({behavior:'smooth',block:'start'});save();}
function directRelationships(n){
  const own=groups.has(n.id)?new Set(data.nodes.filter(x=>x.group===n.id).map(x=>x.id)):new Set([n.id]);
  const edges=[...data.imports,...data.calls];
  return {own,incoming:[...new Set(edges.filter(e=>own.has(e.to)&&!own.has(e.from)).map(e=>e.from))],outgoing:[...new Set(edges.filter(e=>own.has(e.from)&&!own.has(e.to)).map(e=>e.to))]};
}
function componentLearning(n){
  const guide=data.learning?.groups?.[n.group||n.id],rel=directRelationships(n);
  const bookmarked=learner.bookmarks.includes(n.id);
  let out=`<div class="learning-actions"><button class="quiet-button" data-bookmark="${escape(n.id)}">${bookmarked?'Saved ✓':'Save part'}</button><button class="quiet-button" data-part-history="${escape(n.id)}">Its history</button><button class="quiet-button" data-impact="${escape(n.id)}">Change impact</button><button class="quiet-button" data-work-brief="${escape(n.id)}">Copy work brief</button><button class="quiet-button" data-copy-link="${escape(n.id)}">Copy link</button></div>`;
  if(guide){
    out+=`<details class="component-guide" open><summary>${n.group?'How this fits its faculty':'Why this part exists'}</summary><p>${escape(guide.why)}</p><p class="analogy">${escape(guide.analogy)}</p><div class="io-columns"><div><h3>Receives</h3>${listText(guide.inputs)}</div><div><h3>Produces</h3>${listText(guide.outputs)}</div></div>${n.group?'<p class="coverage-note">These inputs and outputs describe the faculty. This file contributes the responsibility described above.</p>':''}<h3>What trouble can look like</h3><p>${escape(guide.failure)}</p><h3>Before extending it</h3>${listText(guide.change)}<p>Suggested entry point: ${partButton(guide.start,guide.start.split('/').pop())}</p></details>`;
  }
  if(n.group||groups.has(n.id))out+=`<details class="component-guide"><summary>Callers & dependencies</summary><p>Imports and resolved calls in this scope. Callbacks and external operations may add other paths.</p><h3>Who refers to this (${rel.incoming.length})</h3>${rel.incoming.length?rel.incoming.map(id=>partButton(id)).join(''):'<p>No external static caller found. Check entry points and dynamic loading before drawing a conclusion.</p>'}<h3>What it refers to (${rel.outgoing.length})</h3>${rel.outgoing.map(id=>partButton(id)).join('')||'<p>No external static dependency found.</p>'}</details>`;
  return out;
}
function renderExperience(){
  const guideOpen=$('understand-guide').querySelector('details')?.open;
  $('understand-guide').hidden=state.level!==1;
  $('understand-guide').innerHTML=`<details ${guideOpen?'open':''}><summary>Four ideas that make the whole map easier to read</summary><div class="principle-grid">${(data.learning?.principles||[]).map(p=>`<article><h3>${escape(p.title)}</h3><p>${escape(p.text)}</p></article>`).join('')}</div></details>`;
  $('learning-bar-text').textContent=state.level===4?'A plan, a commit and a successful runtime check are different kinds of evidence.':state.level===1?'Start with a familiar flow. Then inspect the handoffs.':'Select a part for its purpose, inputs, outputs, callers and change considerations.';
  renderJourneyPlayer();
  $('live-learning').hidden=state.level!==3;
  if(state.level===3)renderLiveLearning();
  if(state.level===4)renderTimeline();
}
function renderJourneyPlayer(){
  const journey=data.learning?.journeys?.[state.journey];
  $('journey-player').hidden=!journey||state.level===4;
  if(!journey)return;
  state.step=Math.max(0,Math.min(state.step,journey.steps.length-1));
  const step=journey.steps[state.step];
  $('journey-player').innerHTML=`<div class="walkthrough-heading"><div><p class="eyebrow">WALK THROUGH ONE REQUEST</p><p>${escape(journey.scenario)}</p></div><div class="step-controls"><button class="quiet-button" data-walk="-1" ${state.step===0?'disabled':''}>Previous</button><span>${state.step+1} / ${journey.steps.length}</span><button class="quiet-button" data-walk="1" ${state.step===journey.steps.length-1?'disabled':''}>Next step</button></div></div><div class="walkthrough-body"><div><h2>${escape(step.title)}</h2><p>${escape(step.what)}</p></div><div><h3>Why this handoff exists</h3><p>${escape(step.why)}</p><span class="pill">${escape(step.mechanism)}</span>${partButton(step.node,'Inspect this step')}</div></div><p class="coverage-note">A source-guided explanation, not a replay of a live Nova request. Conditional branches may be skipped.</p>`;
}
function saveCheckpoint(){learner.checkpoint={at:new Date().toISOString(),revision:data.revision,nodes:Object.fromEntries(data.nodes.map(n=>[n.id,{hash:n.hash,label:n.label}]))};persistLearner();renderLiveLearning();toast('Checkpoint saved in this browser');}
function sourceChanges(){const old=learner.checkpoint?.nodes;if(!old)return null;const now=new Map(data.nodes.map(n=>[n.id,n]));return {added:data.nodes.filter(n=>!old[n.id]),changed:data.nodes.filter(n=>old[n.id]&&old[n.id].hash!==n.hash),removed:Object.keys(old).filter(id=>!now.has(id))};}
function renderLiveLearning(){
  const changes=sourceChanges(),review=data.review||[];
  const notebookOpen=$('live-learning').querySelector('details')?.open;
  const count=changes?changes.added.length+changes.changed.length+changes.removed.length:0;
  $('live-learning').innerHTML=`<details class="live-notebook" ${notebookOpen?'open':''}><summary>Catch up & revisit <span>${review.length} review leads${changes?' · '+count+' files changed since your checkpoint':''}</span></summary><div class="live-notebook-body"><section><h3>Since your saved checkpoint</h3><p>${changes?`${count} source files added, changed or removed since ${escape(dateLabel(learner.checkpoint.at))}. A source edit is not automatically a regression.`:'Save a checkpoint now; this browser can show you which mapped files changed when you return.'}</p><button class="quiet-button" id="save-checkpoint">${changes?'Replace checkpoint with this revision':'Save this revision as my checkpoint'}</button>${changes?`<div class="change-parts">${changes.added.map(n=>partButton(n.id,'Added: '+n.label)).join('')}${changes.changed.map(n=>partButton(n.id,'Changed: '+n.label)).join('')}${changes.removed.map(id=>`<p>Removed from map: <code>${escape(id)}</code></p>`).join('')}</div>`:''}</section><section><h3>Questions worth revisiting</h3><p>These are evidence gaps or integration questions. They are not automatic declarations that code is broken.</p>${review.map(r=>`<button class="list-button" data-review="${escape(r.id)}">${escape(r.title)}<small>${escape(r.kind)}</small></button>`).join('')||'<p>No generated review leads in this snapshot.</p>'}<button class="list-button" data-part-history="nova_memory">Old plan vs present code: memory helpers<small>The May 31 roadmap proposed retiring them. The current package still exists; inspect its consumers and whether the decision changed.</small></button></section></div></details>`;
}
function showImpact(id){
  const n=nodeRecord(id);if(!n)return;
  const rel=directRelationships(n),seen=new Set(rel.own),layers=[];let frontier=rel.own;
  for(let depth=0;depth<3;depth++){
    const next=new Set([...data.imports,...data.calls].filter(e=>frontier.has(e.to)&&!seen.has(e.from)).map(e=>e.from));
    if(!next.size)break;layers.push([...next]);next.forEach(v=>seen.add(v));frontier=next;
  }
  learnDialog('Changing '+n.label,`<p class="lead">These are possible affected callers, traced backward through imports and statically resolved calls. They are places to inspect and test, not a prediction that they will fail.</p>${layers.map((ids,i)=>`<h3>${i===0?'Direct callers / importers':`${i+1} dependency steps away`}</h3><div class="part-cloud">${ids.map(v=>partButton(v)).join('')}</div>`).join('')||'<p>No caller path was established by this static scope. Entry points, dynamic loading and callbacks still need inspection.</p>'}<h3>Dependencies you may need to preserve</h3><div class="part-cloud">${rel.outgoing.map(v=>partButton(v)).join('')||'<p>No external static dependency found.</p>'}</div><h3>Use this while planning</h3><ol><li>Name the behavior you want to change and the input that triggers it.</li><li>Read the selected implementation and its actual callers.</li><li>Preserve or deliberately change the input/output contract.</li><li>Check one success case, one failure case and the result's consumer.</li><li>Record the reason and verification in the timeline.</li></ol><p class="notice">Reviewed event/data-flow arrows are not treated as dependency edges here. Reflective calls, shared files and external systems can add impact this view cannot infer. The trace stops after three steps.</p>`,'CHANGE IMPACT · STATIC EVIDENCE');
}
function renderGlossary(query=''){
  const terms=(data.learning?.glossary||[]).filter(g=>(g.term+' '+g.meaning+' '+g.example).toLowerCase().includes(query.toLowerCase()));
  $('glossary-results').innerHTML=terms.map(g=>`<article class="glossary-term"><h3>${escape(g.term)}</h3><p>${escape(g.meaning)}</p><p class="example"><strong>In Nova:</strong> ${escape(g.example)}</p></article>`).join('')||'<p>No matching concept. Try a broader term.</p>';
}
function showGlossary(){learnDialog('The concepts behind the wiring','<p>Definitions tied to Nova, with networking and software boundaries made explicit.</p><label class="glossary-search">Find a concept<input id="glossary-search" type="search" placeholder="Callback, embedding, process…"></label><div id="glossary-results" class="glossary-grid"></div>');renderGlossary();}
function showSaved(){learnDialog('Your saved parts',`<p>Saved in this browser. Nova's own memory is not involved.</p>${learner.bookmarks.length?learner.bookmarks.map(id=>`<div class="saved-row">${nodeRecord(id)?partButton(id):`<span>${escape(id)} — no longer in this map</span>`}<button class="text-button" data-remove-bookmark="${escape(id)}">Remove</button></div>`).join(''):'<p>Select a component and choose Save part to build your own reading list.</p>'}`);}
function timelinePart(id){const n=nodeRecord(id);return n?.group||id;}
function openPartHistory(id){
  const n=nodeRecord(id);
  if(n&&!n.group&&!groups.has(id)){
    const related=[...new Set(data.connections.filter(e=>e.from===id||e.to===id).flatMap(e=>[groupId(e.from),groupId(e.to)]).filter(g=>groups.has(g)))];
    learnDialog('History around '+n.label,`<p>This boundary is used by the parts below. Select one to see its decisions and recorded source changes.</p>${related.map(g=>`<button class="inline-part" data-part-history="${escape(g)}">${escape(groupName(g))} ↗</button>`).join('')||'<p>No faculty history was linked to this boundary in the reviewed scope.</p>'}`,'RELATED HISTORY');return;
  }
  closeLearn();historyState.part=timelinePart(id);historyState.mode='all';historyState.month='';historyState.query='';historyState.limit=40;changeLevel(4);window.scrollTo({top:0,behavior:'smooth'});
}
function visibleDayFiles(day,part=historyState.part){return day.files.filter(f=>(historyState.noise||f.kind!=='housekeeping')&&(!part||groupForFile(f.file)===part));}
function dayMatchesPart(day,part){return !part||visibleDayFiles(day,part).length>0;}
function milestoneCard(event){
  return `<article class="timeline-event milestone"><div class="timeline-date"><time>${escape(event.date)}</time><span class="pill">${escape(event.stage||'Development record')}</span></div><h2>${escape(event.title)}</h2><p>${escape(event.what)}</p><div class="reason-block"><h3>${event.why_basis==='inferred'?'Purpose inferred from source':'Recorded reason'}</h3><p>${escape(event.why)}</p></div><details><summary>Tradeoff, verification & sources</summary><h3>Tradeoff</h3><p>${escape(event.tradeoff)}</p><h3>Verification and limits</h3><p>${escape(event.verification)}</p>${event.problems?.length?`<p class="notice">${event.problems.map(escape).join('<br>')}</p>`:''}${renderEvidence(event.evidence||[])}</details><div class="part-cloud">${(event.groups||[]).map(id=>partButton(id,groupName(id))).join('')}</div></article>`;
}
function dailyCard(day){
  const files=visibleDayFiles(day),parts=[...new Set(files.map(f=>groupForFile(f.file)))],meaningful=files.filter(f=>f.kind!=='housekeeping').length;
  const noise=day.files.filter(f=>f.kind==='housekeeping'&&(!historyState.part||groupForFile(f.file)===historyState.part)).length;
  const title=meaningful?`${meaningful} ${meaningful===1?'file':'files'} with net source changes`:'Snapshots with no net change beyond housekeeping';
  return `<article class="timeline-event"><div class="timeline-date"><time>${escape(day.date)}</time><span class="pill">Git · ${day.commits.length} ${day.commits.length===1?'snapshot':'snapshots'} across mapped scope</span></div><h2>${escape(title)}</h2><p>${parts.slice(0,4).map(groupName).map(escape).join(' · ')}${parts.length>4?' · and more':''}</p><p class="unknown-reason"><strong>Reason not established by these snapshots.</strong> Auto-save messages record when files were saved. Nearby development milestones may explain a change, but that relationship is not assumed.</p><button class="quiet-button" data-history-day="${escape(day.id)}">Inspect ${files.length} ${files.length===1?'file change':'file changes'} &amp; commit records</button>${noise?`<small class="history-noise-note">${noise} header/line-ending changes counted separately.</small>`:''}</article>`;
}
function renderTimeline(){
  const history=data.history||{};
  $('history-origin').textContent=history.origin||'Historical coverage has not been extracted.';
  const coverage=history.coverage||{};
  $('history-coverage').textContent=history.error||`${coverage.scoped_commits||0} source snapshots across ${(history.daily||[]).length} recorded days. ${coverage.oldest?'Retained source history: '+coverage.oldest.slice(0,10)+' to '+coverage.newest.slice(0,10)+'. ':''}${coverage.shallow?'This is a shallow Git clone; earlier history is missing. ':''}Dates use the offsets recorded by Git. Old verification is attributed to its original report.`;
  const partIds=new Set([...data.groups.map(g=>g.id),...(history.daily||[]).flatMap(d=>d.files.map(f=>groupForFile(f.file)))]);
  $('history-part').innerHTML='<option value="">All parts</option>'+[...partIds].sort((a,b)=>groupName(a).localeCompare(groupName(b))).map(id=>`<option value="${escape(id)}">${escape(groupName(id))}</option>`).join('');
  const months=[...new Set([...(history.daily||[]).map(d=>d.date.slice(0,7)),...(history.milestones||[]).map(d=>d.date.slice(0,7))])].sort();
  $('history-month').innerHTML='<option value="">All months</option>'+months.map(m=>`<option value="${m}">${m}</option>`).join('');
  $('history-mode').value=historyState.mode;$('history-part').value=historyState.part;$('history-month').value=historyState.month;$('history-order').value=historyState.order;$('history-noise').checked=historyState.noise;$('history-search').value=historyState.query;
  const q=historyState.query.toLowerCase(),events=[];
  if(historyState.mode!=='code')for(const e of history.milestones||[]){if((!historyState.part||(e.groups||[]).includes(historyState.part))&&JSON.stringify(e).toLowerCase().includes(q))events.push({...e,type:'milestone'});}
  if(historyState.mode!=='milestones')for(const e of history.daily||[]){if((historyState.noise||e.meaningful_files>0)&&dayMatchesPart(e,historyState.part)&&JSON.stringify(e).toLowerCase().includes(q))events.push({...e,type:'code'});}
  const filtered=events.filter(e=>!historyState.month||e.date.startsWith(historyState.month)).sort((a,b)=>(historyState.order==='oldest'?1:-1)*a.date.localeCompare(b.date));
  $('timeline-list').innerHTML=filtered.slice(0,historyState.limit).map(e=>e.type==='milestone'?milestoneCard(e):dailyCard(e)).join('')||'<p class="empty-history">No records match these filters. This does not prove that no work happened.</p>';
  $('history-count').textContent=`${filtered.length} matching records · ${Math.min(filtered.length,historyState.limit)} shown`;
  $('history-more').hidden=filtered.length<=historyState.limit;
  const working=(history.working||[]).filter(f=>!historyState.part||groupForFile(f.file)===historyState.part);
  $('working-changes').innerHTML=working.length?`<details class="working-changes"><summary>${working.length} mapped files differ from HEAD — uncommitted</summary><p>These changes are present now. Git does not supply their edit date or motivation.</p>${working.map(f=>`<p><span class="pill">${escape(f.kind)}</span>${index.has(f.file)?partButton(f.file,f.file):`<code>${escape(f.file)}</code>`}</p>`).join('')}</details>`:'';
}
function showDay(id){
  const day=data.history?.daily.find(d=>d.id===id);if(!day)return;
  const files=visibleDayFiles(day);
  learnDialog('Source changes · '+day.date,`<p>${escape(data.history.coverage.method)}</p><p>Reason: not inferred from an automatic-save message. The exact retained commits are listed below.</p><div class="history-files">${files.map(f=>`<article><span class="pill">${escape(f.kind)}</span><h3>${escape(f.file)}</h3><p>${escape(f.summary)}</p>${f.added_symbols?.length?`<p>Declarations added: <code>${f.added_symbols.map(escape).join(', ')}</code></p>`:''}${f.removed_symbols?.length?`<p>Declarations removed: <code>${f.removed_symbols.map(escape).join(', ')}</code></p>`:''}<button class="quiet-button" data-history-diff="${escape(day.id)}" data-file="${escape(f.file)}">Read before / after diff</button>${index.has(f.file)?partButton(f.file,'Open current component'):'<p class="coverage-note">This path is absent from the current source map.</p>'}</article>`).join('')}</div><details class="commit-list"><summary>${day.commits.length} retained commit records for this day</summary>${day.commits.map(c=>`<p><code>${escape(c.id.slice(0,12))}</code> · ${escape(c.when)}<br>${escape(c.title)}</p>`).join('')}</details>`,'GIT HISTORY · NET DAILY DIFF');
}
async function showHistoryDiff(day,file){
  $('source-title').textContent=file+' · '+day;$('source-code').textContent='Loading retained source diff…';$('source-note').textContent='Read-only Git evidence.';$('source-dialog').showModal();
  if(!hosted){$('source-code').textContent='Start RUN_MAP.cmd to inspect retained Git diffs. The saved atlas includes history summaries and commit references.';return;}
  try{const response=await fetch('/api/history/diff?'+new URLSearchParams({day,path:file}));if(!response.ok)throw Error('Historical diff unavailable');const result=await response.json();$('source-code').textContent=result.text||'No textual difference remains.';$('source-note').textContent=result.note+(result.truncated?' Display limited to the first 100,000 characters.':'');}catch(e){$('source-code').textContent=e.message;}
}
function downloadDecision(){const record={...data.history?.decision_template,date:new Date().toISOString().slice(0,10)};const blob=new Blob([JSON.stringify(record,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nova-decision-template.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Add the completed record to timeline.json and cite your decision note');}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.openPart){openPart(b.dataset.openPart);return;}
  if(b.dataset.impact){showImpact(b.dataset.impact);return;}
  if(b.dataset.partHistory){openPartHistory(b.dataset.partHistory);return;}
  if(b.dataset.bookmark){const id=b.dataset.bookmark;learner.bookmarks=learner.bookmarks.includes(id)?learner.bookmarks.filter(x=>x!==id):[...learner.bookmarks,id];persistLearner();renderDetail();return;}
  if(b.dataset.removeBookmark){learner.bookmarks=learner.bookmarks.filter(x=>x!==b.dataset.removeBookmark);persistLearner();showSaved();renderDetail();return;}
  if(b.dataset.walk){const journey=data.learning?.journeys?.[state.journey];if(!journey)return;state.step=Math.max(0,Math.min(journey.steps.length-1,state.step+Number(b.dataset.walk)));state.selected=journey.steps[state.step].node;state.symbol=null;state.edge=null;renderJourneyPlayer();renderDetail();highlight();save();return;}
  if(b.dataset.review){const item=data.review.find(x=>x.id===b.dataset.review);learnDialog(item.title,`<p>${escape(item.detail)}</p>${partButton(item.node,'Inspect the evidence')}`,'REVIEW LEAD · NOT A VERDICT');return;}
  if(b.dataset.historyDay){showDay(b.dataset.historyDay);return;}
  if(b.dataset.historyDiff){await showHistoryDiff(b.dataset.historyDiff,b.dataset.file);return;}
  if(b.dataset.copyLink){state.selected=b.dataset.copyLink;save();try{await navigator.clipboard.writeText(location.href);toast('Link copied');}catch(_){toast('Clipboard unavailable; the address bar contains the selected part');}return;}
  if(b.dataset.workBrief){const n=nodeRecord(b.dataset.workBrief),guide=data.learning?.groups?.[n.group||n.id],rel=directRelationships(n);const brief=`Help me work on ${n.label} in Project Nova.\nSource/reference: ${n.id}\nCurrent responsibility: ${n.summary}\n${guide?'Why it exists: '+guide.why+'\nBefore changing it: '+guide.change.join(' ')+'\n':''}Known static callers: ${rel.incoming.join(', ')||'None established in this scope'}\nKnown static dependencies: ${rel.outgoing.join(', ')||'None established in this scope'}\nDesired change: [describe the behavior I want].\nRead the current source and linked history, trace the input/output contract and relevant dynamic seams, propose a bounded change, verify it, and record the reason. Distinguish source inspection from a live Nova test.`;try{await navigator.clipboard.writeText(brief);toast('Work brief copied');}catch(_){learnDialog('Work brief',`<pre>${escape(brief)}</pre>`);}return;}
  if(b.id==='save-checkpoint')saveCheckpoint();
});
$('concepts-button').onclick=showGlossary;$('saved-button').onclick=showSaved;$('close-learning').onclick=closeLearn;
document.addEventListener('input',e=>{if(e.target.id==='glossary-search')renderGlossary(e.target.value);});
for(const [id,key] of [['history-mode','mode'],['history-part','part'],['history-month','month'],['history-order','order'],['history-noise','noise']])$(id).addEventListener('change',()=>{historyState[key]=id==='history-noise'?$(id).checked:$(id).value;historyState.limit=40;renderTimeline();});
$('history-search').addEventListener('input',()=>{historyState.query=$('history-search').value;historyState.limit=40;renderTimeline();$('history-search').focus();});
$('history-more').onclick=()=>{historyState.limit+=40;renderTimeline();};$('decision-template').onclick=downloadDecision;
