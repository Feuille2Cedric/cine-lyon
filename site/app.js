import {addDays,monday,civilMinutes,layoutSessions,makeIcs} from './calendar.js';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=v=>{try{const u=new URL(v);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
const parisDate=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const fmt=(iso,options)=>new Intl.DateTimeFormat('fr-FR',{...options,timeZone:'UTC'}).format(new Date(iso+'T12:00:00Z'));
const clock=v=>String(Math.floor(v/60)%24).padStart(2,'0')+':'+String(v%60).padStart(2,'0');
const normalize=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
let data,cinemas=new Map(),selected=new Set(),date=parisDate(),view='week',query='',version='',genre='',hourHeight=88,overflowGroups=[],renderTimer;
function save(){try{localStorage.setItem('travelling-settings',JSON.stringify({selected:[...selected],view,hourHeight,genre}));}catch{}}
function scrollToToday(){if(view==='week'&&innerWidth<700){const column=$('#calendar').querySelector(`[data-day="${parisDate()}"]`);if(column)$('#calendar-shell').scrollLeft=column.offsetLeft-54;}}
function palette(c){return `--color:${c.color};--pale:${c.pale};--ink:${c.ink}`;}
function period(){const start=view==='day'?date:monday(date);return {start,end:addDays(start,view==='day'?1:7)};}
function visibleEvents(){const {start,end}=period();return data.sessions.filter(s=>s.start.slice(0,10)>=start&&s.start.slice(0,10)<end&&selected.has(s.cinema)&&normalize(s.title).includes(normalize(query))&&(!version||s.version.startsWith(version))&&(!genre||(s.genres||[]).some(g=>normalize(g)===normalize(genre))));}
function renderGenres(){
  const values=[...new Set(data.sessions.flatMap(s=>s.genres||[]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr'));
  $('#genre').innerHTML='<option value="">Tous les genres</option>'+values.map(g=>`<option value="${esc(g)}">${esc(g)}</option>`).join('');
  if(genre&&!values.includes(genre))genre='';
  $('#genre').value=genre;
}
function miniCalendar(){
  $('#mini-month').textContent=fmt(date,{month:'long',year:'numeric'});const first=monday(date.slice(0,7)+'-01'),start=monday(date);
  $('#mini-calendar').innerHTML=['L','M','M','J','V','S','D'].map(d=>`<span>${d}</span>`).join('')+Array.from({length:42},(_,i)=>{const d=addDays(first,i);return `<button data-date="${d}" aria-label="${esc(fmt(d,{dateStyle:'full'}))}" class="${d>=start&&d<addDays(start,7)?'in-week ':''}${d===parisDate()?'is-today ':''}${d.slice(0,7)!==date.slice(0,7)?'outside':''}">${Number(d.slice(8))}</button>`;}).join('');
}
function renderCinemas(){
  const {start,end}=period();let group='';$('#cinemas').innerHTML=data.cinemas.map(c=>{const heading=c.group!==group?`<div class="cinema-group">${esc(c.group)}</div>`:'';group=c.group;const n=data.sessions.filter(s=>s.cinema===c.id&&s.start.slice(0,10)>=start&&s.start.slice(0,10)<end).length;return heading+`<label class="cinema-row" style="${palette(c)}"><input type="checkbox" value="${c.id}" ${selected.has(c.id)?'checked':''}><span>${esc(c.name)}</span><span class="cinema-count">${n||'—'}</span></label>`;}).join('');$('#toggle-all').textContent=selected.size?'Tout masquer':'Tout afficher';
}
function renderNotice(events){
  const errors=data.cinemas.filter(c=>selected.has(c.id)&&(data.sources[c.id]?.status!=='ok'||Date.now()-Date.parse(data.sources[c.id]?.updatedAt)>36*3600000));const {start,end}=period();
  const uncovered=data.cinemas.filter(c=>selected.has(c.id)&&!data.sources[c.id]?.days?.some(d=>d>=start&&d<end));let message='';
  if(errors.length)message=`Programme à vérifier pour ${errors.map(c=>c.name).join(', ')}. Les dernières séances connues restent affichées.`;
  else if(uncovered.length)message=`Programme non disponible sur cette période pour ${uncovered.map(c=>c.name).join(', ')}.`;
  else if(start<parisDate()&&events.length&&data.cinemas.some(c=>selected.has(c.id)&&!data.sources[c.id]?.days?.includes(start)&&!data.sessions.some(s=>s.cinema===c.id&&s.start.startsWith(start))))message='Les premiers jours de cette semaine peuvent être incomplets : certains sites ne publient plus les séances passées.';
  $('#notice').hidden=!message;$('#notice').innerHTML=esc(message)+(message?' <button id="notice-sources">Voir les sources ↗</button>':'');$('#notice-sources')?.addEventListener('click',()=>$('#sources').showModal());
}
function sessionButton(s){const c=cinemas.get(s.cinema);return `<button class="session" data-session="${s.id}" style="${palette(c)}" title="${esc(s.title+' · '+clock(civilMinutes(s.start))+' · '+c.name+' · '+s.version)}" aria-label="${esc(s.title+', '+clock(civilMinutes(s.start))+', '+c.name+', '+s.version)}"><span class="session-time">${clock(civilMinutes(s.start))}</span><span class="session-title">${esc(s.title)}</span><span class="session-cinema">${esc(c.short)}</span>${s.version?`<span class="session-version">${esc(s.version)}</span>`:''}</button>`;}
function listRow(s){const c=cinemas.get(s.cinema);return `<button class="list-session" data-session="${s.id}" style="${palette(c)}"><span class="detail-dot"></span><time>${clock(civilMinutes(s.start))}</time><b>${esc(s.title)}</b><small>${esc(c.name)}<br>${esc(s.version)}</small></button>`;}
function renderCalendar(events){
  const calendar=$('#calendar'),{start}=period();calendar.className='calendar'+(view==='list'?' list-view':view==='day'?' day-view':'');$('#empty').hidden=events.length>0;
  if(!events.length){calendar.replaceChildren();return;}
  if(view==='list'){let last='';calendar.innerHTML=events.map(s=>{const d=s.start.slice(0,10),head=d!==last?`<h3 class="list-day">${esc(fmt(d,{weekday:'long',day:'numeric',month:'long'}))}</h3>`:'';last=d;return head+listRow(s);}).join('');return;}
  const days=Array.from({length:view==='day'?1:7},(_,i)=>addDays(start,i));
  const startHour=Math.min(9,Math.floor(Math.min(...events.map(s=>civilMinutes(s.start)))/60));const endHour=Math.max(24,Math.ceil(Math.max(...events.map(s=>civilMinutes(s.start)+(s.duration||90)))/60));const height=(endHour-startHour)*hourHeight;
  calendar.style.setProperty('--days',days.length);calendar.style.setProperty('--hour',hourHeight+'px');
  calendar.innerHTML=`<div class="calendar-header"><div class="timezone">LYON</div>${days.map(d=>`<div class="day-header ${d===parisDate()?'current':''}"><span class="weekday">${fmt(d,{weekday:'short'})}</span><span class="day-number">${Number(d.slice(8))}</span></div>`).join('')}</div><div class="calendar-body" style="height:${height}px"><div class="time-axis">${Array.from({length:endHour-startHour},(_,i)=>`<span class="hour-label" style="top:${i*hourHeight}px">${clock((startHour+i)*60)}</span>`).join('')}</div>${days.map((d,i)=>`<div class="day-column ${d===parisDate()?'current':''} ${i>=5?'weekend':''}" data-day="${d}"></div>`).join('')}</div>`;
  overflowGroups=[];
  for(const day of days){
    const column=calendar.querySelector(`[data-day="${day}"]`),sessions=layoutSessions(events.filter(s=>s.start.startsWith(day))),cap=view==='day'?6:2,hidden=new Map();
    for(const s of sessions){
      if(s.lane>=cap){const bucket=Math.floor(s.minute/30)*30;if(!hidden.has(bucket))hidden.set(bucket,[]);hidden.get(bucket).push(s);continue;}
      const holder=document.createElement('div');holder.innerHTML=sessionButton(s);const button=holder.firstElementChild,hasOverflow=s.lanes>cap,lanes=Math.min(s.lanes,cap);
      button.style.left=`calc((100% - ${hasOverflow?30:0}px) * ${s.lane/lanes} + 3px)`;button.style.width=`calc((100% - ${hasOverflow?30:0}px) / ${lanes} - 5px)`;button.style.top=(s.minute-startHour*60)/60*hourHeight+'px';button.style.height=Math.max(24,s.length/60*hourHeight-3)+'px';column.append(button);
    }
    for(const [minute,slots] of hidden){const index=overflowGroups.push({day,minute,sessions:slots})-1,button=document.createElement('button');button.className='overflow-button';button.dataset.overflow=index;button.textContent='+'+slots.length;button.title=`${slots.length} autres séances à partir de ${clock(minute)}`;button.setAttribute('aria-label',button.title);button.style.top=(minute-startHour*60)/60*hourHeight+'px';column.append(button);}
    if(day===parisDate()){const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date()).split(':'),minute=Number(parts[0])*60+Number(parts[1]);if(minute>=startHour*60&&minute<endHour*60){const line=document.createElement('div');line.className='now-line';line.style.top=(minute-startHour*60)/60*hourHeight+'px';column.append(line);}}
  }
}
function render(){
  if(!data)return;const events=visibleEvents(),{start,end}=period();$('#range').textContent=view==='day'?fmt(date,{day:'numeric',month:'long',year:'numeric'}):`${fmt(start,{day:'numeric',month:'short'})} — ${fmt(addDays(end,-1),{day:'numeric',month:'short',year:'numeric'})}`;$('#date').value=date;$('#count').textContent=`${events.length} séance${events.length>1?'s':''} · ${new Set(events.map(s=>s.title)).size} films`;
  $('#empty-text').textContent=selected.size?'Aucune séance connue ne correspond à cette période et à vos filtres. Les programmes futurs peuvent ne pas encore être publiés.':'Sélectionnez au moins un cinéma pour afficher ses séances.';
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));renderCinemas();miniCalendar();renderNotice(events);renderCalendar(events);save();
}
function details(id){
  const s=data.sessions.find(s=>s.id===id);if(!s)return;const c=cinemas.get(s.cinema),minute=civilMinutes(s.start);
  $('#detail-content').innerHTML=`<div class="detail-cinema" style="${palette(c)}"><span class="detail-dot"></span>${esc(c.name)}</div><h2 id="detail-title">${esc(s.title)}</h2><div class="detail-meta"><div><span>Le rendez-vous</span><strong>${esc(fmt(s.start.slice(0,10),{weekday:'long',day:'numeric',month:'long'}))}</strong></div><div><span>La séance</span><strong>${clock(minute)}${s.duration?' → '+clock(minute+s.duration):''} ${esc(s.version)}</strong></div><div><span>Le cinéma</span><strong>${esc(c.address)}</strong></div><div><span>Durée du film</span><strong>${s.duration?Math.floor(s.duration/60)+' h '+String(s.duration%60).padStart(2,'0'):'Non communiquée'}</strong></div><div><span>Genre</span><strong>${(s.genres||[]).length?esc(s.genres.join(', ')):'Non communiqué'}</strong></div></div>${s.extra?`<p>${esc(s.extra)}</p>`:''}<p>${s.duration?'L’heure de fin est estimée, hors publicités, présentations et échanges.':'Durée non communiquée : le bloc occupe 90 minutes à titre indicatif.'}</p><div class="detail-actions"><a class="primary" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">Voir / réserver la séance ↗</a><button id="export-ics">Ajouter à mon agenda</button></div>`;
  $('#export-ics').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([makeIcs(s,c)],{type:'text/calendar;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='travelling-'+s.id+'.ics';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});if(!$('#details').open)$('#details').showModal();
}
function showOverflow(index){const g=overflowGroups[index];if(!g)return;$('#detail-content').innerHTML=`<p class="eyebrow">ENCORE PLUS DE CINÉMA</p><h2 id="detail-title">${esc(fmt(g.day,{weekday:'long',day:'numeric',month:'long'}))}</h2><p>${g.sessions.length} autres séances entre ${clock(g.minute)} et ${clock(g.minute+29)}.</p>${g.sessions.map(listRow).join('')}<button id="open-day" class="primary" style="margin-top:20px">Voir toute cette journée</button>`;$('#open-day').onclick=()=>{date=g.day;view='day';$('#details').close();render();};$('#details').showModal();}
function renderSources(){
  $('#source-list').innerHTML=data.cinemas.map(c=>{const s=data.sources[c.id];return `<div class="source-item"><strong>${esc(c.name)}</strong><small>${s?.status==='ok'?'Programme récupéré':'Actualisation indisponible'}${s?.updatedAt?' · '+new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',dateStyle:'short',timeStyle:'short'}).format(new Date(s.updatedAt)):''}</small><small><a href="${esc(safeUrl(s?.url||c.url))}" target="_blank" rel="noopener">${esc(s?.label||'Site du cinéma')} ↗</a></small></div>`;}).join('');const latest=Object.values(data.sources).map(s=>s.updatedAt).filter(Boolean).sort().at(-1);$('#updated').textContent=latest?'Actualisé le '+new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(latest)):'Programmes indisponibles';
}
$('#previous').onclick=()=>{date=addDays(date,view==='day'?-1:-7);render();};$('#next').onclick=()=>{date=addDays(date,view==='day'?1:7);render();};$('#today').onclick=()=>{date=parisDate();render();scrollToToday();};
$('#date').onchange=e=>{if(/^\d{4}-\d{2}-\d{2}$/.test(e.target.value)){date=e.target.value;render();}};$('#mini-calendar').onclick=e=>{const b=e.target.closest('[data-date]');if(b){date=b.dataset.date;render();}};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;render();});$('#cinemas').onchange=e=>{if(e.target.checked)selected.add(e.target.value);else selected.delete(e.target.value);render();};$('#toggle-all').onclick=()=>{selected=selected.size?new Set():new Set(cinemas.keys());render();};
$('#search').oninput=e=>{query=e.target.value;clearTimeout(renderTimer);renderTimer=setTimeout(render,100);};$('#version').onchange=e=>{version=e.target.value;render();};$('#genre').onchange=e=>{genre=e.target.value;render();};$('#zoom').oninput=e=>{hourHeight=Number(e.target.value);render();};$('#reset').onclick=()=>{selected=new Set(cinemas.keys());query='';version='';genre='';$('#search').value='';$('#version').value='';$('#genre').value='';render();};
document.addEventListener('click',e=>{const s=e.target.closest('[data-session]');if(s)details(s.dataset.session);const more=e.target.closest('[data-overflow]');if(more)showOverflow(Number(more.dataset.overflow));});
document.querySelectorAll('dialog').forEach(d=>{d.querySelector('.close').onclick=()=>d.close();d.onclick=e=>{const r=d.getBoundingClientRect();if(e.target===d&&e.clientX&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))d.close();};});$('#sources-button').onclick=()=>$('#sources').showModal();
try{const response=await fetch('./data/schedule.json',{cache:'no-cache'});if(!response.ok)throw new Error('HTTP '+response.status);data=await response.json();data.sessions.forEach(s=>{if(!Array.isArray(s.genres))s.genres=[];});cinemas=new Map(data.cinemas.map(c=>[c.id,c]));selected=new Set(cinemas.keys());
  try{const saved=JSON.parse(localStorage.getItem('travelling-settings'));if(saved){if(Array.isArray(saved.selected))selected=new Set(saved.selected.filter(id=>cinemas.has(id)));if(['week','day','list'].includes(saved.view))view=saved.view;if(typeof saved.genre==='string')genre=saved.genre;if(saved.hourHeight>=60&&saved.hourHeight<=160)hourHeight=saved.hourHeight;}}catch{}
  $('#footer-sources').onclick=()=>$('#sources').showModal();
  $('#zoom').value=hourHeight;renderGenres();renderSources();render();scrollToToday();setInterval(()=>{if(document.visibilityState==='visible'&&!$('#details').open)render();},60000);
}catch(error){$('#notice').hidden=false;$('#notice').textContent='Le programme n’a pas pu être chargé. Vérifiez votre connexion puis rechargez la page.';$('#empty').hidden=false;$('#empty-text').textContent='Les horaires sont momentanément indisponibles.';$('#reset').textContent='Réessayer';$('#reset').onclick=()=>location.reload();$('#updated').textContent='Chargement indisponible';console.error(error);}
