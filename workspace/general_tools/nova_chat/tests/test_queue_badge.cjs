// @nova: Verify queued versus active-turn follow-up labels using the production badge renderer without Nova or a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const source = html.match(/function showQueueBadge\(count,mode\)\{[\s\S]*?\n\}/)[0];
function fixture() {
  const badge = {attributes: {}, classList: {add() {}}, setAttribute(key,value) {this.attributes[key]=value;}};
  const count = {}, label = {};
  const nodes = {'queue-btn':badge, 'queue-btn-count':count, 'queue-btn-label':label};
  const context = {document: {getElementById: id => nodes[id]}};
  vm.createContext(context); vm.runInContext(source, context);
  return {...context, badge, count, label};
}
test('accepted follow-up describes continuing at a completed step', () => {
  const f=fixture(); f.showQueueBadge(2,'steer');
  assert.equal(f.count.textContent,2);
  assert.equal(f.label.textContent,'added to active work');
  assert.match(f.badge.attributes['data-tooltip'],/next completed model or tool step/);
  assert.match(f.badge.attributes['data-tooltip'],/current work continues/);
  assert.match(html,/case 'queued':\s+showQueueBadge\(d.count\|\|1,d.mode\)/);
});
test('ordinary queued input resets a previous steering label', () => {
  const f=fixture(); f.showQueueBadge(2,'steer'); f.showQueueBadge(1);
  assert.equal(f.label.textContent,'queued');
  assert.equal(f.badge.attributes['data-tooltip'],'Your message is queued for the next available turn.');
});
