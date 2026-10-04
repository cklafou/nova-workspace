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
    ['services','Services','Start, stop and inspect Nova’s services',null],
    ['adapters','Adapters','Inspect and equip Nova’s LoRA adapters','controller-adapters'],
    ['generation','Generation','Response settings and model parameters',null],
    ['profile','Profiles','Participant images and identity','controller-profile'],
    ['chat','Conversation','Talk with Nova','chat-main'],
    ['collaboration','Collaboration','A live workshop for Cole, Codex and Claude; separate from Nova',null],
    ['updater','Model updates','Review model updates, installations and training',null],
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
  const LAYOUTS_KEY='nova.controller.layouts.v2';
  const clone=value=>JSON.parse(JSON.stringify(value));
  function readSavedLayouts(){
    let previous=null;
    try{
      previous=localStorage.getItem(LAYOUTS_KEY);
      if(previous){
        const saved=JSON.parse(previous);
        if(saved.version!==2||!Array.isArray(saved.items)||!saved.items.length)throw Error('Invalid layout collection');
        const ids=new Set();
        for(const item of saved.items){
          if(!item||typeof item.id!=='string'||!item.id||ids.has(item.id)||typeof item.name!=='string'||!item.name.trim())throw Error('Invalid saved layout');
          ids.add(item.id);
        }
        if(!ids.has(saved.activeId))saved.activeId=saved.items[0].id;
        if(!Array.isArray(saved.deleted))saved.deleted=[];
        return saved;
      }
    }catch(error){
      // Preserve unreadable data before creating a usable collection; old mode keys are never changed.
      if(previous)try{localStorage.setItem(LAYOUTS_KEY+'.recovery.'+Date.now(),previous);}catch(_){}
      console.warn('Could not read saved layouts',error);
    }
    let active='together';
    try{const legacy=JSON.parse(localStorage.getItem('nova.controller.v1')||'{}');if(['together','observe','focus'].includes(legacy.mode))active=legacy.mode;}catch(_){}
    const items=[];
    for(const mode of ['together','observe','focus']){
      let config=null;
      try{config=JSON.parse(localStorage.getItem('nova.controller.dock.'+mode)||'null');}catch(_){}
      if(config||mode===active)items.push({id:'migrated-'+mode,name:config?mode[0].toUpperCase()+mode.slice(1):'My workspace',seed:mode,config});
    }
    return {version:2,activeId:'migrated-'+active,items,deleted:[]};
  }
  let savedLayouts=readSavedLayouts(),storageWarning=false;
  const currentLayout=()=>savedLayouts.items.find(item=>item.id===savedLayouts.activeId)||savedLayouts.items[0];
  const hadSavedArrangement=!!currentLayout().config;
  function saveLayouts(){
    try{localStorage.setItem(LAYOUTS_KEY,JSON.stringify(savedLayouts));storageWarning=false;layoutSaved.textContent='Saved';layoutSaved.title='Your layouts save automatically on this device.';return true;}
    catch(error){layoutSaved.textContent='Not saved';layoutSaved.title='Local storage is unavailable or full.';if(!storageWarning){toast('Layout could not be saved. Local storage is unavailable or full.');storageWarning=true;}return false;}
  }
  document.body.classList.add('controller');
  const main=$('main-area');
  const store=el('div'); store.hidden=true; document.body.append(store);
  ['sidebar-handle','panel-handle','right-panel','task-rail','queue-panel'].forEach(id=>{if($(id))store.append($(id));});
  const header=el('header','nc-header');
  const modeStatus=el('span','nc-mode-status','Nova off · Chat only');modeStatus.id='nc-mode-status';modeStatus.hidden=true;modeStatus.setAttribute('role','status');modeStatus.title='Only the controller is running. Nova and the model are disabled in chat-only mode.';$('statusbar')?.prepend(modeStatus);
  const identity=el('div','nc-identity'); identity.append(el('span','nc-mark','✦'),el('strong','','Nova'),el('span','nc-caption',document.body.dataset.preview==='true'?'UI preview · simulated data':'Shared workspace'));
  const layoutPicker=el('div','nc-layout-picker');
  const layoutSelect=el('select','nc-layout-select');layoutSelect.setAttribute('aria-label','Saved layout');layoutSelect.title='Switch saved layout';
  const layoutManage=button('⋯',()=>openLayoutManager(),'nc-action nc-layout-manage');layoutManage.setAttribute('aria-label','Manage layouts');layoutManage.title='Create, rename, duplicate or delete layouts';
  const layoutSaved=el('span','nc-layout-saved','Saved');layoutSaved.setAttribute('aria-live','polite');
  layoutPicker.append(el('span','nc-layout-label','Layout'),layoutSelect,layoutManage,layoutSaved);
  const actions=el('div','nc-header-actions');
  const menuBar=$('menubar');menuBar.after(header);header.append(identity,menuBar,layoutPicker,actions);
  const workspace=el('div','nc-docking'); main.append(workspace);
  let layout=null, loadedLayoutId=null, saving=false, chatOnly=false; const containers=new Map();
  for(const [id,title,description,nodeId] of definitions){
    let node=nodeId?$(nodeId):null;
    if(id==='tasks'&&!node){node=el('div','tr-body');node.id='tr-body';}
    if(!node)node=el('div','nc-custom-widget');
    node.dataset.widget=id; store.append(node); registry.set(id,{id,title,description,node});
  }
  // Menus remain anchored in the document. Optional Services/Generation widgets mirror
  // those controls and forward input to their originals, so IDs and legacy handlers stay unique.
  const menuMirrors=[];
  for(const [id,sourceId] of [['services','dd-services'],['generation','dd-advanced']]){
    const source=$(sourceId),target=registry.get(id).node;if(!source)continue;
    target.classList.add('nc-menu-widget');const mirror=source.cloneNode(true);mirror.removeAttribute('id');mirror.classList.remove('dropdown','open');mirror.classList.add('nc-menu-mirror');
    const originals=[source,...source.querySelectorAll('*')],copies=[mirror,...mirror.querySelectorAll('*')];
    originals.forEach((original,index)=>{
      const copy=copies[index];copy.removeAttribute('id');
      for(const attribute of [...copy.attributes])if(attribute.name.startsWith('on'))copy.removeAttribute(attribute.name);
      if(original.matches('input,select,textarea')){
        for(const eventName of ['input','change'])copy.addEventListener(eventName,()=>{original.value=copy.value;if('checked' in original)original.checked=copy.checked;original.dispatchEvent(new Event(eventName,{bubbles:true}));});
      }else if(original.matches('button,[onclick]'))copy.addEventListener('click',event=>{event.preventDefault();original.click();});
    });
    const sync=()=>originals.forEach((original,index)=>{const copy=copies[index];if(!copy)return;if(original.children.length===0&& !original.matches('input,select,textarea'))copy.textContent=original.textContent;if('disabled' in original)copy.disabled=original.disabled;if('value' in original&&document.activeElement!==copy)copy.value=original.value;if('checked' in original)copy.checked=original.checked;if(index>0){copy.className=original.className;copy.style.cssText=original.style.cssText;}});
    new MutationObserver(sync).observe(source,{childList:true,attributes:true,characterData:true,subtree:true});target.append(mirror);menuMirrors.push({id,sync});sync();
  }
  const mirrorTimer=setInterval(()=>{for(const mirror of menuMirrors)if(window.novaWidgetVisible?.(mirror.id))mirror.sync();},500);
  window.addEventListener('pagehide',()=>clearInterval(mirrorTimer),{once:true});
  // Viewers keep their DOM when moved, preserving iframe, terminal and scroll state.
  window.mountNovaControl?.(registry.get('control').node);
  window.mountNovaCollaboration?.(registry.get('collaboration').node);
  window.mountNovaUpdater?.(registry.get('updater').node);
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
    if(!registry.has(id)||!layout||saving)return;
    const containsWidget=item=>item&&(item.componentState?.id===id||(item.content||[]).some(containsWidget));
    for(const popout of layout.openPopouts){
      try{if(containsWidget(popout.getGlInstance()?.saveLayout().root)){popout.getWindow().focus();if(library.open)library.close();return;}}catch(_){}
    }
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
  window.togglePanel=()=>{const c=containers.get('tools');if(c)c.close();else showWidget('tools');};
  window.toggleSidebar=()=>{const c=containers.get('sidebar');if(c)c.close();else showWidget('sidebar');};
  const comp=id=>({type:'component',componentType:'nova',componentState:{id},title:registry.get(id).title});
  const stack=(ids,extra={})=>({type:'stack',content:ids.map(comp),...extra});
  function starterLayout(mode='together'){
    const chat=stack(['chat'],{size:mode==='observe'?'30%':'52%'});
    const side=stack(['sidebar'],{size:'16%'});
    const right={type:'column',size:'32%',content:[stack(['control','tasks','thoughts','tools'],{size:'60%'}),stack(['logs','monitor'],{size:'40%'})]};
    const content=mode==='focus'?[chat]:mode==='observe'?[chat,{type:'column',size:'70%',content:[stack(['computer','eyes'],{size:'70%'}),stack(['tools','pipeline','console'],{size:'30%'})]}]:[side,chat,right];
    return {root:{type:'row',content},settings:{popInOnClose:true},dimensions:{borderWidth:8,headerHeight:40,defaultMinItemWidth:'180px',defaultMinItemHeight:'120px'},header:{popout:'Open in a separate window',maximise:'Expand widget',minimise:'Restore widget',close:'Close widget',dock:'Return to main window'}};
  }
  function persistLayout(){
    if(!layout||layout.isSubWindow||saving||!loadedLayoutId)return;
    const item=savedLayouts.items.find(entry=>entry.id===loadedLayoutId);if(!item)return;
    try{item.config=layout.saveLayout();item.updatedAt=new Date().toISOString();saveLayouts();}catch(error){console.warn('Layout save failed',error);}
  }
  function refreshLayoutPicker(){
    layoutSelect.replaceChildren();
    for(const item of savedLayouts.items){const option=el('option','',item.name);option.value=item.id;layoutSelect.append(option);}
    layoutSelect.value=savedLayouts.activeId;
  }
  function layoutConfig(item){
    let config=item.config?NovaDock.LayoutConfig.fromResolved(clone(item.config)):starterLayout(item.seed);
    // Reclaim saved popouts on restore rather than reopening stale browser windows. Their widgets survive.
    const returned=(config.openPopouts||[]).map(popout=>popout.root).filter(Boolean);config.openPopouts=[];
    if(returned.length)config.root={type:'row',content:[...(config.root?[config.root]:[]),...returned]};
    return config;
  }
  async function render(){
    if(!layout)return;
    refreshLayoutPicker();
    if(layout.isSubWindow)return;
    const item=currentLayout();
    if(loadedLayoutId!==item.id){
      persistLayout();saving=true;
      if(layout.openPopouts.length){
        // Golden Layout schedules window.close(); loading immediately lets the old
        // window's unload callback pop its widget into the newly selected layout.
        const windows=layout.openPopouts.map(popout=>popout.getWindow());
        layoutSelect.disabled=true;layoutManage.disabled=true;
        layout.layoutConfig.settings.popInOnClose=false;layout.closeAllOpenPopouts();
        const closed=await new Promise(resolve=>{
          const deadline=Date.now()+3000;
          const check=()=>{if(windows.every(child=>child.closed))resolve(true);else if(Date.now()>=deadline)resolve(false);else setTimeout(check,20);};check();
        });
        layoutSelect.disabled=false;layoutManage.disabled=false;
        if(!closed){saving=false;savedLayouts.activeId=loadedLayoutId;refreshLayoutPicker();toast('Close the separate widget windows before switching layouts.');return false;}
        layout.layoutConfig.openPopouts=[];
      }
      try{layout.loadLayout(layoutConfig(item));}
      catch(error){savedLayouts.deleted=[...(savedLayouts.deleted||[]),{...clone(item),deletedAt:new Date().toISOString(),reason:'restore-failed'}].slice(-20);console.warn('Saved layout could not be restored',error);toast('This layout could not be restored. Its original saved data is preserved.');layout.loadLayout(starterLayout());}
      loadedLayoutId=item.id;saving=false;
    }
    saveLayouts();layout.setSize(workspace.clientWidth,workspace.clientHeight);syncEmptyDock();return true;
  }
  layoutSelect.onchange=()=>{if(saving)return;persistLayout();savedLayouts.activeId=layoutSelect.value;render();};
  const layoutManager=el('dialog','nc-library nc-layout-dialog');layoutManager.setAttribute('aria-label','Manage layouts');
  const managerHead=el('header','nc-library-header');managerHead.append(el('h2','','Saved layouts'),button('Close',()=>layoutManager.close()));
  const managerHelp=el('p','nc-custom-help','Arrange any widgets, resize the dividers, or open separate windows. Changes save automatically on this device.');
  const renameLabel=el('label','','Current layout name');const renameInput=el('input','nc-search');renameInput.maxLength=48;renameInput.setAttribute('aria-label','Current layout name');
  const renameButton=button('Rename',()=>{const name=checkName(renameInput.value,currentLayout().id);if(!name)return;currentLayout().name=name;saveLayouts();refreshLayoutPicker();managerError.textContent='';toast('Layout renamed');});
  const newLabel=el('label','','New layout name');const newInput=el('input','nc-search');newInput.maxLength=48;newInput.placeholder='For example, Research';newInput.setAttribute('aria-label','New layout name');
  const managerError=el('p','nc-layout-error');managerError.setAttribute('role','alert');
  function checkName(value,excludeId){
    const name=value.trim();
    if(!name||name.length>48){managerError.textContent='Use a name between 1 and 48 characters.';return null;}
    if(savedLayouts.items.some(item=>item.id!==excludeId&&item.name.toLowerCase()===name.toLowerCase())){managerError.textContent='A layout already uses that name.';return null;}
    return name;
  }
  async function createLayout(duplicate){
    if(saving)return;
    const name=checkName(newInput.value);if(!name){newInput.focus();return;}
    persistLayout();
    const id='layout-'+(globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2));
    const blank=starterLayout();delete blank.root;
    const config=duplicate?clone(layout.saveLayout()):null;
    const item={id,name,seed:duplicate?currentLayout().seed:'blank',config};
    savedLayouts.items.push(item);savedLayouts.activeId=id;if(!await render())return;
    if(!duplicate){saving=true;layout.loadLayout(blank);saving=false;persistLayout();}
    layoutManager.close();toast(duplicate?'Layout duplicated':'Empty layout created. Add widgets to make it yours.');
  }
  const createActions=el('div','nc-layout-actions');createActions.append(button('Create empty',()=>createLayout(false)),button('Duplicate current',()=>createLayout(true)));
  let deleteConfirmed=false;
  const deleteLayout=button('Delete this layout',async()=>{
    if(saving||savedLayouts.items.length<2)return;
    if(!deleteConfirmed){deleteConfirmed=true;deleteLayout.textContent='Confirm delete “'+currentLayout().name+'”';return;}
    persistLayout();const removed=currentLayout(),remaining=savedLayouts.items.filter(item=>item.id!==removed.id);
    savedLayouts.activeId=remaining[0].id;if(!await render())return;
    savedLayouts.items=remaining;savedLayouts.deleted=[...(savedLayouts.deleted||[]),{...removed,deletedAt:new Date().toISOString()}].slice(-20);
    refreshLayoutPicker();saveLayouts();layoutManager.close();toast('Layout deleted');
  },'nc-action nc-layout-delete');
  layoutManager.append(managerHead,managerHelp,renameLabel,renameInput,renameButton,el('hr','nc-layout-divider'),newLabel,newInput,createActions,managerError,deleteLayout);document.body.append(layoutManager);
  layoutManager.onclick=event=>{if(event.target===layoutManager)layoutManager.close();};
  renameInput.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();renameButton.click();}};
  newInput.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();createLayout(false);}};
  function openLayoutManager(){
    if(saving)return;
    window.closeDD?.();
    renameInput.value=currentLayout().name;newInput.value='';managerError.textContent='';deleteConfirmed=false;
    deleteLayout.textContent='Delete this layout';deleteLayout.disabled=savedLayouts.items.length<2;deleteLayout.title=deleteLayout.disabled?'Keep at least one layout.':'';
    layoutManager.showModal();renameInput.focus();renameInput.select();
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
  const widgetsDropdown=$('dd-widgets');
  if(widgetsDropdown){widgetsDropdown.replaceChildren(el('div','dd-header','Open a widget'));for(const item of registry.values()){const entry=button(item.title,()=>{showWidget(item.id);window.closeDD?.();},'dd-item nc-widget-menu-item');entry.title=item.description;widgetsDropdown.append(entry);}widgetsDropdown.append(button('Browse widget library…',()=>{window.closeDD?.();openLibrary();},'dd-item nc-widget-menu-item'));}
  const viewDropdown=$('dd-view');if(viewDropdown){viewDropdown.replaceChildren(button('Manage saved layouts…',()=>{window.closeDD?.();openLayoutManager();},'dd-item nc-widget-menu-item'),button('Appearance…',()=>{window.closeDD?.();openAppearance();},'dd-item nc-widget-menu-item'),button('Reload interface',()=>location.reload(),'dd-item nc-widget-menu-item'));}
  for(const trigger of menuBar.querySelectorAll('[data-dd]')){trigger.setAttribute('aria-haspopup','true');trigger.setAttribute('aria-expanded','false');trigger.setAttribute('aria-controls','dd-'+trigger.dataset.dd);}

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
  const syncConnection=()=>{const online=typeof ws!=='undefined'&&ws?.readyState===1;const lifecycle=window.novaLifecycleState;const changing=!!lifecycle?.pending||!!lifecycle?.busy||['starting','stopping'].includes(lifecycle?.state);document.body.classList.toggle('nc-offline',!online);document.body.classList.toggle('nc-model-offline',!agentOnline.Nova);$('pb-auto').disabled=chatOnly||!online||changing;$('pb-wake').disabled=chatOnly||!online||changing;};
  window.addEventListener('nova:lifecycle',syncConnection);
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
  const emptyDock=el('div','nc-layout-empty');emptyDock.append(el('h2','','Make room for your work.'),el('p','','Open widgets, then drag their tabs and dividers to arrange your workspace.'),button('Browse widgets',openLibrary));workspace.append(emptyDock);
  const syncEmptyDock=()=>{emptyDock.hidden=!!layout.rootItem||layout.isSubWindow;};syncEmptyDock();
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
  layout.on('stateChanged',()=>{enhanceDockControls();syncEmptyDock();clearTimeout(layoutSaveTimer);layoutSaveTimer=setTimeout(persistLayout,250);});
  // Save popouts before the library tears down. Its unload closes child windows;
  // those must not try to bind components back into an already destroyed layout.
  window.addEventListener('beforeunload',()=>{
    persistLayout();
    if(!layout.isSubWindow)layout.layoutConfig.settings.popInOnClose=false;
  },{capture:true});
  new ResizeObserver(()=>layout.setSize(workspace.clientWidth,workspace.clientHeight)).observe(workspace);
  const appearanceButton=button('Appearance ▾',()=>openAppearance(),'menu-trigger');appearanceButton.dataset.dd='appearance';appearanceButton.setAttribute('aria-haspopup','true');appearanceButton.setAttribute('aria-controls','dd-appearance');appearanceButton.setAttribute('aria-expanded','false');actions.append(appearanceButton);
  const customize=el('div','dropdown nc-appearance-menu');customize.id='dd-appearance';customize.setAttribute('aria-label','Appearance');customize.close=()=>window.closeDD?.();
  function openAppearance(){window.toggleDD?.('appearance',appearanceButton);}
  const ch=el('header','nc-library-header');ch.append(el('h2','','Appearance'),button('Close',()=>customize.close()));customize.append(ch,el('p','nc-custom-help','Drag widget tabs to reorder, stack, or split. Drag the dividers to resize. Use a widget’s popout control to move it into its own window. Each named layout remembers its arrangement.'));
  const density=el('select','nc-search');density.setAttribute('aria-label','Interface density');for(const [v,t] of [['comfortable','Comfortable'],['compact','Compact']]){const o=el('option','',t);o.value=v;density.append(o);}
  const accent=el('input','nc-search');accent.type='color';accent.setAttribute('aria-label','Accent color');
  let appearance={density:'comfortable',accent:'#b5a0f6'};try{appearance={...appearance,...JSON.parse(localStorage.getItem('nova.controller.appearance')||'{}')};}catch(_){}
  function style(){document.body.dataset.density=appearance.density;document.body.style.setProperty('--nova',appearance.accent);try{localStorage.setItem('nova.controller.appearance',JSON.stringify(appearance));}catch(_){}}
  density.value=appearance.density;accent.value=appearance.accent;density.onchange=()=>{appearance.density=density.value;style();};accent.oninput=()=>{appearance.accent=accent.value;style();};style();
  customize.append(el('label','','Density'),density,el('label','','Accent'),accent,button('Reset this layout to a starter arrangement',async()=>{if(saving)return;persistLayout();const item=currentLayout();savedLayouts.deleted=[...(savedLayouts.deleted||[]),{...clone(item),deletedAt:new Date().toISOString(),reason:'before-reset'}].slice(-20);item.config=null;item.seed='together';loadedLayoutId=null;if(await render())persistLayout();customize.close();}));document.body.append(customize);
  render();
  if(!layout.isSubWindow)window.initNovaUpdaterNotifications?.({showWidget});
  const chatOnlyReason='Nova is off. Use Start Nova in Conversation to enable her, or use Collaboration while she stays off.';
  function applyChatOnly(enabled){
    chatOnly=enabled===true;document.body.dataset.chatOnly=String(chatOnly);modeStatus.hidden=!chatOnly;
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
    syncConnection();if(!layout.isSubWindow&&!hadSavedArrangement)showWidget('collaboration');
  }
  fetch('/api/version',{cache:'no-store'}).then(response=>response.ok?response.json():null).then(version=>{if(version?.chat_only)applyChatOnly(true);}).catch(()=>{});

})();

