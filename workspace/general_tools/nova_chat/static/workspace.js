/* @nova: Mount Nova's dockable controller widgets while preserving their handlers and state.
   The runtime protocol and legacy layouts are deliberately independent of this face. */
(() => {
  if (new URLSearchParams(location.search).get('layout') === 'legacy') return;
  const $ = id => document.getElementById(id);
  const el = (tag, cls, text) => { const n=document.createElement(tag); n.className=cls||''; if(text)n.textContent=text; return n; };
  const button = (text, action, cls='nc-action') => { const b=el('button',cls,text); b.type='button'; b.onclick=action; return b; };
  $('lora-overlay').firstElementChild.id='controller-adapters';
  $('settings-overlay').firstElementChild.id='controller-profile';
  const definitions = [
    ['control','Control','Focus, verification, memory health and VM handoff',null],
    ['services','Services','Start, stop and inspect Nova’s services','dd-services'],
    ['adapters','Adapters','Inspect and equip Nova’s LoRA adapters','controller-adapters'],
    ['generation','Generation','Response settings and model parameters','dd-advanced'],
    ['profile','Profiles','Participant images and identity','controller-profile'],
    ['chat','Conversation','Talk with Nova','chat-main'],
    ['collaboration','Collaboration','A live workshop for Cole, Codex and Claude; separate from Nova',null],
    ['sidebar','Sessions','Browse and reopen conversations','sidebar'],
    ['tasks','Tasks','Your shared queue and next steps','tr-body'],
    ['tools','Activity','Widget executions, inputs and results','panel-tools'],
    ['thoughts','Thoughts','Nova’s streamed reasoning','panel-thoughts'],
    ['computer','Computer','Observe and interact with Nova’s VM',null],
    ['files','Files','Explore the workspace','panel-files'],
    ['editor','File viewer','Inspect a file without leaving your work',null],
    ['terminal','Terminal','Commands and server output','panel-terminal'],
    ['browser','Preview','Open a local application or page',null],
    ['eyes','Perceptions','Images Nova has actually looked at','panel-eyes'],
    ['pipeline','Pipeline','Follow cognition and execution stages','panel-pipeline'],
    ['logs','Live log','Nova’s ongoing activity','novaLog'],
    ['console','Console','Service logs and diagnostics','novaConsole'],
    ['monitor','System','Resource use and runtime telemetry','panel-monitor'],
    ['variables','Variables','Adjust Nova’s live settings','panel-variables']
  ];
  const registry = new Map();
  const defaults={mode:'together'};
  let state={...defaults};
  try { const saved=JSON.parse(localStorage.getItem('nova.controller.v1')||'{}');
    for(const key of Object.keys(defaults)) if(typeof saved[key]===typeof defaults[key])state[key]=saved[key];
  } catch(_) {}
  if(!['together','observe','focus'].includes(state.mode))state.mode='together';
  const save=()=>{try{localStorage.setItem('nova.controller.v1',JSON.stringify(state));}catch(_){}};
  document.body.classList.add('controller');
  const main=$('main-area');
  const store=el('div'); store.hidden=true; document.body.append(store);
  ['sidebar-handle','panel-handle','right-panel','task-rail','queue-panel'].forEach(id=>{if($(id))store.append($(id));});
  const header=el('header','nc-header');
  const identity=el('div','nc-identity'); identity.append(el('span','nc-mark','✦'),el('strong','','Nova'),el('span','nc-caption',document.body.dataset.preview==='true'?'UI preview · simulated data':'Shared workspace'));
  const modes=el('nav','nc-modes'); modes.setAttribute('aria-label','Workspace');
  for(const [id,name] of [['together','Together'],['observe','Observe'],['focus','Focus']]){
    const b=button(name,()=>{state.mode=id;render();},'nc-mode'); b.dataset.mode=id; modes.append(b);
  }
  const actions=el('div','nc-header-actions');
  actions.append(button('Collaboration',()=>showWidget('collaboration'),'nc-action ncc-shortcut'),button('Control',()=>showWidget('control')),button('Widgets  ⌘',()=>openLibrary()),button('Sessions',()=>window.toggleSidebar()));
  header.append(identity,modes,actions); $('menubar').after(header);
  const workspace=el('div','nc-docking'); main.append(workspace);
  let layout=null, loadedMode=null, saving=false, chatOnly=false; const containers=new Map();
  for(const [id,title,description,nodeId] of definitions){
    let node=nodeId?$(nodeId):null;
    if(id==='tasks'&&!node){node=el('div','tr-body');node.id='tr-body';}
    if(!node)node=el('div','nc-custom-widget');
    node.dataset.widget=id; store.append(node); registry.set(id,{id,title,description,node});
  }
  // Viewers keep their DOM when moved, preserving iframe, terminal and scroll state.
  window.mountNovaControl?.(registry.get('control').node);
  window.mountNovaCollaboration?.(registry.get('collaboration').node);
  for(const id of ['computer','browser']){
    const node=registry.get(id).node; node.classList.add('nv-browser');
    const bar=el('div','nbw-bar'); const input=el('input','nbw-url');
    input.setAttribute('aria-label',id==='computer'?'VM desktop address':'Preview address');
    input.value=id==='computer'?'http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale':'';
    try{input.value=localStorage.getItem('nova.widget.'+id+'.url')||input.value;}catch(_){}
    input.placeholder='http://localhost:3000';
    const frame=el('iframe','nbw-frame'); frame.title=id==='computer'?'Nova VM desktop':'Application preview'; frame.src='about:blank';
    const intro=el('div','nc-viewer-intro');
    intro.append(el('span','nc-orbit',id==='computer'?'⌘':'↗'),el('h2','',id==='computer'?'Her desktop. Your shared view.':'A place to see what you’re building.'),el('p','',id==='computer'?'Connect to the VM’s desktop viewer to observe or interact with it.':'Enter an address above to open a preview. Some sites require an external browser.'));
    const open=()=>{let url=input.value.trim();if(!url)return;if(!/^https?:\/\//i.test(url))url='http://'+url;
      try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol))return;frame.src=parsed.href;try{localStorage.setItem('nova.widget.'+id+'.url',parsed.href);}catch(_){}intro.hidden=true;frame.hidden=false;}catch(_){toast('Enter a valid HTTP address');}};
    input.onkeydown=e=>{if(e.key==='Enter')open();}; frame.hidden=true;
    bar.append(input,button(id==='computer'?'Connect':'Open',open),button('↗',()=>{const url=frame.src!=='about:blank'?frame.src:input.value;if(/^https?:\/\//i.test(url))window.open(url,'_blank');}));
    bar.lastChild.setAttribute('aria-label','Open in external browser');node.append(bar,intro,frame);
  }
  const editor=registry.get('editor').node; editor.classList.add('nv-editor');
  const editorHead=el('div','ned-head');const editorName=el('span','ned-name','No file selected');editorName.id='ned-name';
  const code=el('code','ned-code','Select a file in the Files widget to read it here.');code.id='ned-code';const pre=el('pre','ned-pre');pre.append(code);
  editorHead.append(editorName,button('Copy',()=>navigator.clipboard.writeText(code.textContent).then(()=>toast('Copied'),()=>toast('Clipboard unavailable'))));editor.append(editorHead,pre);
  let fileRequest=0;
  window.openInEditor=async(path,name)=>{
    const request=++fileRequest;showWidget('editor');editorName.textContent=name||path;code.textContent='Loading…';
    try{const response=await fetch('/api/files/read?path='+encodeURIComponent(path));if(!response.ok)throw Error('File unavailable');const data=await response.json();if(request===fileRequest)code.textContent=data.error||data.content||'(empty)';}
    catch(error){if(request===fileRequest)code.textContent=error.message;}
  };
  window.novaWidgetVisible=id=>!!registry.get(id)?.node.getClientRects().length;
  async function refresh(id){
    if(!window.novaWidgetVisible(id))return;
    const actions={services:window.pollServices,tools:window.refreshActivity,logs:window.novaLogRefresh,adapters:window.loadLora,profile:window.buildAvatarSettings,tasks:window.refreshBoard,files:window.refreshFiles,pipeline:window.plPoll,variables:window.varsPoll,eyes:window.sightRefresh,monitor:window.pollMonitor,terminal:()=>{termRenderTabs();termSwitch(_termActive);}};
    try{await actions[id]?.();}catch(error){console.warn('Widget refresh:',id,error);toast(registry.get(id).title+': '+error.message);}
  }
  function showWidget(id){
    if(!registry.has(id)||!layout)return;
    const container=containers.get(id);
    if(layout.maximisedStack && layout.maximisedStack!==container?.parent?.parent)layout.maximisedStack.minimise();
    if(container)container.focus();
    else {const target=containers.get('chat')?.parent?.parent;if(target?.type==='stack')target.addItem(comp(id));else layout.addComponent('nova',{id},registry.get(id).title);}
    refresh(id);if(library.open)library.close();
  }
  window.ensureWidget=id=>showWidget(id);
  window.toggleWidget=id=>showWidget(id);
  window.switchPanel=id=>showWidget(id);
  window.openLora=()=>showWidget('adapters');
  window.openSettings=()=>showWidget('profile');
  window.closeLora=()=>containers.get('adapters')?.close();
  window.closeSettings=()=>containers.get('profile')?.close();
  for(const [menu,id] of [['services','services'],['advanced','generation']]){const trigger=document.querySelector('[data-dd="'+menu+'"]');if(trigger)trigger.onclick=()=>showWidget(id);}
  window.togglePanel=()=>{state.mode=state.mode==='focus'?'together':'focus';render();};
  window.toggleSidebar=()=>{const c=containers.get('sidebar');if(c)c.close();else showWidget('sidebar');};
  const comp=id=>({type:'component',componentType:'nova',componentState:{id},title:registry.get(id).title});
  const stack=(ids,extra={})=>({type:'stack',content:ids.map(comp),...extra});
  function preset(mode){
    const chat=stack(['chat'],{size:mode==='observe'?'30%':'52%'});
    const side=stack(['sidebar'],{size:'16%'});
    const right={type:'column',size:'32%',content:[stack(['control','tasks','thoughts','tools'],{size:'60%'}),stack(['logs','monitor'],{size:'40%'})]};
    const content=mode==='focus'?[chat]:mode==='observe'?[chat,{type:'column',size:'70%',content:[stack(['computer','eyes'],{size:'70%'}),stack(['tools','pipeline','console'],{size:'30%'})]}]:[side,chat,right];
    return {root:{type:'row',content},settings:{popInOnClose:true},dimensions:{borderWidth:8,headerHeight:40,defaultMinItemWidth:'180px',defaultMinItemHeight:'120px'},header:{popout:'Open in a separate window',maximise:'Expand widget',minimise:'Restore widget',close:'Close widget',dock:'Return to main window'}};
  }
  function persistLayout(){if(!layout||layout.isSubWindow||saving||!loadedMode)return;try{const saved=layout.saveLayout();localStorage.setItem('nova.controller.dock.'+loadedMode,JSON.stringify(saved));}catch(_){}}
  function render(){
    if(!layout)return;
    modes.querySelectorAll('button').forEach(b=>{b.classList.toggle('active',b.dataset.mode===state.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));});
    if(layout.isSubWindow)return;
    if(loadedMode!==state.mode){
      persistLayout();saving=true;let config=preset(state.mode);
      try{const saved=JSON.parse(localStorage.getItem('nova.controller.dock.'+state.mode)||'null');if(saved){config=NovaDock.LayoutConfig.fromResolved(saved);const returned=(config.openPopouts||[]).map(p=>p.root).filter(Boolean);config.openPopouts=[];if(returned.length)config.root={type:'row',content:[...(config.root?[config.root]:[]),...returned]};}}catch(_){}
      try{layout.loadLayout(config);}catch(error){console.warn('Layout restored to preset',error);layout.loadLayout(preset(state.mode));}
      loadedMode=state.mode;saving=false;
    }
    save();layout.setSize(workspace.clientWidth,workspace.clientHeight);
  }
  const library=el('dialog','nc-library');library.setAttribute('aria-label','Widget library');
  const libraryHeader=el('header','nc-library-header');libraryHeader.append(el('h2','','Widgets'),button('Close',()=>library.close()));
  const search=el('input','nc-search');search.placeholder='Find a widget…';search.setAttribute('aria-label','Find a widget');
  const results=el('div','nc-library-grid');
  const fill=()=>{results.replaceChildren();for(const item of registry.values()){
    if(!(item.title+' '+item.description).toLowerCase().includes(search.value.toLowerCase()))continue;
    const b=button('',()=>showWidget(item.id),'nc-library-item');b.append(el('strong','',item.title),el('span','',item.description));results.append(b);
  }if(!results.children.length)results.append(el('p','nc-no-results','No matching widgets.'));};
  search.oninput=fill;library.append(libraryHeader,search,results);document.body.append(library);
  library.onclick=e=>{if(e.target===library)library.close();};
  function openLibrary(){search.value='';fill();library.showModal();search.focus();}
  window.novaWidgets=openLibrary;
  const widgetsMenu=document.querySelector('[data-dd="widgets"]');if(widgetsMenu)widgetsMenu.onclick=()=>openLibrary();
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='k'){e.preventDefault();openLibrary();}});
  // Keep the composer calm. Less-used controls remain in an explicit options popover.
  const options=el('details','nc-composer-options');const summary=el('summary','','Options');const optionBody=el('div','nc-options-body');options.append(summary,optionBody);
  ['user-new','user-del','reinject-btn'].forEach(id=>{if($(id))optionBody.append($(id));});
  const advanced=document.querySelector('.input-bar-right');if(advanced)optionBody.append(advanced);
  document.querySelector('.input-bar-left')?.append(options);
  $('input').placeholder='Message Nova…';$('input').setAttribute('aria-label','Message Nova');
  const newChat=document.querySelector('.new-session-btn');
  if(newChat){newChat.firstChild.nodeValue='＋ New chat ';newChat.title='Start a new conversation';}
  $('send-btn').setAttribute('aria-label','Send message or stop response');
  const empty=el('div','nc-chat-empty');empty.append(el('span','nc-orbit','✦'),el('h1','','A space to think together.'),el('p','','Talk with Nova, follow her work, or open a widget alongside your conversation.'));
  $('chat').append(empty);
  const syncEmpty=()=>{empty.hidden=Array.from($('chat').children).some(n=>n!==empty);};new MutationObserver(syncEmpty).observe($('chat'),{childList:true});
  // Offline is a connection state, never evidence that Nova is asleep.
  const syncConnection=()=>{const online=typeof ws!=='undefined'&&ws?.readyState===1;document.body.classList.toggle('nc-offline',!online);document.body.classList.toggle('nc-model-offline',!agentOnline.Nova);$('pb-auto').disabled=chatOnly||!online;$('pb-wake').disabled=chatOnly||!online;};
  new MutationObserver(syncConnection).observe($('menu-status'),{childList:true,characterData:true,subtree:true});
  new MutationObserver(syncConnection).observe($('pb-state-nova'),{childList:true,characterData:true,subtree:true});
  syncConnection();
  window.pollThoughts=()=>{}; // The Tasks widget owns the queue; Thoughts shows reasoning.
  const bind=(container,config)=>{
    const id=config.componentState?.id;const item=registry.get(id);
    if(!item)throw Error('Unknown widget '+id);
    const body=el('div','nc-pane-body');body.dataset.widget=id;body.append(item.node);container.element.append(body);containers.set(id,container);
    container.on('destroy',()=>{store.append(item.node);containers.delete(id);});
    container.on('show',()=>refresh(id));
    setTimeout(()=>refresh(id),0);return {component:item.node,virtual:false};
  };
  layout=new NovaDock.GoldenLayout(workspace,bind);
  function enhanceDockControls(){
    workspace.querySelectorAll('.lm_controls>*,.lm_close_tab').forEach(control=>{
      control.setAttribute('aria-label',control.title||'Close widget');
      if(control.dataset.keyboard)return;
      control.dataset.keyboard='true';control.tabIndex=0;control.setAttribute('role','button');
      control.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();event.stopPropagation();control.click();}});
    });
  }
  new MutationObserver(enhanceDockControls).observe(workspace,{childList:true,subtree:true});
  enhanceDockControls();
  if(layout.isSubWindow){document.body.classList.add('nc-popout');}
  let layoutSaveTimer;
  layout.on('stateChanged',()=>{enhanceDockControls();clearTimeout(layoutSaveTimer);layoutSaveTimer=setTimeout(persistLayout,250);});
  // Save popouts before the library tears down. Its unload closes child windows;
  // those must not try to bind components back into an already destroyed layout.
  window.addEventListener('beforeunload',()=>{
    persistLayout();
    if(!layout.isSubWindow)layout.layoutConfig.settings.popInOnClose=false;
  },{capture:true});
  new ResizeObserver(()=>layout.setSize(workspace.clientWidth,workspace.clientHeight)).observe(workspace);
  actions.append(button('Customize',()=>customize.showModal()));
  const customize=el('dialog','nc-library');customize.setAttribute('aria-label','Customize workspace');
  const ch=el('header','nc-library-header');ch.append(el('h2','','Make this space yours'),button('Close',()=>customize.close()));customize.append(ch,el('p','nc-custom-help','Drag widget tabs to reorder, stack, or split. Drag the dividers to resize. Use a widget’s popout control to move it into its own window. Each workspace remembers its arrangement.'));
  const density=el('select','nc-search');density.setAttribute('aria-label','Interface density');for(const [v,t] of [['comfortable','Comfortable'],['compact','Compact']]){const o=el('option','',t);o.value=v;density.append(o);}
  const accent=el('input','nc-search');accent.type='color';accent.setAttribute('aria-label','Accent color');
  let appearance={density:'comfortable',accent:'#b5a0f6'};try{appearance={...appearance,...JSON.parse(localStorage.getItem('nova.controller.appearance')||'{}')};}catch(_){}
  function style(){document.body.dataset.density=appearance.density;document.body.style.setProperty('--nova',appearance.accent);try{localStorage.setItem('nova.controller.appearance',JSON.stringify(appearance));}catch(_){}}
  density.value=appearance.density;accent.value=appearance.accent;density.onchange=()=>{appearance.density=density.value;style();};accent.oninput=()=>{appearance.accent=accent.value;style();};style();
  customize.append(el('label','','Density'),density,el('label','','Accent'),accent,button('Restore this workspace’s default layout',()=>{saving=true;layout.loadLayout(preset(state.mode));saving=false;persistLayout();customize.close();}));document.body.append(customize);
  render();
  const chatOnlyReason='Nova is disabled in chat-only mode. Use Collaboration, or close this controller and launch NovaStart.cmd to enable Nova.';
  function applyChatOnly(enabled){
    chatOnly=enabled===true;document.body.dataset.chatOnly=String(chatOnly);
    if(!chatOnly)return;
    identity.querySelector('.nc-caption').textContent='Chat only · Nova is off';
    const notice=el('div','ncc-chat-only');notice.append(el('strong','','Nova is off in this controller'),el('p','',chatOnlyReason),button('Open Collaboration',()=>showWidget('collaboration')));$('chat-main').append(notice);
    for(const id of ['input','send-btn','pb-auto','pb-wake','pb-nova','da-mute-nova','auto-toggle','llama-start-btn','llama-stop-btn','reinject-btn']){
      const node=$(id);if(node){node.disabled=true;node.title=chatOnlyReason;node.dataset.chatOnlyBlocked='true';}
    }
    for(const node of document.querySelectorAll('.new-session-btn,.stab-add,button[onclick*="novaRestart(\'server\')"],button[onclick*="novaRestart(\'nova\')"]')){
      node.disabled=true;node.title=chatOnlyReason;node.dataset.chatOnlyBlocked='true';
    }
    registry.get('control').node.querySelectorAll('button').forEach(node=>{if(node.textContent!=='Services and restart'){node.disabled=true;node.title=chatOnlyReason;node.dataset.chatOnlyBlocked='true';}});
    document.addEventListener('click',event=>{if(event.target.closest('[data-chat-only-blocked=true]')){event.preventDefault();event.stopImmediatePropagation();toast(chatOnlyReason);}},true);
    syncConnection();if(!layout.isSubWindow)showWidget('collaboration');
  }
  fetch('/api/version',{cache:'no-store'}).then(response=>response.ok?response.json():null).then(version=>{if(version?.chat_only)applyChatOnly(true);}).catch(()=>{});

})();

