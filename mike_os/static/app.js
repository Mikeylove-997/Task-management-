const $=s=>document.querySelector(s);let tasks=[],filter='all',editing=null,currentView='tasks';
const today=new Date();let calendarYear=today.getFullYear(),calendarMonth=today.getMonth();
const escapeHtml=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
async function api(path,options={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...options});const data=await res.json();if(!res.ok)throw new Error(data.error||'Something went wrong.');return data}
function fmtDate(s){if(!s)return'';return new Date(s.length===10?s+'T12:00:00':s).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}
function dateParts(s){if(!s)return null;const m=String(s).slice(0,10).match(/^(\d{4})-(\d{2})-(\d{2})$/);return m?{year:+m[1],month:+m[2]-1,day:+m[3]}:null}
async function load(){tasks=await api('/api/tasks');render()}
function updateCounts(){for(const s of ['inbox','active','backlog','completed'])$('#count-'+s).textContent=tasks.filter(t=>t.status===s).length;$('#count-all').textContent=tasks.length}
function render(){updateCounts();if(currentView==='calendar'){renderCalendar();return}renderTasks()}
function renderTasks(){const q=$('#search').value.toLowerCase();const visible=tasks.filter(t=>(filter==='all'||t.status===filter)&&(!q||[t.title,t.notes,t.next_action,t.project].some(v=>(v||'').toLowerCase().includes(q))));$('#task-summary').textContent=`${visible.length} task${visible.length===1?'':'s'}`;$('#task-list').innerHTML=visible.length?visible.map(t=>`<article class="task" data-id="${t.id}" data-status="${t.status}"><button class="complete" title="${t.status==='completed'?'Return to Active':'Complete task'}"></button><div><h3>${escapeHtml(t.title)}${t.is_accomplishment?' ★':''}</h3><div class="meta"><span class="pill">${t.status[0].toUpperCase()+t.status.slice(1)}</span>${t.project?`<span>${escapeHtml(t.project)}</span>`:''}${t.target_date?`<span class="pill due">Due ${fmtDate(t.target_date)}</span>`:''}${t.completed_at?`<span>Completed ${fmtDate(t.completed_at)}</span>`:''}${t.next_action?`<span>Next: ${escapeHtml(t.next_action)}</span>`:''}</div></div><button class="edit">Edit</button></article>`).join(''):`<div class="empty"><h2>Nothing here yet</h2><p>Add a task or try the command box above.</p></div>`}
function renderCalendar(){
  const first=new Date(calendarYear,calendarMonth,1);const daysInMonth=new Date(calendarYear,calendarMonth+1,0).getDate();const start=first.getDay();
  $('#calendar-month').textContent=first.toLocaleDateString(undefined,{month:'long',year:'numeric'});
  const byDay=new Map();
  tasks.forEach(t=>{const p=dateParts(t.target_date);if(!p||p.year!==calendarYear||p.month!==calendarMonth)return;if(!byDay.has(p.day))byDay.set(p.day,[]);byDay.get(p.day).push(t)});
  let html='';
  for(let i=0;i<start;i++)html+='<div class="calendar-day outside" aria-hidden="true"></div>';
  const now=new Date();
  for(let day=1;day<=daysInMonth;day++){
    const isToday=day===now.getDate()&&calendarMonth===now.getMonth()&&calendarYear===now.getFullYear();
    const dayTasks=(byDay.get(day)||[]).sort((a,b)=>String(a.title).localeCompare(String(b.title)));
    html+=`<div class="calendar-day${isToday?' today':''}"><div class="calendar-date">${day}</div><div class="calendar-items">${dayTasks.map(t=>`<button type="button" class="calendar-task" data-id="${t.id}" data-status="${t.status}" title="${escapeHtml(t.title)}"><span>${escapeHtml(t.title)}</span>${t.status==='completed'?'<small>✓</small>':''}</button>`).join('')}</div></div>`;
  }
  const totalCells=start+daysInMonth;for(let i=totalCells;i%7!==0;i++)html+='<div class="calendar-day outside" aria-hidden="true"></div>';
  $('#calendar-grid').innerHTML=html;
}
function showView(view,status='all',label='Overview'){
  currentView=view;filter=status;$('#page-title').textContent=label;
  $('#task-view').hidden=view==='calendar';$('#calendar-view').hidden=view!=='calendar';
  render();
}
function openTask(task=null,presetDate=null){editing=task;$('#dialog-title').textContent=task?'Edit task':'New task';$('#task-id').value=task?.id||'';$('#title').value=task?.title||'';$('#status').value=task?.status||'inbox';$('#target-date').value=(task?.target_date||presetDate||'').slice(0,10);$('#project').value=task?.project||'';$('#next-action').value=task?.next_action||'';$('#notes').value=task?.notes||'';$('#accomplishment').checked=!!task?.is_accomplishment;$('#history').innerHTML='';if(task)loadHistory(task.id);$('#task-dialog').showModal();setTimeout(()=>$('#title').focus(),50)}
async function loadHistory(id){const items=await api(`/api/tasks/${id}/history`);$('#history').innerHTML='<strong>History</strong>'+items.slice(0,6).map(e=>`<p>${fmtDate(e.occurred_at)} · ${escapeHtml(e.event_type)} via ${escapeHtml(e.source)}</p>`).join('')}
async function save(e){e.preventDefault();const data={title:$('#title').value,status:$('#status').value,target_date:$('#target-date').value||null,project:$('#project').value||null,next_action:$('#next-action').value||null,notes:$('#notes').value||null,is_accomplishment:$('#accomplishment').checked};await api(editing?`/api/tasks/${editing.id}`:'/api/tasks',{method:editing?'PATCH':'POST',body:JSON.stringify(data)});$('#task-dialog').close();await load()}
async function runCommand(){const input=$('#command'),text=input.value.trim();if(!text)return;$('#send').disabled=true;try{const result=await api('/api/command',{method:'POST',body:JSON.stringify({text})});$('#command-result').textContent=result.message;input.value='';await load()}catch(e){$('#command-result').textContent=e.message}finally{$('#send').disabled=false}}
$('#nav').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');const view=b.dataset.view||'tasks';showView(view,b.dataset.status||'all',b.querySelector('span').textContent)});
$('#task-list').addEventListener('click',async e=>{const card=e.target.closest('.task');if(!card)return;const task=tasks.find(t=>String(t.id)===String(card.dataset.id));if(!task)return;if(e.target.classList.contains('complete')){await api(`/api/tasks/${task.id}`,{method:'PATCH',body:JSON.stringify({status:task.status==='completed'?'active':'completed'})});await load()}else openTask(task)});
$('#calendar-grid').addEventListener('click',e=>{const button=e.target.closest('.calendar-task');if(!button)return;const task=tasks.find(t=>String(t.id)===String(button.dataset.id));if(task)openTask(task)});
$('#calendar-prev').onclick=()=>{calendarMonth--;if(calendarMonth<0){calendarMonth=11;calendarYear--}renderCalendar()};
$('#calendar-next').onclick=()=>{calendarMonth++;if(calendarMonth>11){calendarMonth=0;calendarYear++}renderCalendar()};
$('#calendar-today').onclick=()=>{const d=new Date();calendarYear=d.getFullYear();calendarMonth=d.getMonth();renderCalendar()};
$('#new-task').onclick=()=>openTask();$('#close').onclick=$('#cancel').onclick=()=>$('#task-dialog').close();$('#task-form').addEventListener('submit',save);$('#send').onclick=runCommand;$('#command').addEventListener('keydown',e=>{if(e.key==='Enter')runCommand()});$('#search').addEventListener('input',render);$('#date-line').textContent=new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});load().catch(e=>$('#task-list').innerHTML=`<div class="empty">${escapeHtml(e.message)}</div>`);
