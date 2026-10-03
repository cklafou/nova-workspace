// @nova: Browser code for the interactive architecture explorer (built into Orient/Architecture/index.html): zoom levels, search, journeys, live updates.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const snapshot = window.NOVA_ARCHITECTURE;
  let latest = snapshot, data = snapshot, status = null, index = new Map(), groups = new Map(), edgeRefs = [], bounds = {width:1000,height:600};
  const hosted = location.protocol === 'http:' || location.protocol === 'https:';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nova-atlas-view') || '{}'); } catch (_) {}
  const hashLevel = Number(new URLSearchParams(location.hash.slice(1)).get('level'));
  const state = {level:[1,2,3,4].includes(hashLevel)?hashLevel:1, selected:null, simpleNode:null, focus:null, symbol:null, journey:'', step:0, scale:1, x:25, y:25, edge:null};
  let lastAsset = null, polling = false;

  function reindex() {
    index = new Map([...data.nodes,...data.resources].map(n => [n.id,n]));
    groups = new Map(data.groups.map(g => [g.id,g]));
  }
  function save() {
    try { localStorage.setItem('nova-atlas-view', JSON.stringify({level:state.level,focus:state.focus,selected:state.selected,journey:state.journey})); } catch (_) {}
    const params=new URLSearchParams({level:String(state.level)});
    if(state.selected)params.set('node',state.selected);if(state.focus)params.set('focus',state.focus);if(state.journey)params.set('journey',state.journey);
    history.replaceState(null,'', '#'+params);
  }
  function dateLabel(value) { return new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
  function label(id) { return (index.get(id)||groups.get(id)||data.simple.nodes.find(n=>n.id===id)||{}).label || id; }
  function allEdges() { return [...data.imports,...data.calls,...data.connections]; }
  function evidenceButton(ref) {
    const key = edgeRefs.push(ref)-1;
    return `<button class="source-button" data-evidence="${key}">${escape(ref.file)}:${ref.line || 1} ↗</button>`;
  }
  function renderEvidence(refs) {
    return refs.map(ref => `<div class="evidence-item">${evidenceButton(ref)}${ref.text?`<p><code>${escape(ref.text)}</code></p>`:''}${ref.symbol?`<small>${escape(ref.symbol)}</small>`:''}</div>`).join('');
  }
  function reviewPill(n) {
    return n.status==='parse_error'?'<span class="pill caution">Parse failed</span>':n.explanation_status==='needs_review'?'<span class="pill caution">Explanation needs review</span>':'<span class="pill good">Source inspected</span>';
  }
  function renderIntro() {
    const levels = {
      1:['LEVEL 1 · THE BIG PICTURE','How Nova fits together.','Follow a message, a thought, or a memory. Select a part to see what it does.'],
      2:['LEVEL 2 · THE SOURCE SNAPSHOT','See the actual wiring.','Explore faculties, modules, calls, files and process boundaries. Every mapped connection leads back to source.'],
      3:['LEVEL 3 · THE LIVING ARCHITECTURE','A map that follows the code.','See what changed, revisit uncertain wiring, and keep explanations tied to their source.'],
      4:['YOUR PROJECT HISTORY','How Nova got here.','Connect the code to the decisions, fixes and unfinished work that shaped it.']
    };
    const [eyebrow,title,desc] = levels[state.level];
    $('level-eyebrow').textContent=eyebrow; $('page-title').textContent=title; $('page-description').textContent=desc;
    document.body.classList.toggle('simple-view',state.level===1);
    document.querySelectorAll('[data-level]').forEach(b=>{const active=Number(b.dataset.level)===state.level;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
    $('advanced-controls').hidden=state.level===1||state.level===4;
    $('evidence-section').hidden=state.level===1||state.level===4;
    $('map-controls').hidden=state.level===4;$('workspace').hidden=state.level===4;$('timeline-page').hidden=state.level!==4;
    $('refresh-button').hidden=state.level<3 || !hosted;
    $('build-time').textContent='Generated '+dateLabel(data.generated_at);
    $('revision-label').textContent='Revision '+data.revision;
    $('scope-note').textContent=state.level===1
      ? 'The computer is shown separately because its normal conversation connection is not established by this source map. A line means information or a request passes between parts.'
      : 'Arrow direction: caller / reader → dependency or destination. Imports are not execution order. Detachable tool internals are omitted; attachment seams stay visible.';
    $('journey').innerHTML='<option value="">Whole architecture</option>'+data.journeys.map(j=>`<option value="${escape(j.id)}">${escape(j.label)}</option>`).join('');
    $('journey').value=state.journey;
    renderStatus();
    renderExperience();
  }
  function renderStatus() {
    $('live-status').className='';
    if(state.level<3) { $('live-label').textContent='Source snapshot · not a runtime trace'; return; }
    if(!hosted) { $('live-label').textContent='Offline snapshot · run RUN_MAP.cmd for updates'; $('live-status').className='disconnected'; return; }
    if(status?.watching) { $('live-label').textContent=status.error?'Watcher active · build needs attention':'Watching workspace · automatic refresh'; $('live-status').className=status.error?'disconnected':'watching'; }
    else { $('live-label').textContent='Watcher disconnected · last snapshot retained'; $('live-status').className='disconnected'; }
  }
  function changeLevel(level) {
    state.level=level;data=level>=3?latest:snapshot;reindex();
    state.focus=null;state.symbol=null;state.edge=null;state.selected=null;state.simpleNode=null;state.journey='';
    renderIntro();renderGraph(true);renderDetail();renderInventory();save();
    if(level>=3&&hosted) poll();
  }
  function edgesForView() {
    const mode=$('edge-filter').value;
    if(mode==='imports')return data.imports;
    if(mode==='calls')return data.calls;
    if(mode==='all')return allEdges();
    return [...data.imports.filter(e=>groupId(e.from)!==groupId(e.to)),...data.connections];
  }
  function groupId(id) {return index.get(id)?.group || id;}
  function nodeRecord(id) {return groups.get(id)||index.get(id);}
  function displayGraph() {
    if(state.level===1 && !state.journey) {
      const connections=new Map(data.connections.map(e=>[e.id,e]));
      return {nodes:data.simple.nodes.map(n=>({...n,kind:n.id==='chat'?'boundary':'body',simple:true})),
        edges:data.simple.edges.map(e=>({...e,kind:'flow',items:e.connection&&connections.has(e.connection)?[connections.get(e.connection)]:[],status:connections.get(e.connection)?.status}))};
    }
    let nodes=[],edges=edgesForView(), mapId=id=>groupId(id);
    if(state.journey) {
      const journey=data.journeys.find(j=>j.id===state.journey);
      nodes=(journey?.nodes||[]).map(id=>index.get(id)).filter(Boolean).map(n=>({...n,lane:n.group?groups.get(n.group)?.lane: n.lane}));
      const wanted=new Set(nodes.map(n=>n.id));
      edges=allEdges().filter(e=>wanted.has(e.from)&&wanted.has(e.to));mapId=id=>id;
    } else if(state.focus) {
      const own=data.nodes.filter(n=>n.group===state.focus);
      const ownIds=new Set(own.map(n=>n.id));
      edges=edges.filter(e=>ownIds.has(e.from)||ownIds.has(e.to));
      mapId=id=>ownIds.has(id)?id:groupId(id);
      const adjacent=new Set(edges.flatMap(e=>[mapId(e.from),mapId(e.to)]).filter(id=>!ownIds.has(id)));
      const split=own.length>6;
      const outward=new Set(edges.filter(e=>ownIds.has(e.from)).map(e=>mapId(e.to)));
      nodes=own.map((n,i)=>({...n,lane:1+(split?i%2:0),order:Math.floor(i/(split?2:1))}));
      nodes.push(...[...adjacent].map(id=>nodeRecord(id)).filter(Boolean).map((n,i)=>({...n,lane:outward.has(n.id)?3:0,order:i})));
    } else {
      nodes=data.groups.map(g=>({...g,moduleCount:data.nodes.filter(n=>n.group===g.id).length}));
      if($('show-resources').checked)nodes.push(...data.resources);
    }
    if(state.symbol)edges=edges.filter(e=>e.kind==='call'&&((e.from===state.selected&&e.caller===state.symbol)||(e.to===state.selected&&e.callee===state.symbol)));
    const visible=new Set(nodes.map(n=>n.id)), joined=new Map();
    edges.forEach(e=>{
      const from=mapId(e.from),to=mapId(e.to);
      if(!visible.has(from)||!visible.has(to)||from===to)return;
      const key=from+'|'+to;
      if(!joined.has(key))joined.set(key,{from,to,items:[],label:'',kind:e.kind});
      joined.get(key).items.push(e);
    });
    for(const edge of joined.values()){
      const kinds=[...new Set(edge.items.map(e=>e.kind))];
      edge.label=kinds.join(' + ');
      edge.status=edge.items.some(e=>e.status==='needs_review')?'needs_review':'source_checked';
    }
    return {nodes,edges:[...joined.values()]};
  }
  let currentGraph={nodes:[],edges:[]}, positions=new Map();
  function renderGraph(reset=false) {
    if(state.level===4)return;
    currentGraph=displayGraph();positions=new Map();
    const lanes=new Map();
    for(const n of currentGraph.nodes){const lane=n.lane??2;if(!lanes.has(lane))lanes.set(lane,[]);lanes.get(lane).push(n);}
    const laneKeys=[...lanes.keys()].sort((a,b)=>a-b);
    const simpleStack=state.level===1&&!state.journey&&$('map-viewport').clientWidth<650;
    document.body.classList.toggle('stacked-simple',simpleStack);
    const width=simpleStack?270:234,spacing=290,rowHeight=127;
    const laneLabels=state.level===1&&!state.journey?['INPUT','CONTEXT & DIRECTION','REASONING','OUTPUT']:['ATTACHMENTS','COORDINATION','BODY FACULTIES','OTHER PROCESSES','PERSISTENT DATA'];
    let nodeHTML='',maxY=200;
    laneKeys.forEach((lane,column)=>{
      const values=lanes.get(lane).sort((a,b)=>(a.order??50)-(b.order??50)||a.label.localeCompare(b.label));
      nodeHTML+=`<span class="lane-label" style="left:${column*spacing+28}px;top:12px">${escape(state.focus?(column===0?'CONNECTED PARTS':column===laneKeys.length-1?'DEPENDENCIES':'MODULES'):(laneLabels[lane]||'COMPONENTS'))}</span>`;
      values.forEach((n,row)=>{
        const simpleOrder=['human','chat','senses','cortex','memory','model','actions','computer'];
        const x=simpleStack?58:column*spacing+28,y=simpleStack?simpleOrder.indexOf(n.id)*140+30:row*rowHeight+48;positions.set(n.id,{x,y,width,height:100});maxY=Math.max(maxY,y+135);
        const isGroup=groups.has(n.id),ownModules=isGroup?data.nodes.filter(v=>v.group===n.id):[];
        const incoming=isGroup?data.imports.filter(e=>ownModules.some(v=>v.id===e.to)&&groupId(e.from)!==n.id).length:0;
        const stale=n.explanation_status==='needs_review'||n.status==='parse_error';
        const kicker=n.simple?'':isGroup?(n.kind==='boundary'?'Attachment boundary':'Body faculty'):(n.group?'Module':n.kind==='service'?'Process / service':n.kind==='boundary'?'Excluded internals':n.kind==='external'?'External service':'Persistent data');
        const caption=n.simple?n.plain:isGroup?`${ownModules.length} modules · ${incoming} inbound imports`:n.group?n.id.split('/').pop():(n.plain||n.path||n.kind);
        nodeHTML+=`<button class="graph-node ${escape(n.kind||'body')} ${stale?'needs-review':''}" style="left:${x}px;top:${y}px;width:${width}px" data-map-node="${escape(n.id)}" aria-label="${escape(n.label+'. '+caption)}">${kicker?`<span class="node-kicker">${escape(kicker)}</span>`:''}<span class="node-title">${escape(n.label)}</span><span class="node-caption">${escape(caption)}</span>${stale?'<span class="node-dot" aria-label="Explanation needs review"></span>':''}</button>`;
      });
    });
    bounds={width:simpleStack?385:laneKeys.length*spacing+15,height:maxY};
    $('map-viewport').style.height=simpleStack?Math.ceil(maxY*Math.min(1,($('map-viewport').clientWidth-24)/385)+65)+'px':'';
    const svg=$('graph-lines');svg.setAttribute('width',bounds.width);svg.setAttribute('height',bounds.height);
    let svgHTML='<defs><marker id="arrow-normal" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="#6d879e"/></marker><marker id="arrow-active" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="#81d9c4"/></marker></defs>';
    currentGraph.edges.forEach((e,i)=>{
      const a=positions.get(e.from),b=positions.get(e.to);if(!a||!b)return;
      let x1=a.x+(b.x>=a.x?a.width:0),x2=b.x+(b.x>=a.x?0:b.width),y1=a.y+48,y2=b.y+48;
      let d;if(simpleStack){
        if(b.y-a.y===140){x1=x2=a.x+a.width/2;y1=a.y+100;y2=b.y;d=`M${x1},${y1} L${x2},${y2}`;}
        else{const side=e.from==='actions'?a.x+a.width:a.x;x1=x2=side;const bend=side+(e.from==='actions'?44:-44);d=`M${x1},${y1} C${bend},${y1} ${bend},${y2} ${x2},${y2}`;}
      }else if(a.x===b.x){x1=a.x+a.width;x2=b.x+b.width;d=`M${x1},${y1} C${x1+38},${y1} ${x2+38},${y2} ${x2},${y2}`;}
      else {const dx=Math.max(35,Math.abs(x2-x1)/2);d=`M${x1},${y1} C${x1+(x2>x1?dx:-dx)},${y1} ${x2-(x2>x1?dx:-dx)},${y2} ${x2},${y2}`;}
      const midx=(x1+x2)/2,midy=(y1+y2)/2;
      svgHTML+=`<path class="graph-edge ${e.status==='needs_review'?'caution':''}" data-edge-line="${i}" d="${d}" marker-end="url(#arrow-normal)"/><path class="graph-edge-hit" data-graph-edge="${i}" d="${d}"/><text class="edge-label" data-edge-label="${i}" x="${midx}" y="${midy-8}" text-anchor="middle" style="display:none">${escape(e.label.length>32?e.label.slice(0,30)+'…':e.label)}</text>`;
    });
    svg.innerHTML=svgHTML;$('graph-nodes').innerHTML=nodeHTML;
    $('empty-map').hidden=Boolean(currentGraph.nodes.length);
    $('graph-count').textContent=`${currentGraph.nodes.length} parts · ${currentGraph.edges.length} connections`;
    $('crumb').textContent=state.journey?'/ '+(data.journeys.find(j=>j.id===state.journey)?.label||''):state.focus?'/ '+label(state.focus)+(state.symbol?' / '+state.symbol:''):'';
    if(reset)fitMap();else applyTransform();
    highlight();
  }
  function fitMap(){const v=$('map-viewport');state.scale=Math.min(1,(v.clientWidth-24)/bounds.width,(v.clientHeight-75)/bounds.height);state.x=(v.clientWidth-bounds.width*state.scale)/2;state.y=16;applyTransform();}
  function applyTransform(){$('graph-stage').style.transform=`translate(${state.x}px,${state.y}px) scale(${state.scale})`;$('zoom-label').textContent=Math.round(state.scale*100)+'%';}
  function zoom(factor){const v=$('map-viewport'),before=state.scale;state.scale=Math.max(.35,Math.min(1.8,before*factor));state.x=v.clientWidth/2-(v.clientWidth/2-state.x)*state.scale/before;state.y=v.clientHeight/2-(v.clientHeight/2-state.y)*state.scale/before;applyTransform();}
  function highlight(){
    const requested=state.level===1&&!state.journey?(state.simpleNode||data.simple.nodes.find(n=>n.target===state.selected)?.id):state.selected;
    const selected=currentGraph.nodes.some(n=>n.id===requested)?requested:null;
    const connected=new Set(selected?[selected]:[]);
    currentGraph.edges.forEach((e,i)=>{
      const active=(selected&&(e.from===selected||e.to===selected))||state.edge===i;
      if(active){connected.add(e.from);connected.add(e.to);}
      const line=document.querySelector(`[data-edge-line="${i}"]`),text=document.querySelector(`[data-edge-label="${i}"]`);
      line?.classList.toggle('highlight',Boolean(active));line?.setAttribute('marker-end',active?'url(#arrow-active)':'url(#arrow-normal)');
      if(text)text.style.display=active||(state.level===1&&!state.journey)?'':'none';
    });
    document.querySelectorAll('[data-map-node]').forEach(b=>{b.classList.toggle('selected',b.dataset.mapNode===selected);b.classList.toggle('faded',Boolean(selected&&connected.size&& !connected.has(b.dataset.mapNode)));});
  }
  function selectNode(id){
    const simple=data.simple.nodes.find(n=>n.id===id);
    state.simpleNode=state.level===1&&!state.journey?simple?.id:null;
    if(state.level===1&&!state.journey&&simple)id=simple.target;
    state.selected=id;state.symbol=null;state.edge=null;renderDetail();highlight();save();
    if(window.innerWidth<=850)$('detail-panel').scrollIntoView({block:'start',behavior:'smooth'});
  }
  function focusGroup(id,selected=null){
    if(state.level===1||state.level===4){state.level=state.level===4?3:2;data=state.level===3?latest:snapshot;reindex();renderIntro();renderInventory();}
    state.focus=id;state.selected=selected||null;state.symbol=null;state.journey='';state.edge=null;$('journey').value='';renderGraph(true);renderDetail();renderExperience();save();
  }
  function starter(){
    const j=data.journeys.find(v=>v.id===state.journey);
    if(j)return `<h2>${escape(j.label)}</h2><p class="lead">${escape(j.description)}</p><h3>The parts along this flow</h3>${j.nodes.filter(id=>index.has(id)).map((id,i)=>`<button class="list-button" data-node="${escape(id)}"><span class="arrow">↗</span>${i+1}. ${escape(label(id))}<small>${escape(index.get(id).summary.slice(0,125))}</small></button>`).join('')}<p>The list describes the flow; source-call ordering, branches and callbacks are available on each connection.</p>`;
    if(state.level===1)return `<h2>One system.<br>Several kinds of work.</h2><p class="lead">The model generates language. Nova's surrounding body gives it context, senses, decisions, memory and ways to act.</p><div class="flow-step"><span class="step-number">1</span><p>You speak, or Nova's own wake cycle starts.</p></div><div class="flow-step"><span class="step-number">2</span><p>Relevant context and memories accompany the request to think.</p></div><div class="flow-step"><span class="step-number">3</span><p>The response loop checks evidence, performs requested actions and returns a reply.</p></div><h3>Try a path</h3>${data.journeys.slice(0,3).map(j=>`<button class="list-button" data-journey="${escape(j.id)}">${escape(j.label)} <span class="arrow">→</span></button>`).join('')}`;
    return `<h2>Read the connections.</h2><p class="lead">Select a faculty to inspect its modules. Select a connection to see the exact mechanism and source evidence.</p><div class="flow-step"><span class="step-number">1</span><p><strong>Faculties</strong> explain responsibilities.</p></div><div class="flow-step"><span class="step-number">2</span><p><strong>Modules</strong> expose functions, imports and call sites.</p></div><div class="flow-step"><span class="step-number">3</span><p><strong>Evidence</strong> opens the relevant source location.</p></div><h3>What this map can prove</h3><p>${escape(data.scope.evidence)}</p><h3>What is excluded</h3><p>${escape(data.scope.boundary)}</p>${state.level===3&&!hosted?'<p class="notice">This is a saved snapshot. Run RUN_MAP.cmd in this folder to start the live watcher.</p>':''}`;
  }
  function renderDetail(){
    $('close-detail').hidden=!state.selected&&state.edge===null;
    if(state.edge!==null){renderEdgeDetail();return;}
    const n=nodeRecord(state.selected);
    if(!n){$('detail-kind').textContent=state.journey?'FOLLOW A FLOW':'START EXPLORING';$('detail-content').innerHTML=starter();return;}
    const isGroup=groups.has(n.id);
    $('detail-kind').textContent=isGroup?(n.kind==='boundary'?'ATTACHMENT BOUNDARY':'BODY FACULTY'):n.group?'MODULE':'PROCESS / DATA BOUNDARY';
    const simple=state.level===1&&!state.journey?data.simple.nodes.find(v=>v.id===state.simpleNode):null;
    let out=`<h2>${escape(simple?.label||n.label)}</h2><p class="lead">${escape(simple?.description||n.summary)}</p>`;
    if(simple?.description)out+=`<h3>Where this lives</h3><p>${escape(n.label)}: ${escape(n.summary)}</p>`;
    out+=componentLearning(n);
    if(n.group)out+=`<div class="path"><code>${escape(n.id)}</code></div>${reviewPill(n)}`;
    if(n.explanation_status==='needs_review')out+='<p class="notice">This file changed after its explanation was reviewed. Imports, symbols and resolved calls below are regenerated from the current source.</p>';
    if(isGroup){
      const own=data.nodes.filter(v=>v.group===n.id),ids=new Set(own.map(v=>v.id));
      const incoming=data.imports.filter(e=>ids.has(e.to)&&!ids.has(e.from));
      out+=`<span class="pill">${own.length} modules</span><span class="pill">${incoming.length} incoming import references</span>`;
      if(!incoming.length)out+='<p class="notice">No cross-package import was found in this scope. This is a wiring clue, not a declaration that the package is unused.</p>';
      out+=`<div class="detail-actions"><button class="primary-button" data-focus="${escape(n.id)}">Explore this faculty</button><button class="quiet-button" data-copy="${escape(n.id)}">Copy reference</button></div>`;
      if(n.notes?.length)out+='<h3>Boundaries to understand</h3>'+n.notes.map(s=>`<p>${escape(s)}</p>`).join('');
      out+='<h3>Inside this part</h3>'+own.map(v=>`<button class="list-button" data-focus="${escape(n.id)}" data-select="${escape(v.id)}">${escape(v.label)}<small>${escape(v.id.split('/').pop())}</small></button>`).join('');
    } else if(n.group){
      out+=`<div class="detail-actions"><button class="quiet-button" data-focus="${escape(n.group)}" data-select="${escape(n.id)}">Show neighbors</button><button class="quiet-button" data-copy="${escape(n.id)}">Copy reference</button></div>`;
      out+=renderEvidence([{file:n.id,line:1,text:n.id}]);
      const seams=data.connections.filter(e=>e.from===n.id||e.to===n.id);
      if(seams.length)out+='<h3>Architecture connections</h3>'+seams.map(e=>`<button class="list-button" data-connection="${escape(e.id)}">${escape(e.label)}<small>${escape(e.kind)} · ${e.status==='needs_review'?'needs review':'source checked'}</small></button>`).join('');
      if(state.symbol){
        const symbol=n.symbols.find(s=>s.name===state.symbol);
        out+=`<h3>${escape(state.symbol)}</h3><p>${escape(symbol?.summary||'No function description in source.')}</p>`;
        if(symbol)out+=renderEvidence([{file:n.id,line:symbol.line,symbol:symbol.name,text:symbol.signature}]);
        const calls=data.calls.filter(e=>(e.from===n.id&&e.caller===state.symbol)||(e.to===n.id&&e.callee===state.symbol));
        out+=`<h3>${calls.length} resolved call sites</h3>`+calls.map(e=>`<div class="connection-detail">${escape(e.caller)} → ${escape(e.callee)}<br>${renderEvidence(e.evidence)}</div>`).join('');
      }
      out+='<h3>Declared classes and functions</h3>'+n.symbols.map(s=>`<button class="list-button" data-symbol="${escape(s.name)}">${escape(s.name)}<small>Line ${s.line} · ${escape(s.kind)}${s.summary?' · '+escape(s.summary.slice(0,85)):''}</small></button>`).join('');
      if(n.routes?.length)out+=`<h3>${n.routes.length} HTTP / WebSocket declarations</h3>`+n.routes.map(r=>`<div class="evidence-item"><code>${escape(r.method)} ${escape(r.path)}</code><br>${evidenceButton({file:n.id,line:r.line,text:r.path})}</div>`).join('');
      const unresolved=data.unresolved.filter(u=>u.file===n.id&&(!state.symbol||u.scope===state.symbol));
      if(unresolved.length)out+=`<details><summary>${unresolved.length} unresolved / external references</summary>${unresolved.map(u=>`<div class="evidence-item"><code>${escape(u.expression)}</code><p>${escape(u.reason)}</p>${evidenceButton({file:u.file,line:u.line,text:u.expression,symbol:u.scope})}</div>`).join('')}</details>`;
    } else {
      if(n.path)out+=`<p><code>${escape(n.path)}</code><br>${n.present?'Present in this checkout':'Not present in this checkout'}</p>`;
      if(n.url)out+=`<p><code>${escape(n.url)}</code><br>${escape(n.port_origin)}</p>`;
      const service=status?.services?.find(s=>s.id===n.id);
      if(service)out+=`<p class="service-status"><b>${service.listening?'TCP listener detected':'No TCP listener detected'}</b> at ${escape(service.host)}:${service.port}. This is not an inference/VM test.</p>`;
      if(n.url_evidence)out+=renderEvidence([n.url_evidence]);
      out+='<h3>Connected faculties</h3>'+data.connections.filter(e=>e.from===n.id||e.to===n.id).map(e=>`<button class="list-button" data-connection="${escape(e.id)}">${escape(e.label)}<small>${escape(e.kind)}</small></button>`).join('');
    }
    $('detail-content').innerHTML=out;
  }
  function renderConnection(edge){
    $('detail-kind').textContent='REVIEWED ARCHITECTURE CONNECTION';$('close-detail').hidden=false;
    $('detail-content').innerHTML=`<h2>${escape(edge.label)}</h2><p>${escape(label(edge.from))} → ${escape(label(edge.to))}</p><span class="pill">${escape(edge.kind)}</span><span class="pill ${edge.status==='needs_review'?'caution':'good'}">${edge.status==='needs_review'?'Needs review':'Source checked'}</span>${edge.problems?.length?`<p class="notice">${edge.problems.map(escape).join('<br>')}</p>`:''}<h3>Evidence</h3>${renderEvidence(edge.evidence)}<p>Source evidence establishes this connection in the code. It is not a live execution trace.</p>`;
  }
  function renderEdgeDetail(){
    const edge=currentGraph.edges[state.edge];if(!edge)return;
    $('detail-kind').textContent='CONNECTION EVIDENCE';
    $('detail-content').innerHTML=`<h2>${escape(label(edge.from))} → ${escape(label(edge.to))}</h2><p class="lead">${escape(edge.label)}</p><p>${edge.items.length} source references. Static dependency arrows are not a promise of execution order.</p>`+edge.items.map(e=>`<div class="evidence-item"><span class="pill ${e.status==='needs_review'?'caution':''}">${escape(e.kind)}</span><p>${escape(e.label)}</p>${e.caller?`<p><code>${escape(e.caller)} → ${escape(e.callee)}</code></p>`:''}${e.conditions?.length?`<p>Conditional: ${e.conditions.map(escape).join('; ')}</p>`:''}${e.problems?.length?`<p class="notice">${e.problems.map(escape).join('; ')}</p>`:''}${renderEvidence(e.evidence||[])}</div>`).join('');
  }
  function renderInventory(){
    const stale=data.connections.filter(e=>e.status==='needs_review').length;
    $('coverage').textContent=`${data.nodes.length} mapped modules · ${data.imports.length} import references · ${data.calls.length} statically resolved call sites · ${data.connections.length} reviewed architecture seams · ${data.errors.length} parse failures · ${stale} seams need review. ${data.unresolved.length} external/dynamic references are retained as unresolved. No live execution is implied.`;
    $('inventory').innerHTML=data.groups.map(g=>{
      const own=data.nodes.filter(n=>n.group===g.id);
      return `<details class="inventory-group"><summary>${escape(g.label)}<span>${own.length} modules</span></summary><p>${escape(g.summary)}</p><table><thead><tr><th>Module</th><th>Responsibility</th><th>Evidence</th></tr></thead><tbody>${own.map(n=>`<tr><td><button data-focus="${escape(g.id)}" data-select="${escape(n.id)}">${escape(n.label)}</button><br><code>${escape(n.id)}</code></td><td>${escape(n.summary)}</td><td>${reviewPill(n)}<br>${n.symbols.length} declarations</td></tr>`).join('')}</tbody></table></details>`;
    }).join('')+`<details class="inventory-group"><summary>Supporting launch and provisioning files<span>${(data.definitions||[]).length} files</span></summary><p>These definitions are watched alongside Python source. They are not executed by this map.</p>${(data.definitions||[]).map(d=>`<div class="evidence-item">${evidenceButton({file:d.id,line:1,text:d.kind})}</div>`).join('')}</details>`+(data.errors.length?'<h3>Parse failures</h3>'+data.errors.map(e=>`<p class="notice">${escape(e.file+': '+e.message)}</p>`).join(''):'');
  }
  function setJourney(id){
    state.journey=id;state.step=0;state.focus=null;state.selected=null;state.symbol=null;state.edge=null;$('journey').value=id;renderGraph(true);renderDetail();renderExperience();save();
  }
  async function source(ref){
    $('source-title').textContent=ref.file+':'+(ref.line||1);$('source-code').textContent=ref.text||'';
    $('source-note').textContent='Evidence from the generated snapshot.';$('source-dialog').showModal();
    if(!hosted){$('source-note').textContent='Saved evidence excerpt. Start RUN_MAP.cmd to open surrounding source lines.';return;}
    try{
      const query=new URLSearchParams({path:ref.file,line:String(ref.line||1)});
      const response=await fetch('/api/source?'+query);if(!response.ok)throw Error('Source unavailable');
      const result=await response.json();$('source-note').textContent=ref.historical?'Current copy of a historical development record. Its past verification claims do not certify today’s runtime.':'Current file on disk · read only. Snapshot and file may differ after edits.';
      $('source-code').innerHTML=result.lines.map((s,i)=>`<span${result.start+i===Number(ref.line)?' class="highlight-line"':''}>${String(result.start+i).padStart(5)}  ${escape(s)}</span>`).join('\n');
    }catch(error){$('source-note').textContent=error.message+'; showing saved evidence.';}
  }
  function search(){
    const q=$('search').value.trim().toLowerCase();if(!q){$('search-results').hidden=true;return;}
    const hits=[];
    for(const g of data.groups)if((g.label+' '+g.id+' '+g.summary).toLowerCase().includes(q))hits.push({id:g.id,title:g.label,sub:g.summary,group:true});
    for(const n of data.nodes){
      if((n.label+' '+n.id+' '+n.summary).toLowerCase().includes(q))hits.push({id:n.id,title:n.label,sub:n.id});
      for(const s of n.symbols)if(s.name.toLowerCase().includes(q))hits.push({id:n.id,title:s.name,sub:n.id+':'+s.line,symbol:s.name});
    }
    $('search-results').hidden=false;
    $('search-results').innerHTML=hits.length?hits.slice(0,35).map(h=>`<button data-search-node="${escape(h.id)}" ${h.symbol?`data-search-symbol="${escape(h.symbol)}"`:''}>${escape(h.title)}<small>${escape(h.sub)}</small></button>`).join(''):`<p>No matching faculty, module or declaration.</p>`;
  }
  async function poll(){
    if(!hosted||polling)return;polling=true;
    try{
      const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw Error('Unavailable');
      const previousServices=JSON.stringify(status?.services);
      status=await response.json();
      if(status.app!=='nova-architecture-atlas')throw Error('Different server');
      if(lastAsset&&lastAsset!==status.asset_revision){save();location.reload();return;}lastAsset=status.asset_revision;
      if(status.revision!==latest.revision){
        const r=await fetch('/api/map',{cache:'no-store'});if(!r.ok)throw Error('Map unavailable');latest=await r.json();
        if(state.level>=3){const previous=data.revision;data=latest;reindex();state.edge=null;if(state.selected&&!nodeRecord(state.selected))state.selected=null;if(state.focus&&!groups.has(state.focus))state.focus=null;renderIntro();renderGraph(false);renderDetail();renderInventory();if(previous!==data.revision)toast('Architecture updated from source');}
      }
      renderStatus();
      if(previousServices!==JSON.stringify(status.services)&&index.get(state.selected)?.port)renderDetail();
    }catch(_){status=null;renderStatus();}finally{polling=false;}
  }
  function toast(message){let t=document.querySelector('.toast');if(t)t.remove();t=document.createElement('div');t.className='toast';t.setAttribute('role','status');t.textContent=message;document.body.appendChild(t);setTimeout(()=>t.remove(),2800);}
  document.addEventListener('click',async event=>{
    const b=event.target.closest('button');if(!b)return;
    if(b.dataset.level){changeLevel(Number(b.dataset.level));return;}
    if(b.dataset.mapNode){selectNode(b.dataset.mapNode);return;}
    if(b.dataset.focus){focusGroup(b.dataset.focus,b.dataset.select);$('workspace').scrollIntoView({block:'start',behavior:'smooth'});return;}
    if(b.dataset.node){selectNode(b.dataset.node);return;}
    if(b.dataset.evidence!==undefined){source(edgeRefs[Number(b.dataset.evidence)]);return;}
    if(b.dataset.connection){renderConnection(data.connections.find(e=>e.id===b.dataset.connection));return;}
    if(b.dataset.journey){setJourney(b.dataset.journey);return;}
    if(b.dataset.symbol){state.symbol=b.dataset.symbol;renderGraph(false);renderDetail();return;}
    if(b.dataset.copy){const n=nodeRecord(b.dataset.copy);try{await navigator.clipboard.writeText(`Explain ${n.label} in Project Nova. Source: ${n.id}. Check its incoming and outgoing connections and distinguish source wiring from live execution.`);toast('Reference copied');}catch(_){toast('Clipboard unavailable; source path is shown in the details');}return;}
    if(b.dataset.searchNode){const n=nodeRecord(b.dataset.searchNode);if(n.group)focusGroup(n.group,n.id);else focusGroup(n.id);if(b.dataset.searchSymbol){state.symbol=b.dataset.searchSymbol;renderGraph(false);renderDetail();}$('search-results').hidden=true;return;}
  });
  $('graph-lines').addEventListener('click',event=>{const e=event.target.closest('[data-graph-edge]');if(e){state.edge=Number(e.dataset.graphEdge);state.selected=null;renderDetail();highlight();}});
  $('journey').addEventListener('change',()=>setJourney($('journey').value));
  $('show-resources').addEventListener('change',()=>renderGraph(true));$('edge-filter').addEventListener('change',()=>{state.edge=null;renderGraph(false);renderDetail();});
  $('search').addEventListener('input',search);
  $('home-map').onclick=()=>{state.focus=null;state.selected=null;state.simpleNode=null;state.journey='';state.symbol=null;state.edge=null;$('journey').value='';renderGraph(true);renderDetail();renderExperience();save();};
  $('close-detail').onclick=()=>{state.selected=null;state.simpleNode=null;state.edge=null;state.symbol=null;renderDetail();renderGraph(false);if(window.innerWidth<=850)$('workspace').scrollIntoView({block:'start',behavior:'smooth'});};
  $('zoom-in').onclick=()=>zoom(1.15);$('zoom-out').onclick=()=>zoom(1/1.15);$('fit-map').onclick=fitMap;$('reset-map').onclick=()=>{state.scale=1;state.x=25;state.y=25;applyTransform();};
  $('about-button').onclick=()=>$('about-dialog').showModal();$('close-about').onclick=()=>$('about-dialog').close();$('close-source').onclick=()=>$('source-dialog').close();
  document.querySelector('.brand').onclick=e=>{e.preventDefault();changeLevel(1);};
  $('inventory-button').onclick=()=>$('evidence-section').scrollIntoView({behavior:'smooth'});
  $('refresh-button').onclick=poll;
  $('print-button').onclick=()=>{document.querySelectorAll('.inventory-group').forEach(d=>d.open=true);window.print();};
  $('download-json').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='nova-architecture-'+data.revision+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  let drag=null;
  $('map-viewport').addEventListener('pointerdown',e=>{if(document.body.classList.contains('stacked-simple')||e.target.closest('button')||e.target.closest('[data-graph-edge]'))return;drag={x:e.clientX,y:e.clientY,ox:state.x,oy:state.y};$('map-viewport').setPointerCapture(e.pointerId);});
  $('map-viewport').addEventListener('pointermove',e=>{if(!drag)return;state.x=drag.ox+e.clientX-drag.x;state.y=drag.oy+e.clientY-drag.y;applyTransform();});
  $('map-viewport').addEventListener('pointerup',()=>drag=null);$('map-viewport').addEventListener('pointercancel',()=>drag=null);
  $('map-viewport').addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();zoom(e.deltaY<0?1.08:1/1.08);}},{passive:false});
  /*__EXPERIENCE__*/
  reindex();renderIntro();renderGraph(true);renderDetail();renderInventory();
  let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>renderGraph(true),120);});
  window.addEventListener('hashchange',()=>{
    const params=new URLSearchParams(location.hash.slice(1)),level=Number(params.get('level'));
    if(![1,2,3,4].includes(level))return;
    if(level!==state.level)changeLevel(level);
    state.focus=groups.has(params.get('focus'))?params.get('focus'):null;
    state.selected=nodeRecord(params.get('node'))?params.get('node'):null;
    state.journey=data.journeys.some(j=>j.id===params.get('journey'))?params.get('journey'):'';
    state.step=0;state.edge=null;state.symbol=null;state.simpleNode=null;
    renderIntro();renderGraph(true);renderDetail();save();
  });
  const deepLink=new URLSearchParams(location.hash.slice(1));
  if(state.level!==4){const focus=deepLink.get('focus')||(state.level===3?saved.focus:null),node=deepLink.get('node');if(focus&&groups.has(focus))state.focus=focus;if(node&&nodeRecord(node))state.selected=node;const journey=deepLink.get('journey');if(journey&&data.journeys.some(j=>j.id===journey))state.journey=journey;renderGraph(true);renderDetail();renderExperience();}
  if(hosted){poll();setInterval(poll,2500);}
})();
