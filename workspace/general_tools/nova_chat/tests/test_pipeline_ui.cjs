/* @nova: Verify Pipeline tool progress, honest audit outcomes and same-timestamp polling with isolated events only. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
const start=source.indexOf('const _PL_META='),end=source.indexOf('const _AICONS=',start);
assert.ok(start>=0&&end>start);
const clone=value=>JSON.parse(JSON.stringify(value));
const nodes=new Map();
let feedWrites=0,fetchCount=0,events=[],failure=null,deferred=null;
for(const name of ['feed','now','tools','pass','incomplete','concern','answered','over','unres','hold','err'])nodes.set('pl-'+name,{textContent:'',_html:'',set innerHTML(value){this._html=value;feedWrites++;},get innerHTML(){return this._html;}});
const context={
  window:{novaWidgetVisible:()=>true},activePanel:'pipeline',
  esc:value=>String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),
  document:{getElementById:id=>nodes.get(id),querySelector:()=>null},
  setInterval:()=>1,setTimeout:()=>1,
  fetch:async()=>{fetchCount++;if(deferred)await deferred;if(failure)throw Error(failure);return {ok:true,json:async()=>({events:clone(events)})};},
  Date,
};
vm.createContext(context);
vm.runInContext(source.slice(start,end)+`\nthis.test={normalize:_plNormalizeEvent,status:_plToolStatus,steps:_plToolSteps,rows:_plToolRows,groups:_plGroups,render:_plRenderGroup,pass:_plExplicitPass,poll:plPoll,open:turn=>{_plOpen[turn]=true;},stats:()=>({..._PLSTATS})};`,context);
const api=context.test;
const event=(stage,extra={})=>({ts:'2026-10-04T14:13:51',turn:'turn1',run_id:'run1',stage,operation_id:'call1',tool:'computer_exec',environment:'guest',...extra});
const html=()=>nodes.get('pl-feed').innerHTML;
(async()=>{
let cases=0;
assert.equal(api.pass('PASS'),true);assert.equal(api.pass('2. PASS.'),true);assert.equal(api.pass('1. PASS'),true);assert.equal(api.pass('4) PASS!'),true);assert.equal(api.pass('```text\nPASS\n```'),true);
for(const invalid of ['','```plain\nPASS\n```','PASS because it seems fine','{"tool":"read_file"}','PASS\nCONCERN: actually no','```json\n"PASS"\n```'])assert.equal(api.pass(invalid),false,invalid);cases++;

const legacy=event('witness_pass',{verdict:'```json\n{"tool":"read_file"}\n```'});
assert.equal(api.normalize(legacy).stage,'witness_incomplete');assert.equal(legacy.stage,'witness_pass','Historical record is not mutated');
let rendered=api.render({turn:'turn1',events:[legacy]});assert.match(rendered,/AUDIT INCOMPLETE/);assert.ok(!rendered.includes('pl-badge ok'));assert.match(rendered,/without an explicit PASS/);cases++;

rendered=api.render({turn:'turn1',events:[event('witness_error',{reason:'Inference failed'})]});assert.match(rendered,/AUDIT ERROR/);assert.match(rendered,/Inference failed/);assert.match(rendered,/pl-badge err/);cases++;
rendered=api.render({turn:'turn1',events:[event('future_stage',{detail:'A new kind of observation'})]});assert.match(rendered,/pl-badge neutral/);assert.ok(!rendered.includes('pl-turn ok'));cases++;

const started=event('tool_started',{status:'running'});
rendered=api.render({turn:'turn1',events:[started]});assert.match(rendered,/Running · computer_exec/);assert.match(rendered,/aria-label="Tool progress"/);assert.match(rendered,/Guest/);assert.match(rendered,/awaiting a completion event/);assert.equal(api.steps([started]).length,1);cases++;
const completed=event('tool_completed',{status:'succeeded',ok:true,duration_ms:1250});
const paired=api.steps([started,completed]);assert.equal(paired.length,1);assert.equal(paired[0].event.stage,'tool_completed');
rendered=api.rows([started,completed]);assert.match(rendered,/Completed/);assert.match(rendered,/1\.3 s/);assert.equal((rendered.match(/<li /g)||[]).length,1);assert.ok(!rendered.includes('Running'));cases++;

for(const [status,label,color] of [['failed','Failed','err'],['partial','Partial','held'],['refused','Refused','held'],['cancelled','Cancelled','held'],['unexpected','Outcome unknown','neutral']]){
 const result=api.status(event('tool_completed',{status}));assert.equal(result.label,label);assert.equal(result.color,color);
}
assert.equal(api.status(event('tool_failed',{status:'succeeded',ok:false})).color,'err','Failure event cannot be made green by contradictory status');cases++;

const cancelling=event('tool_failed',{status:'cancellation_requested',detail:'Stop requested'});
assert.equal(api.status(cancelling).color,'neutral');
rendered=api.render({turn:'turn1',events:[started,cancelling]});
assert.match(rendered,/Cancellation requested/);assert.match(rendered,/worker cleanup may still be pending/);
assert.ok(!rendered.includes('Cancelled'));assert.ok(!rendered.includes('pl-badge err'));
assert.equal(api.steps([started,cancelling]).length,1);
assert.equal(api.steps([started,cancelling,completed])[0].event.stage,'tool_completed');cases++;

const second=event('tool_started',{operation_id:'call2',tool:'computer_look'});
assert.equal(api.steps([started,completed,second]).length,2,'Repeated tools retain distinct operation IDs');
assert.equal(api.steps([completed,started])[0].event.stage,'tool_completed','Late duplicate start does not resurrect a completed call');cases++;

rendered=api.render({turn:'bad\'"<id>',events:[event('tool_failed',{tool:'<img src=x onerror=alert(1)>',status:'failed',detail:'bad "quoted" <script>'})]});
assert.ok(!rendered.includes('<img'));assert.ok(!rendered.includes('<script>'));assert.match(rendered,/&lt;img/);assert.match(rendered,/data-pl-turn="bad&#39;&quot;&lt;id&gt;"/);assert.match(rendered,/onclick="plToggle\(this.dataset.plTurn\)"/);cases++;

const grouped=api.groups([started,event('witness_check',{turn:'turn2'}),completed]);
assert.equal(grouped[0].turn,'turn1','Latest update brings active turn above newer but idle turns');
const many=Array.from({length:70},(_,i)=>event('witness_check',{turn:'t'+i}));assert.equal(api.groups(many).length,60);cases++;

events=[started];await api.poll();assert.match(html(),/Running/);assert.equal(nodes.get('pl-tools').textContent,1);
const firstWrites=feedWrites;events=[completed];await api.poll();
assert.ok(feedWrites>firstWrites,'Equal row count and timestamp still redraw a different outcome');assert.match(html(),/Completed/);assert.ok(!html().includes('Running'));
const stableWrites=feedWrites;await api.poll();assert.equal(feedWrites,stableWrites,'Unchanged settled history does not rebuild the DOM');cases++;

events=[started,completed,event('witness_incomplete',{reason:'Read limit reached'})];await api.poll();
assert.equal(nodes.get('pl-tools').textContent,1);assert.equal(nodes.get('pl-incomplete').textContent,1);assert.equal(nodes.get('pl-pass').textContent,0);
assert.match(html(),/Read limit reached/);assert.match(html(),/Completed/);assert.match(html(),/AUDIT INCOMPLETE/);cases++;

events=[legacy];await api.poll();assert.equal(nodes.get('pl-pass').textContent,0);assert.equal(nodes.get('pl-incomplete').textContent,1,'Legacy false success is excluded from PASS tally');cases++;

events=[event('witness_pass',{verdict:'PASS'})];await api.poll();assert.equal(nodes.get('pl-pass').textContent,1);assert.match(html(),/WITNESS: PASS/);cases++;

failure='Network unavailable';const beforeError=html();await api.poll();assert.equal(html(),beforeError);assert.match(nodes.get('pl-now').textContent,/last received events retained/);failure=null;cases++;

let release;deferred=new Promise(resolve=>{release=resolve;});const beforeFetch=fetchCount;
const pending=api.poll();await api.poll();assert.equal(fetchCount,beforeFetch+1,'Only one poll is in flight');release();await pending;deferred=null;cases++;

events=[started];await api.poll();const runningWrites=feedWrites;await api.poll();assert.ok(feedWrites>runningWrites,'Elapsed running time refreshes while events remain unchanged');cases++;

api.open('turn1');rendered=api.render({turn:'turn1',events:[legacy]});assert.match(rendered,/raw audit output \(not a verdict\)/);assert.match(rendered,/read_file/);assert.match(rendered,/aria-expanded="true"/);cases++;

events=[];await api.poll();assert.match(html(),/No Pipeline events yet/);assert.equal(nodes.get('pl-tools').textContent,0);cases++;
console.log('Pipeline UI: '+cases+' isolated scenarios passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
