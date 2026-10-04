/* @nova: Verify manual-only dock persistence, session undo/redo, saved-layout loading and widget presence with isolated storage fixtures. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/workspace.js'),'utf8');
function sourceBetween(start,end){
  const first=source.indexOf(start),last=source.indexOf(end,first);
  assert.ok(first>=0&&last>first,'Expected live implementation boundary: '+start);
  return source.slice(first,last);
}
const key='nova.controller.layouts.v2',jsonClone=value=>JSON.parse(JSON.stringify(value));
const implementation=[
  sourceBetween('  function setLayoutSaveStatus(',"  document.body.classList.add"),
  sourceBetween('  function snapshotKey(', '  function refreshLayoutPicker('),
  sourceBetween('  function layoutConfig(', '  const layoutManager='),
  sourceBetween('  function discardLayoutBeforeUnload(',"  window.addEventListener('beforeunload'"),
].join('\n');
const buttonBinding=sourceBetween('  const layoutSave=button(', '  layoutSave.id=');
function fixture(){
  const f={storageFails:false,captureFails:false,writes:0,toasts:[],timers:new Map()};
  const config={root:{type:'row',content:[{type:'stack',size:38,content:[{componentState:{id:'chat'}}]},{type:'stack',size:62,content:[{componentState:{id:'files'}}]}]},openPopouts:[],settings:{popInOnClose:true}};
  const collection={version:2,activeId:'work',deleted:[{id:'old',name:'Recovery',config:{root:{type:'stack'}}}],items:[{id:'work',name:'My work',config:jsonClone(config)},{id:'other',name:'Other layout',config:{root:{type:'stack',size:25},openPopouts:[],settings:{popInOnClose:true}}}]};
  f.current=jsonClone(config);f.storage=new Map([[key,JSON.stringify(collection)]]);
  let timerId=0;
  const control=()=>({disabled:false});
  const context={
    clone:jsonClone,window:{},savedLayouts:collection,LAYOUTS_KEY:key,storageWarning:false,
    loadedLayoutId:'work',saving:false,closing:false,layoutGesture:false,layoutChangeTimer:undefined,
    layoutHistory:[],layoutHistoryIndex:-1,savedBaseline:null,
    layoutSave:control(),layoutLoad:control(),layoutRevert:control(),layoutUndo:control(),layoutRedo:control(),layoutManage:control(),layoutSelect:{value:'work',disabled:false},
    layoutSaved:{textContent:'Saved',dataset:{},title:''},
    layout:{isSubWindow:false,openPopouts:[],layoutConfig:{settings:{popInOnClose:true}},saveLayout(){if(f.captureFails)throw Error('Capture failed');return jsonClone(f.current);},loadLayout(config){f.current=jsonClone(config);},setSize(){},closeAllOpenPopouts(){}},
    currentLayout:()=>context.savedLayouts.items.find(item=>item.id===context.savedLayouts.activeId),
    refreshLayoutPicker:()=>{context.layoutSelect.value=context.savedLayouts.activeId;},
    workspace:{clientWidth:1200,clientHeight:720},syncEmptyDock(){},syncWidgetChecks(){},
    NovaDock:{LayoutConfig:{fromResolved:jsonClone}},starterLayout:()=>jsonClone(config),
    localStorage:{setItem(k,v){if(f.storageFails)throw Error('Quota full');f.storage.set(k,v);f.writes++;}},
    toast:message=>f.toasts.push(message),console:{warn(){}},Date,
    setTimeout:(callback,delay)=>{f.timers.set(++timerId,{callback,delay});return timerId;},clearTimeout:id=>f.timers.delete(id),
    button:(text,action)=>({textContent:text,click:action}),
  };
  vm.createContext(context);
  vm.runInContext(implementation,context);
  vm.runInContext(buttonBinding+'\nthis.saveButton=layoutSave;',context);
  context.resetLayoutHistory();
  f.context=context;
  f.saved=()=>JSON.parse(f.storage.get(key));
  f.flush=()=>{const pending=[...f.timers.values()];f.timers.clear();for(const item of pending)item.callback();};
  f.edit=size=>{f.current.root.content[0].size=size;f.current.root.content[1].size=100-size;context.queueLayoutChange();};
  return f;
}
(async()=>{
let cases=0;
const draft=fixture(),original=draft.storage.get(key);
draft.edit(45);draft.flush();
assert.equal(draft.writes,0,'Settled layout changes never write storage');
assert.equal(draft.context.layoutSaved.textContent,'Unsaved changes');
assert.equal(draft.context.layoutUndo.disabled,false);
assert.equal(draft.context.layoutRedo.disabled,true);
draft.context.discardLayoutBeforeUnload();
assert.equal(draft.storage.get(key),original,'Closing/reloading discards unsaved changes');
assert.equal(draft.context.layout.layoutConfig.settings.popInOnClose,false);
draft.context.queueLayoutChange();assert.equal(draft.timers.size,0);
assert.equal(draft.context.persistLayout(),false,'Implicit persist call is forbidden');cases++;

const save=fixture(),unrelated=JSON.stringify(save.saved().items[1]),recovery=JSON.stringify(save.saved().deleted);
save.edit(43);
save.current.openPopouts=[{root:{componentState:{id:'monitor'}},window:{width:720,height:480,left:20,top:30}}];
assert.equal(save.context.saveButton.click(),true);
assert.deepEqual(save.saved().items[0].config,save.current,'Explicit Save captures CURRENT sizes and popout geometry');
assert.equal(JSON.stringify(save.saved().items[1]),unrelated);assert.equal(JSON.stringify(save.saved().deleted),recovery);
assert.equal(save.context.layoutSaved.textContent,'Saved');assert.equal(save.context.layoutRevert.disabled,true);assert.equal(save.timers.size,0);cases++;

const failure=fixture(),prior=failure.storage.get(key),priorBaseline=JSON.stringify(failure.context.savedBaseline);
failure.edit(48);failure.storageFails=true;
assert.equal(failure.context.saveButton.click(),false);
assert.equal(failure.storage.get(key),prior);assert.equal(JSON.stringify(failure.context.savedBaseline),priorBaseline);
assert.equal(failure.context.savedLayouts.items[0].config.root.content[0].size,38,'Failed write cannot silently replace saved in-memory baseline');
assert.equal(failure.context.layoutSaved.textContent,'Save failed');
failure.storageFails=false;assert.equal(failure.context.saveButton.click(),true);
failure.captureFails=true;assert.equal(failure.context.saveButton.click(),false);assert.equal(failure.context.layoutSaved.textContent,'Save failed');cases++;

const history=fixture();
history.edit(40);history.edit(42);history.edit(44);history.flush();
assert.equal(history.context.layoutHistory.length,2,'Debounce coalesces resize state updates');
await history.context.stepLayoutHistory(-1);assert.equal(history.current.root.content[0].size,38);assert.equal(history.context.layoutSaved.textContent,'Saved');
assert.equal(history.context.layoutRedo.disabled,false);
await history.context.stepLayoutHistory(1);assert.equal(history.current.root.content[0].size,44);assert.equal(history.context.layoutSaved.textContent,'Unsaved changes');
assert.equal(history.writes,0,'Undo/Redo never persist drafts');cases++;
await history.context.stepLayoutHistory(-1);history.edit(51);history.flush();
assert.equal(history.context.layoutRedo.disabled,true);assert.equal(await history.context.stepLayoutHistory(1),false);
assert.equal(history.current.root.content[0].size,51);cases++;

const revert=fixture();revert.edit(46);revert.flush();revert.context.layoutSelect.value='other';
await revert.context.revertLayout();assert.equal(revert.current.root.content[0].size,38);
assert.equal(revert.context.loadedLayoutId,'work','Revert uses active baseline, not pending dropdown target');
assert.equal(revert.context.layoutSelect.value,'other');assert.equal(revert.writes,0);
await revert.context.stepLayoutHistory(-1);assert.equal(revert.current.root.content[0].size,46,'Revert itself is undoable');cases++;

const load=fixture(),beforeLoad=load.storage.get(key);load.edit(49);load.flush();load.context.layoutSelect.value='other';
assert.equal(load.context.loadedLayoutId,'work');assert.equal(load.current.root.content[0].size,49,'Choosing a name does not load');
assert.equal(await load.context.loadSelectedLayout(),true);assert.equal(load.current.root.size,25);
assert.equal(load.storage.get(key),beforeLoad,'Load never saves the departing dirty layout or active selection');
assert.equal(load.context.layoutUndo.disabled,true);assert.equal(load.context.layoutRedo.disabled,true,'Load starts a new session history');
load.context.layoutSelect.value='work';await load.context.loadSelectedLayout();assert.equal(load.current.root.content[0].size,38);
load.edit(52);load.flush();await load.context.loadSelectedLayout();assert.equal(load.current.root.content[0].size,38,'Load same layout discards current draft');cases++;

const afterSave=fixture();afterSave.edit(47);afterSave.context.saveButton.click();await afterSave.context.stepLayoutHistory(-1);
assert.equal(afterSave.current.root.content[0].size,38);assert.equal(afterSave.context.layoutSaved.textContent,'Unsaved changes','Undo after Save compares against the new saved baseline');
await afterSave.context.revertLayout();assert.equal(afterSave.current.root.content[0].size,47);assert.equal(afterSave.context.layoutSaved.textContent,'Saved');cases++;

const guarded=fixture();guarded.context.saving=true;const writes=guarded.writes;
assert.equal(guarded.context.saveButton.click(),false);guarded.context.saving=false;guarded.context.layout.isSubWindow=true;
guarded.context.queueLayoutChange();assert.equal(guarded.timers.size,0);assert.equal(guarded.context.saveButton.click(),false);assert.equal(guarded.writes,writes);cases++;

const gesture=fixture();gesture.context.layoutGesture=true;gesture.edit(40);gesture.edit(43);assert.equal(gesture.timers.size,0,'Dragging does not create intermediate undo steps');
gesture.context.layoutGesture=false;gesture.context.queueLayoutChange();gesture.flush();assert.equal(gesture.context.layoutHistory.length,2);cases++;

const historyBound=fixture();for(let i=0;i<140;i++){historyBound.edit(i+1);historyBound.flush();}assert.equal(historyBound.context.layoutHistory.length,100);assert.equal(historyBound.context.layoutHistoryIndex,99);cases++;

const popout=fixture();popout.current.openPopouts=[{root:{type:'stack',content:[{componentState:{id:'monitor'}}]}}];popout.context.saveButton.click();
popout.current.openPopouts=[];popout.context.recordLayoutChange();await popout.context.revertLayout();
assert.deepEqual(popout.current.openPopouts,[]);assert.equal(popout.current.root.content.at(-1).content[0].componentState.id,'monitor');
assert.equal(popout.context.layoutSaved.textContent,'Saved','Revert safely reclaims saved popouts and reports the restored baseline');cases++;


const failedLoad=fixture();failedLoad.edit(53);failedLoad.flush();failedLoad.context.layoutSelect.value='other';
failedLoad.context.layout.loadLayout=()=>{throw Error('Invalid layout');};
assert.equal(await failedLoad.context.loadSelectedLayout(),false);
assert.equal(failedLoad.context.savedLayouts.activeId,'work');assert.equal(failedLoad.context.loadedLayoutId,'work');
assert.equal(failedLoad.context.layoutSaved.textContent,'Unsaved changes','Failed Load cannot label the dirty current arrangement Saved');assert.equal(failedLoad.writes,0);cases++;

const asyncPopout=fixture();asyncPopout.edit(55);asyncPopout.flush();asyncPopout.context.layoutSelect.value='other';
const popupWindow={closed:false};asyncPopout.context.layout.openPopouts=[{getWindow:()=>popupWindow}];
const pendingLoad=asyncPopout.context.loadSelectedLayout();assert.equal(asyncPopout.context.saving,true);
assert.equal(asyncPopout.context.saveButton.click(),false,'Save during asynchronous popout closure cannot capture a half-loaded layout');
assert.equal(asyncPopout.writes,0);popupWindow.closed=true;asyncPopout.flush();await pendingLoad;
assert.equal(asyncPopout.context.loadedLayoutId,'other');assert.equal(asyncPopout.current.root.size,25);assert.equal(asyncPopout.writes,0);cases++;

const deleting=fixture();deleting.context.deleteConfirmed=true;deleting.context.layoutManager={close(){}};deleting.storageFails=true;
vm.runInContext(sourceBetween('  const deleteLayout=button(', '  layoutManager.append(')+'\nthis.deleteButton=deleteLayout;',deleting.context);
await deleting.context.deleteButton.click();
assert.equal(deleting.context.savedLayouts.items.length,2,'Failed delete retains both saved layouts');
assert.equal(deleting.context.savedLayouts.activeId,deleting.context.loadedLayoutId,'Failed delete keeps picker and loaded layout aligned');
assert.equal(deleting.context.layoutSaved.textContent,'Save failed');cases++;

const rename=fixture();rename.edit(54);rename.flush();rename.context.renameInput={value:'Renamed'};
rename.context.checkName=value=>value;rename.context.managerError={textContent:''};
vm.runInContext(sourceBetween('  const renameButton=button(', '  const newLabel=')+'\nthis.renameButton=renameButton;',rename.context);
rename.context.renameButton.click();assert.equal(rename.saved().items[0].name,'Renamed');
assert.equal(rename.saved().items[0].config.root.content[0].size,38,'Rename never captures unsaved widget changes');
assert.equal(rename.context.layoutSaved.textContent,'Unsaved changes');cases++;

const duplicate=fixture();duplicate.edit(56);duplicate.flush();duplicate.context.newInput={value:'Copy',focus(){}};
duplicate.context.checkName=value=>value;duplicate.context.layoutManager={close(){}};
duplicate.context.NovaDock.LayoutConfig.resolve=jsonClone;
vm.runInContext(sourceBetween('  async function createLayout(', '  const createActions='),duplicate.context);
await duplicate.context.createLayout(true);
assert.equal(duplicate.saved().items[0].config.root.content[0].size,38,'Duplicate does not save departing draft into original');
assert.equal(duplicate.saved().items[2].config.root.content[0].size,56,'Explicit duplicate keeps the current draft under its new name');cases++;

const referenceSource=sourceBetween('  function screenshotLayout(', '  function snapshotKey(');
const migration={clone:jsonClone,Date,NovaDock:{LayoutConfig:{resolve:jsonClone}},starterLayout:()=>({settings:{popInOnClose:true}}),stack:(ids,extra)=>({type:'stack',content:ids.map(id=>({type:'component',componentState:{id}})),...extra})};
vm.createContext(migration);vm.runInContext(referenceSource,migration);
const priorLayouts={version:2,activeId:'mine',items:[{id:'mine',name:'Default Workspace',config:{root:{id:'existing-user-layout'}}}],deleted:[{reason:'old-recovery'}]};
assert.equal(migration.ensureScreenshotReference(priorLayouts),true);
assert.equal(priorLayouts.activeId,'mine');assert.equal(priorLayouts.items[0].config.root.id,'existing-user-layout');assert.equal(priorLayouts.deleted.length,1);
const recovered=priorLayouts.items[1];assert.equal(recovered.name,'Screenshot reference');
assert.deepEqual(recovered.config.root.content.map(item=>item.size),['24%','44%','32%']);
const [left,middle,right]=recovered.config.root.content;
assert.deepEqual(left.content.map(item=>item.activeItemIndex),[1,2]);assert.equal(middle.activeItemIndex,5);assert.deepEqual(right.content.map(item=>item.activeItemIndex),[2,0]);
assert.deepEqual(right.content.map(item=>item.size),['60%','40%']);
const migrated=JSON.stringify(priorLayouts);assert.equal(migration.ensureScreenshotReference(priorLayouts),false);assert.equal(JSON.stringify(priorLayouts),migrated,'Screenshot reference is never recreated or auto-selected after subsequent edits');cases++;

assert.ok(!/persistLayout\(\);/.test(source),'No implicit persist calls remain');
assert.ok(!source.includes('setTimeout(persistLayout'),'No autosave timer remains');
assert.ok(source.includes("layoutSelect.onchange=()=>updateLayoutControls();"));
assert.ok(source.includes("window.addEventListener('beforeunload',discardLayoutBeforeUnload"));cases++;

const choiceSource = sourceBetween(
  "  function openWidgetIds(",
  "  function widgetChoice(",
);
const choice = (id) => ({
  dataset: { widgetChoice: id },
  check: { textContent: "" },
  attrs: {},
  setAttribute(k, v) {
    this.attrs[k] = v;
  },
  querySelector() {
    return this.check;
  },
});
const menu = [choice("chat"), choice("monitor"), choice("files")],
  library = [choice("monitor"), choice("files")];
let popoutClosed = false;
const choices = {
  containers: new Map([["chat", {}]]),
  layout: {
    saveLayout: () => ({
      root: { content: [{ componentState: { id: "chat" } }] },
    }),
    openPopouts: [
      {
        getWindow: () => ({ closed: popoutClosed }),
        getGlInstance: () => ({
          saveLayout: () => ({
            root: { content: [{ componentState: { id: "monitor" } }] },
          }),
        }),
      },
    ],
  },
  registry: new Map(
    ["chat", "monitor", "files"].map((id) => [
      id,
      { id, title: id, description: id + " description" },
    ]),
  ),
  widgetsDropdown: { querySelectorAll: () => menu },
  results: { querySelectorAll: () => library },
};
vm.createContext(choices);
vm.runInContext(choiceSource, choices);
choices.syncWidgetChecks();
assert.equal(menu[0].check.textContent, "✓");
assert.equal(menu[1].check.textContent, "✓");
assert.equal(
  library[0].check.textContent,
  "✓",
  "Popout is marked open in the library too",
);
assert.equal(menu[2].check.textContent, "");
assert.equal(menu[2].dataset.open, "false");
assert.match(menu[1].attrs["aria-label"], /open\. Focus widget/);
assert.match(menu[2].attrs["aria-label"], /closed\. Open widget/);
popoutClosed = true;
choices.syncWidgetChecks();
assert.equal(menu[1].check.textContent, "");
assert.equal(library[0].check.textContent, "");
choices.containers = new Map([["files", {}]]);
choices.layout.saveLayout = () => ({
  root: { componentState: { id: "files" } },
});
choices.syncWidgetChecks();
assert.equal(menu[0].check.textContent, "");
assert.equal(
  menu[2].check.textContent,
  "✓",
  "Checks follow a newly selected layout",
);

let focused = 0,
  opened = 0;
const focusContext = {
  registry: new Map([
    ["chat", { title: "Conversation" }],
    ["monitor", { title: "System" }],
  ]),
  layout: {
    openPopouts: [],
    addComponent() {
      opened++;
    },
    maximisedStack: null,
  },
  saving: false,
  containers: new Map([
    [
      "chat",
      {
        focus() {
          focused++;
        },
      },
    ],
  ]),
  refresh() {},
  library: { open: false },
};
vm.createContext(focusContext);
vm.runInContext(
  sourceBetween("  function showWidget(", "  window.ensureWidget="),
  focusContext,
);
focusContext.showWidget("chat");
assert.equal(focused, 1);
assert.equal(opened, 0);
focusContext.layout.openPopouts = [
  {
    getGlInstance: () => ({
      saveLayout: () => ({ root: { componentState: { id: "monitor" } } }),
    }),
    getWindow: () => ({
      focus() {
        focused++;
      },
    }),
  },
];
focusContext.showWidget("monitor");
assert.equal(focused, 2);
assert.equal(
  opened,
  0,
  "Open-widget clicks focus existing dock/popout instead of duplicating or closing it",
);

console.log(`Layout UI: ${cases+2} scenarios passed (manual save/discard, failure recovery, Undo/Redo/Revert/Load, drag coalescing, bounded history, safe popouts, screenshot reference, and widget checks/focus).`);
})().catch(error=>{console.error(error);process.exitCode=1;});
