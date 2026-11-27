'use strict';
const $=id=>document.getElementById(id);let session, generation=0, busy=false, replaces=null;
const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
const privacyUpdates = new BroadcastChannel('trace-workspace-privacy');
privacyUpdates.onmessage = () => { controller?.abort(); reset(); refresh().catch(e=>notice(e.message)); };
async function api(path,payload){const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Workspace-Token':session.token},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
function notice(s){$('notice').textContent=s;}
function button(label,handler,cls){const b=node('button',label,cls);b.type='button';b.onclick=handler;return b;}
function reset(){generation++;$('messages').replaceChildren(node('div','New conversation. Your saved memories are still available.','msg'));$('evidence').textContent='No evidence selected.';$('usage').textContent='0 / '+Number($('budget').value).toLocaleString();$('meter').value=0;$('retrieved').textContent='0 / 0';}
async function refresh(){const r=await api('list',{date:$('asof').value});$('count').textContent=r.facts.length;const box=$('library');box.replaceChildren();for(const f of r.facts){const c=node('div','','memory');c.append(node('b',f.key+(f.pin?' · pinned':'')),node('p',f.value),node('small','From '+f.start+(f.end?' until '+f.end:'')));c.append(button('Edit',()=>{replaces=f.id;$('key').value=f.key;$('value').value=f.value;$('pin').checked=f.pin;$('share').checked=!!f.share;$('effective').value=session.today;$('key').focus();}),button('Forget',async()=>{if(!confirm('Forget every saved version of this label?'))return;try{await api('forget',{key:f.key});privacyUpdates.postMessage('changed');reset();await refresh();notice('Forgot all versions of '+f.key+'.');}catch(e){notice(e.message);}},'danger'));box.append(c);}if(!r.facts.length)box.append(node('p','No memories for this date.','muted'));}
function message(role,text,cls=''){const el=node('div','','msg '+cls);el.append(node('small',role),node('div',text));$('messages').append(el);$('messages').scrollTop=$('messages').scrollHeight;}
$('save').onsubmit=async e=>{e.preventDefault();try{await api('save',{key:$('key').value,value:$('value').value,date:$('effective').value,pin:$('pin').checked,share:$('share').checked,share_revisions:$('share').checked,replaces});reset();await refresh();notice('Memory saved. Same-day updates replace the previous value.');$('value').value='';replaces=null;}catch(e){notice(e.message);}};
$('clear').onclick=async()=>{if(!confirm('Remove all saved memories and clear the visible chat?'))return;try{await api('clear',{});privacyUpdates.postMessage('changed');reset();await refresh();notice('All saved memories removed.');}catch(e){notice(e.message);}};
$('seed').onclick=async()=>{try{const current=await api('list',{date:session.today});const keys=new Set(current.facts.map(x=>x.key));for(const [key,value] of [['project deadline','The fictional Atlas research draft is due December 10.'],['programming language','I prefer Python for the fictional Atlas project.'],['research project','Atlas is a fictional study of long-term AI memory.']])if(!keys.has(key))await api('save',{key,value,date:session.today,pin:false});$('asof').value=session.today;reset();await refresh();notice('Fictional sample notes ready. Existing labels were not overwritten.');}catch(e){notice(e.message);}};
$('new').onclick=reset;$('asof').onchange=()=>{reset();refresh().catch(e=>notice(e.message));};$('budget').oninput=()=>{$('budgetval').textContent=Number($('budget').value).toLocaleString()+' chars';};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('question').value=b.dataset.prompt;$('question').focus();});
$('ask').onsubmit=async e=>{e.preventDefault();if(busy||!session)return;const q=$('question').value.trim();if(!q)return;const g=generation;busy=true;$('send').disabled=true;const welcome=$('messages').querySelector('.welcome');if(welcome)welcome.remove();message('You',q,'user');$('question').value='';try{const budget=Number($('budget').value);const r=await api('ask',{question:q,date:$('asof').value,budget,mode:$('mode').value});if(g!==generation)return;message(r.mode==='ollama'?'Local AI · unverified':'Memory lookup',r.answer);$('usage').textContent=r.used.toLocaleString()+' / '+budget.toLocaleString();$('meter').max=budget;$('meter').value=r.used;$('retrieved').textContent=r.evidence.length+' / '+r.available;$('evidence').replaceChildren();for(const f of r.evidence){const c=node('div','','memory');c.append(node('b',f.label),node('p',f.value),node('small','Effective '+f.valid_from));$('evidence').append(c);}if(!r.evidence.length)$('evidence').textContent='No matching evidence.';}catch(e){if(g===generation)message('Workspace',e.message,'error');}finally{busy=false;$('send').disabled=false;}};
(async()=>{try{const r=await fetch('/api/session');if(!r.ok)throw Error('Connection failed');session=await r.json();for(const id of ['effective','asof']){$(id).value=session.today;$(id).max=session.today;}if(session.model){$('mode').options[1].disabled=false;$('mode').options[1].textContent='Local AI · '+session.model;}$('status').textContent='● Local workspace';await refresh();await initAssistant();}catch(e){$('status').textContent='Disconnected';notice(e.message);}})();

$('key').addEventListener('input', () => { replaces = null; });
const theme = $('theme');
theme.value = localStorage.getItem('trace-theme') || 'dark';
const applyTheme = () => { document.documentElement.dataset.theme = theme.value; };
theme.addEventListener('change', () => {
    localStorage.setItem('trace-theme', theme.value);
    applyTheme();
});
applyTheme();
let chat = null, controller = null;
async function listChats() {
    const {chats} = await api('chats/search', {query: $('search').value});
    $('chats').replaceChildren(...chats.map(([id,title]) => new Option(title,id)));
    $('chats').value = chat || '';
}
function formatted(el, text) {
    el.replaceChildren();
    for (const [i,part] of text.split('```').entries()) {
        if (i % 2) {
            const code = part.replace(/^[\w+#.-]*\n/, '');
            el.append(node('pre',code),button('Copy code',()=>navigator.clipboard.writeText(code)));
        } else {
            for (const line of part.split('\n')) {
                const block = node(/^#{1,6} /.test(line)?'strong':'div','');
                for (const [j,span] of line.replace(/^#{1,6} /,'').split(/(\*\*.*?\*\*|`[^`]*`)/).entries()) {
                    block.append(j%2 ? node(span.startsWith('`')?'code':'strong',span.startsWith('`')?span.slice(1,-1):span.slice(2,-2)) : document.createTextNode(span));
                }
                el.append(block);
            }
        }
    }
    el.append(button('Copy answer',()=>navigator.clipboard.writeText(text)));
}
async function openChat(id) {
    controller?.abort();
    chat=id; reset(); $('messages').replaceChildren();
    const {turns}=await api('chats/history',{chat:id});
    if(chat!==id)return;
    for(const [q,a] of turns){message('You',q,'user');message('Assistant','');formatted($('messages').lastChild.lastChild,a);}
}
function guarded(fn){return async()=>{try{await fn();}catch(e){notice(e.message);}};}
$('new').onclick=guarded(async()=>{chat=(await api('chats/new',{})).chat;await openChat(chat);await listChats();});
$('chats').onchange=guarded(()=>openChat($('chats').value));
$('search').oninput=guarded(listChats);
$('rename').onclick=guarded(async()=>{const title=prompt('Conversation title');if(title&&chat){await api('chats/rename',{chat,title});await listChats();}});
$('remove').onclick=guarded(async()=>{if(chat&&confirm('Delete this transcript? Confirmed memories are managed separately.')){controller?.abort();await api('chats/remove',{chat});chat=null;reset();await listChats();}});
$('stop').onclick=()=>controller?.abort();
const offlineAsk=$('ask').onsubmit;
async function stream(regenerate){
    if(controller)return;
    const question=$('question').value.trim();
    if(!regenerate&&!question)return;
    const requestGeneration=generation;
    controller=new AbortController();$('stop').disabled=false;$('send').disabled=true;
    try{
        if(!chat){chat=(await api('chats/new',{})).chat;$('messages').replaceChildren();await listChats();}
        if(regenerate){const previous=$('messages').lastChild;if(previous?.classList.contains('msg'))previous.remove();}
        if(!regenerate){message('You',question,'user');$('question').value='';}
        message('Assistant','Preparing response…');
        const el=$('messages').lastChild.lastChild;
        const response=await fetch('/api/stream',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','X-Workspace-Token':session.token},body:JSON.stringify({chat,question,regenerate,semantic:$('semantic').checked,strategy:$('strategy').value,verification:Number($('verification').value),model:$('models').value,temperature:Number($('temperature').value),output:Number($('output').value),budget:Number($('budget').value),date:$('asof').value})});
        const reader=response.body.pipeThrough(new TextDecoderStream()).getReader();
        let buffer='',answer='',done=false;
        while(true){
            const part=await reader.read();if(part.done)break;
            buffer+=part.value;let end;
            while((end=buffer.indexOf('\n'))>=0){
                const row=JSON.parse(buffer.slice(0,end));buffer=buffer.slice(end+1);
                if(row.error)throw Error(row.error);
                if(row.text){answer+=row.text;el.textContent=answer;}
                if(row.done){
                    done=true;el.parentElement.firstChild.textContent=row.reader_reason?"Direct memory lookup":"Local AI · generated";formatted(el,answer);
                    $('usage').textContent=row.prompt+' input / '+row.output+' output tokens';
                    $('retrieved').textContent=row.strategy+' · '+row.semantic_status+' · '+row.evidence.length+' memories · '+row.history+' earlier turns';
                    $('meter').max=4096;$('meter').value=row.prompt;
                    $('evidence').textContent=row.evidence.map(r=>r.label+' · '+r.value+' ('+r.reason+' · '+r.valid_from+' · source '+(r.source||r.id)+', '+JSON.stringify(r).length+' JSON characters)').join('\n')||'No matching evidence.';
                    if(row.reader_reason)el.append(node('small',row.reader_reason));for(const p of row.proposals||[]){el.append(node('small','From turn '+p.turn+' · effective '+p.date+' · '+p.intent));el.append(button('Review '+p.intent+' · '+p.key,guarded(async()=>{const value=prompt(p.review+' Confirm or edit this '+p.intent+' proposal.',p.value);if(value){if(p.target&&!confirm('Replace the confirmed '+p.key+' with this correction?'))return;await api('proposal',{...p,value,date:p.date,replaces:p.target});await refresh();notice('Memory confirmed.');}})));}
                }
            }
        }
        if(!done)throw Error('Incomplete response. Check Ollama and retry.');
        await listChats();
    }catch(e){if(!regenerate&&e.name!=='AbortError'&&generation===requestGeneration&&!$('question').value)$('question').value=question;const last=$('messages').lastChild; if(last?.querySelector('small')?.textContent==='Assistant') last.append(node('small',e.name==='AbortError'?'Stopped':'Response incomplete'));notice(e.name==='AbortError'?'Generation stopped.':e.message);}
    finally{controller=null;$('stop').disabled=true;$('send').disabled=false;}
}
$('ask').onsubmit=e=>{if($('mode').value==='memory')return offlineAsk(e);e.preventDefault();stream(false);};
$('retry').onclick=()=>stream(true);
async function initAssistant(){
    const models=(await (await fetch('/api/models')).json()).models;
    $('models').replaceChildren(...models.map(m=>new Option(m,m)));
    if(models.length){$('models').value=models.find(m=>m.startsWith('qwen2.5:7b'))||models[0];$('mode').options[1].disabled=false;$('mode').value='ollama';}
    else notice('Offline lookup ready. Start Ollama with a local model and reload for chat.');
    await listChats();if($('chats').options.length)await openChat($('chats').options[0].value);
}
$('pilot').addEventListener('toggle', async () => {
    const panel = $('pilotReport');
    if (!$('pilot').open || panel.childElementCount) return;
    try {
        const response = await fetch('/api/pilot');
        if (!response.ok) throw Error('Pilot results unavailable.');
        const data = await response.json();
        panel.replaceChildren(node('h2','Live Ollama results'),node('p','Five internally authored questions per mode, with a shared model and context allowance.'));
        const table = document.createElement('table');
        const head = table.insertRow();
        for (const label of ['Mode','Exact answers','Input tokens','Output tokens','Mean seconds','Abstentions','Request errors']) head.append(node('th',label));
        for (const mode of ['standard','rag','trace']) {
            const rows = data.rows.filter(r=>r.mode===mode);
            const sum = field => rows.reduce((total,r)=>total+Number(r[field]||0),0);
            const tr = table.insertRow();
            tr.insertCell().textContent=mode;
            const cell=tr.insertCell(), bar=document.createElement('progress');
            bar.value=sum('correct'); bar.max=rows.length;
            cell.append(bar,document.createTextNode(' '+bar.value+'/'+bar.max));
            for(const value of [sum('prompt'),sum('output'),(sum('seconds')/rows.length).toFixed(2),sum('abstained'),rows.filter(r=>r.error).length]) tr.insertCell().textContent=value;
        }
        panel.append(table,node('h3','Incorrect answers'));
        for(const r of data.rows.filter(r=>!r.correct))panel.append(node('p',r.mode+' · '+r.query+' — '+(r.answer||r.error)));
        panel.append(node('h3','Deterministic storage check'),node('p','Incorrect overwrites on one unconfirmed conflict: '+data.engineering.incorrect_overwrites));
    } catch(error) { panel.textContent=error.message; }
});
$('reliability').addEventListener('toggle', async () => {
    const panel = $('reliabilityReport');
    if (!$('reliability').open || panel.childElementCount) return;
    try {
        const response = await fetch('/api/reliability-pilot');
        if (!response.ok) throw Error('Reliability results unavailable.');
        const data = await response.json();
        const total = (rows,key) => rows.reduce((n,r)=>n+Number(r[key]||0),0);
        panel.append(node('h2','Raw-message acquisition and answering'));
        panel.append(node('p','Internally authored messages with scripted review. '+
            total(data.extracts,'tp')+' correct proposals, '+total(data.extracts,'fp')+
            ' extra and '+total(data.extracts,'fn')+' missed.'));
        for (const mode of ['standard','rag','trace']) {
            const rows=data.answers.filter(r=>r.mode===mode);
            const supported=rows.filter(r=>r.supported);
            panel.append(node('h3',mode),node('p',total(rows,'correct')+'/'+rows.length+
                ' exact answers · '+total(supported,'correct')+'/'+supported.length+
                ' with target evidence · '+total(rows,'prompt')+' input and '+
                total(rows,'output')+' generated tokens.'));
        }
    } catch(error) {panel.textContent=error.message;}
});
const updateStory = () => {
    $('story').textContent = $('persona').selectedIndex===0
        ? 'You plan workshops. Start with “I live in Laurel Port.” Your later move is to Fawn Crossing.'
        : 'You study river habitats. Start with “I live in Copper Hill.” Your later move is to Maple Inlet.';
};
$('persona').onchange=updateStory;
updateStory();
if(location.hash==='#practice') $('practice').open=true;
$('longHistory').addEventListener('toggle',async()=>{
    const panel=$('historyResults');
    if(!$('longHistory').open||panel.childElementCount)return;
    try {
        const data=await (await fetch('/api/long-history')).json();
        panel.append(node('p','Exact answers out of three per length. TRACE-Mem used two direct lookups and one generated answer per length.'));
        const table=document.createElement('table');
        const header=table.insertRow();
        for(const h of ['Estimated tokens','Standard','RAG','TRACE-Mem'])header.append(node('th',h));
        for(const size of [...new Set(data.rows.map(r=>r.length))]){
            const tr=table.insertRow();tr.insertCell().textContent=size.toLocaleString();
            for(const mode of ['standard','rag','trace']){
                const rows=data.rows.filter(r=>r.length===size&&r.mode===mode);
                tr.insertCell().textContent=rows.filter(r=>r.correct).length+' / '+rows.length;
            }
        }
        panel.append(table);
    } catch(e){panel.textContent='Long-history data unavailable.';}
});
$('modelPilot').addEventListener('toggle',async()=>{
    const panel=$('modelResults');
    if(!$('modelPilot').open||panel.childElementCount)return;
    try{
        const report=await (await fetch('/api/model-pilot')).json();
        for(const [model,data] of Object.entries(report)){
            const rows=data.rows.filter(r=>r.direct===false&&'correct' in r);
            panel.append(node('p',model+' · '+rows.filter(r=>r.correct).length+'/'+rows.length+' exact generated arithmetic and abstention answers across two repetitions.'));
        }
    }catch(e){panel.textContent='Model comparison unavailable.';}
});
