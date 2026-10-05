// @nova: Verify growing audited reply rendering, ordered segment deduplication and aggregate terminal reconciliation without a browser or Nova.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
const range = (start,end) => html.slice(html.indexOf(start),html.indexOf(end,html.indexOf(start)));
const source = range('const completedSegmentReplies', 'function appendThink(')
  + range('function _cleanChatText(', 'function copyMsgText(')
  + range('function appendResponseAttribution(', 'function startStream(');
function fixture() {
  const nodes=new Map();let created=0;
  const context={streamBufs:{},isActiveConversationFrame:d=>d.conversation_id==null||d.conversation_id==='A',
    renderMD:text=>text,hideTyping(){},addCtxChars(){},scrollBot(){},_sweepEmptyNova(){},
    appendMsg(){throw new Error('A second reply bubble must not be created');},
    document:{createElement:()=>({style:{},setAttribute(){}}),getElementById:id=>nodes.get(id)}};
  context.startStream=(author,id)=>{
    created++;
    const header={appendChild:child=>{wrap.progress=child;}};
    const wrap={querySelector(selector){return selector==='.msg-header'?header:selector==='.reply-progress'?this.progress:null;}};
    context.streamBufs[id]={w:wrap,st:{},text:'',think:''};nodes.set('msg-'+id,wrap);
  };
  vm.createContext(context);vm.runInContext(source,context);
  return {context,nodes,created:()=>created};
}
const part=(index,extra={})=>({id:'m',author:'Nova',run_id:'run',turn_id:'run',conversation_id:'A',
  delivery:'delivered',segment_index:index,content:`Part ${index}.`,audit:{status:'INCOMPLETE',reason:'Not approved'},...extra});
test('parts grow one reply before final, duplicates do not repeat, terminal does not create another bubble',()=>{
  const f=fixture();f.context.appendDeliveredSegment(part(1));
  const buffer=f.context.streamBufs.m;
  assert.equal(buffer.st.innerHTML,'Part 1.');
  assert.match(buffer.w.progress.textContent,/Reply in progress.*Audit INCOMPLETE/);
  f.context.appendDeliveredSegment(part(1));f.context.appendDeliveredSegment(part(3));
  assert.equal(buffer.st.innerHTML,'Part 1.');
  f.context.appendDeliveredSegment(part(2));assert.equal(buffer.st.innerHTML,'Part 1.\n\nPart 2.');
  f.context.finalizeMsg('m','Part 1.\n\nPart 2.','Nova');
  f.context.finishSegmentReply({id:'m',segment_count:2,delivery:'delivered'});
  f.context.appendDeliveredSegment(part(3));
  assert.equal(f.created(),1);assert.equal(f.context.streamBufs.m,undefined);
  assert.match(buffer.w.progress.textContent,/Turn complete.*2 delivered parts/);
});
test('wrong session, run, turn, delivery and indices cannot mutate delivered text; cancellation retains delivered parts',()=>{
  const f=fixture();
  for(const extra of [{conversation_id:'B'},{turn_id:'wrong'},{delivery:'error'},{segment_index:true},{segment_index:0}])f.context.appendDeliveredSegment(part(1,extra));
  assert.equal(f.created(),0);
  f.context.appendDeliveredSegment(part(1));const buffer=f.context.streamBufs.m;
  f.context.appendDeliveredSegment(part(2,{run_id:'other',turn_id:'other'}));
  assert.equal(buffer.st.innerHTML,'Part 1.');
  f.context.finalizeMsg('m','','Nova');f.context.finishSegmentReply({id:'m',segment_count:1,delivery:'cancelled'});
  assert.equal(buffer.st.innerHTML,'Part 1.');assert.match(buffer.w.progress.textContent,/cancelled/);
});

test('reloaded segments retain explicit audit and part attribution as text',()=>{
  const f=fixture();f.context.startStream('Nova','saved');
  f.context.appendResponseAttribution(f.nodes.get('msg-saved'),{segment_index:2,run_id:'run',input_revision:1,
    audit:{status:'INCOMPLETE',reason:'<img src=x> is unverified'}});
  const label=f.nodes.get('msg-saved').progress;
  assert.equal(label.textContent,'Delivered part 2 · Audit INCOMPLETE');
  assert.match(label.title,/Input revision: 1/);
  assert.equal(label.innerHTML,undefined);
  assert.match(html,/case 'history':\s+appendMsg\(d.author, d.content, d.id, d.images, d.timestamp, d.response_metadata\)/);
  assert.match(html,/hist.forEach\(m=>appendMsg\(m.author,m.content,m.id,m.images,m.timestamp,m.response_metadata\)\)/);
});
