/* @nova: Display the isolated workshop feed for Cole, Codex and Cowork without sending messages to Nova. */
(() => {
  'use strict';
  window.mountNovaCollaboration = function(root) {
    if(root.dataset.collaborationMounted)return;
    root.dataset.collaborationMounted='true';
    root.classList.add('ncc-workshop');
    const element=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
    const storageKey='nova.collaboration.workshop.draft.v1';
    const uuid=()=>globalThis.crypto?.randomUUID?.()||('cole-'+Date.now()+'-'+Math.random().toString(36).slice(2));
    const header=element('div','ncc-heading');
    const title=element('div');title.append(element('strong','','Workshop'),element('p','','A shared channel for your development team.'));
    const connection=element('span','ncc-connection','Connecting…');connection.setAttribute('role','status');
    header.append(title,connection);
    const boundary=element('div','ncc-boundary');
    boundary.append(element('strong','','Nova is not participating'),element('p','','Messages stay in this collaboration channel. They are not sent to Nova’s context or memory, even if you write @Nova.'));
    const people=element('div','ncc-people');people.setAttribute('aria-label','Collaboration participants');
    const help=element('details','ncc-help');
    help.append(element('summary','','How the agents connect'),element('p','','Codex and Claude Cowork read and post through the collaboration bridge while their tasks are running. Waiting means a bridge is listening; active means it checked in recently. Neither state proves a message has been understood. Sleeping apps do not automatically wake up.'));
    const viewport=element('div','ncc-feed');viewport.setAttribute('role','log');viewport.setAttribute('aria-label','Workshop messages');viewport.setAttribute('aria-live','polite');viewport.setAttribute('aria-relevant','additions');viewport.tabIndex=0;
    const empty=element('div','ncc-empty');empty.append(element('span','ncc-empty-mark','◇'),element('h3','','Work it out together'),element('p','','Send a question, share a result, or ask the team to challenge a plan. Messages will appear here as each agent connects.'));viewport.append(empty);
    const feedArea=element('div','ncc-feed-area');
    const jump=element('button','ncc-jump','↓ Latest');jump.type='button';jump.hidden=true;jump.title='Jump to the latest message';
    feedArea.append(viewport,jump);
    const footer=element('form','ncc-compose');
    const label=element('label','','Message the workshop as Cole');label.htmlFor='collaboration-message';
    const input=element('textarea','ncc-input');input.id='collaboration-message';input.rows=3;input.maxLength=12000;input.placeholder='Talk with Codex and Claude…';input.setAttribute('aria-describedby','collaboration-hint');
    const bottom=element('div','ncc-compose-row');
    const hint=element('span','ncc-hint','Ctrl / ⌘ + Enter to send');hint.id='collaboration-hint';
    const send=element('button','nc-action ncc-send','Send message');send.type='submit';bottom.append(hint,send);
    const notice=element('p','ncc-notice');notice.setAttribute('role','status');
    footer.append(label,input,bottom,notice);root.append(header,boundary,people,help,feedArea,footer);
    let draft={text:'',id:''},cursor=0,stopped=false,busy=false,ready=false,failures=0,stateTimer=null,pollTimer=null;
    const requests=new Set(), messages=new Map();
    try{const value=JSON.parse(localStorage.getItem(storageKey)||'null');if(value&&typeof value.text==='string')draft={text:value.text.slice(0,input.maxLength),id:typeof value.id==='string'?value.id:''};}catch(_){}
    input.value=draft.text;
    const saveDraft=()=>{try{localStorage.setItem(storageKey,JSON.stringify(draft));}catch(_){notice.textContent='Draft storage is unavailable in this window. Keep it open until your message is sent.';}};
    const sendState=()=>{send.disabled=busy||!ready||!input.value.trim();send.textContent=busy?'Sending…':'Send message';};
    input.addEventListener('input',()=>{if(draft.text!==input.value)draft={text:input.value,id:''};saveDraft();sendState();});
    input.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();if(!send.disabled)footer.requestSubmit();}});
    function setConnection(text,online){connection.textContent=text;connection.dataset.online=String(online);}
    async function request(path,options={}) {
      const controller=new AbortController();requests.add(controller);
      const timeout=setTimeout(()=>controller.abort(),30000);
      try {
        const response=await fetch('/api/collaboration/'+path,{...options,signal:controller.signal,credentials:'same-origin',cache:'no-store'});
        const data=await response.json().catch(()=>({}));
        if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:typeof data.error==='string'?data.error:'Collaboration request failed ('+response.status+').');error.status=response.status;throw error;}
        return data;
      } finally {clearTimeout(timeout);requests.delete(controller);}
    }
    let unseen=0;
    const atBottom=()=>viewport.scrollHeight-viewport.scrollTop-viewport.clientHeight<=60;
    const syncJump=()=>{const bottom=atBottom();if(bottom)unseen=0;jump.hidden=bottom;jump.textContent=unseen?'↓ '+unseen+' new':'↓ Latest';};
    const scrollBottom=()=>{viewport.scrollTop=viewport.scrollHeight;unseen=0;syncJump();};
    jump.addEventListener('click',scrollBottom);
    viewport.addEventListener('scroll',syncJump,{passive:true});
    const resizeObserver=typeof ResizeObserver==='function'?new ResizeObserver(syncJump):null;
    resizeObserver?.observe(viewport);
    function addEvents(events,own=false) {
      const follow=atBottom()||own,oldHeight=viewport.scrollHeight,oldTop=viewport.scrollTop;
      let added=0;
      for(const event of events){
        if(!Number.isSafeInteger(event.seq)||event.seq<=0||typeof event.text!=='string'||messages.has(event.seq))continue;
        messages.set(event.seq,event);added++;
      }
      if(!added)return;
      const ordered=[...messages.values()].sort((a,b)=>a.seq-b.seq);
      while(ordered.length>200){messages.delete(ordered.shift().seq);}
      const retained=new Set(ordered.map(event=>String(event.seq)));
      for(const child of [...viewport.children])if(child!==empty&&!retained.has(child.dataset.seq))child.remove();
      empty.hidden=ordered.length>0;
      for(const event of ordered){
        if(viewport.querySelector('[data-seq="'+event.seq+'"]'))continue;
        const item=element('article','ncc-message');item.dataset.seq=String(event.seq);item.dataset.participant=event.participant;
        const meta=element('div','ncc-message-meta');meta.append(element('strong','',event.label||event.participant||'Participant'));
        const time=element('time');const date=new Date(event.created_at);
        if(!Number.isNaN(date.getTime())){time.dateTime=date.toISOString();time.textContent=date.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});time.title=date.toLocaleString();}
        else time.textContent='Time unavailable';
        meta.append(time,element('span','ncc-sequence','#'+event.seq));item.append(meta,element('p','ncc-message-text',event.text));
        const next=[...viewport.children].find(n=>Number(n.dataset.seq)>event.seq);
        viewport.insertBefore(item,next||null);
      }
      if(follow)requestAnimationFrame(scrollBottom);
      else {viewport.scrollTop=oldTop+Math.min(0,viewport.scrollHeight-oldHeight);unseen+=added;syncJump();}
    }
    async function refreshState() {
      try {
        const state=await request('state');
        if(state.nova_access!==false)throw new Error('The channel isolation status could not be confirmed.');
        ready=true;people.replaceChildren();
        for(const person of state.participants||[]){
          const chip=element('div','ncc-person');const status=['waiting','active','offline'].includes(person.state)?person.state:'offline';chip.dataset.state=status;
          chip.append(element('span','ncc-person-dot'),element('strong','',person.label||person.id),element('span','ncc-person-state',status));
          chip.title=(person.last_seen?'Last check-in: '+new Date(typeof person.last_seen==='number'?person.last_seen*1000:person.last_seen).toLocaleString():'No check-in yet')+(person.last_read?' · Read through #'+person.last_read:'');people.append(chip);
        }
      } catch(error) {ready=false;setConnection('Reconnecting…',false);people.querySelectorAll('.ncc-person').forEach(n=>{n.dataset.state='unknown';n.querySelector('.ncc-person-state').textContent='unknown';});}
      finally {sendState();if(!stopped)stateTimer=setTimeout(refreshState,10000);}
    }
    async function poll(wait=20) {
      try {
        const data=await request('events?after='+cursor+'&wait='+wait);
        if(!Array.isArray(data.events)||!Number.isSafeInteger(data.cursor))throw new Error('Invalid feed response');
        addEvents(data.events);cursor=Math.max(cursor,data.cursor);failures=0;setConnection('Connected',true);
        if(!stopped)pollTimer=setTimeout(()=>poll(data.has_more?0:20),data.has_more?0:100);
      } catch(error) {
        if(stopped)return;
        failures++;setConnection('Reconnecting…',false);
        pollTimer=setTimeout(()=>poll(),Math.min(15000,1000*Math.pow(2,Math.min(failures-1,4))));
      }
    }
    footer.addEventListener('submit',async event=>{
      event.preventDefault();if(busy||!ready||!input.value.trim())return;
      if(!draft.id)draft.id=uuid();draft.text=input.value;saveDraft();
      const submission={text:draft.text,client_message_id:draft.id};busy=true;input.readOnly=true;notice.textContent='';sendState();
      try {
        const message=await request('messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(submission)});
        if(!Number.isSafeInteger(message.seq))throw new Error('The server did not confirm this message.');
        addEvents([message],true);draft={text:'',id:''};input.value='';saveDraft();notice.textContent='Sent to the workshop.';
      } catch(error) {notice.textContent=error.message+' Your draft is saved. Send again to retry the same message safely.';}
      finally {busy=false;input.readOnly=false;sendState();input.focus();}
    });
    function stop(){stopped=true;resizeObserver?.disconnect();clearTimeout(stateTimer);clearTimeout(pollTimer);for(const controller of requests)controller.abort();}
    window.addEventListener('pagehide',stop,{once:true});
    sendState();refreshState();poll(0);
  };
})();
