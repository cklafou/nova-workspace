// @nova: Verify production Conversation frame routing excludes other sessions while retaining global Thoughts and legacy frames.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const source = html.slice(html.indexOf('function isActiveConversationFrame(d)'), html.indexOf('/* ', html.indexOf('function handle(d)')));
function fixture() {
  const calls = [];
  const context = {activeId: 'session-A'};
  for (const name of ['appendMsg','showTyping','appendToken','appendThink','finalizeMsg','hideTyping','liveThinkStart','liveThinkAppend','liveThinkEnd','appendDeliveredSegment','finishSegmentReply']) {
    context[name] = (...args) => calls.push({name, args});
  }
  vm.createContext(context);
  vm.runInContext(source, context);
  return {context, calls};
}
function response(context, conversation_id) {
  for (const type of ['user_message','message_start','message_context','message_segment','think_start','think_token','think_end','token','message_end']) {
    context.handle({type, conversation_id, author: 'Nova', id: 'response-1', token: 'piece', content: 'final'});
  }
}
test('late frames from previous session never create or finalize selected-session chat bubbles', () => {
  const {context,calls}=fixture();
  context.handle({type:'message_start',conversation_id:'session-A',author:'Nova'});
  context.activeId='session-B';
  calls.length=0;
  response(context,'session-A');
  assert.deepEqual(calls.map(call=>call.name),['liveThinkStart','liveThinkAppend','liveThinkEnd']);
  assert.equal(context.isActiveConversationFrame({conversation_id:'session-A'}),false);
});
test('matching session and untagged legacy frames still render, including inline thinking', () => {
  const {context,calls}=fixture();
  const expected=['appendMsg','showTyping','appendDeliveredSegment','liveThinkStart','appendThink','liveThinkAppend','liveThinkEnd','appendToken','finalizeMsg','finishSegmentReply','hideTyping'];
  response(context,'session-A');
  assert.deepEqual(calls.map(call=>call.name),expected);
  calls.length=0;
  response(context,undefined);
  assert.deepEqual(calls.map(call=>call.name),expected);
});
