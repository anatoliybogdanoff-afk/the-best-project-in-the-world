import {CRITERIA, byId, icon} from './data/criteria.js';
import {duckSvg, duckMotionCss} from './components/duck-art.js';
import './components/criterion-explainer.js';

const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => new Intl.NumberFormat('ru-RU').format(value ?? 0);
const weight = id => state.rules.find(rule => rule.id === id)?.weight ?? byId[id]?.weight ?? 0;
const scoreText = value => value == null ? '—' : `${number(value)}%`;
const initials = name => name.replace(/[^\p{L}\s]/gu,' ').trim().split(/\s+/).slice(0,2).map(part=>part[0]||'').join('').toUpperCase() || 'П';
const state = {view:'analysis', selectedCriterion:'route_tail', rules:[], offset:0, limit:25, query:'', filter:'all', sort:'score', total:0, calculating:false, showResults:false, person:null, listController:null, personController:null};
let searchTimer;

function fillIcons(root=document){root.querySelectorAll('[data-icon]').forEach(node=>node.innerHTML=icon(node.dataset.icon));}
async function api(path, options={}){
 const response=await fetch(path,options);
 const data=await response.json();
 if(!response.ok)throw new Error(data.error||'Не удалось получить данные');
 return data;
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4000);}
function showError(message){$('pageError').textContent=message;$('pageError').hidden=false;}
function heroArtwork(){return `<svg class="hero-illustration" viewBox="0 0 440 330" fill="none"><circle cx="292" cy="163" r="132" fill="#F0DDE8"/><circle cx="292" cy="163" r="111" stroke="#E7CEDD" stroke-dasharray="3 9"/><path d="M65 258C10 116 353 294 353 75" stroke="#CBA0BB" stroke-width="1.5" stroke-dasharray="5 7"/><path d="m343 78 9-8 5 9" stroke="#CBA0BB" stroke-width="1.5" stroke-linecap="round"/><circle cx="65" cy="258" r="5" fill="#B57C9E"/><g class="float-ticket"><g transform="translate(190 48) rotate(-11)"><rect width="165" height="85" rx="11" fill="#FFFCFE" stroke="#E5CDDD"/><path d="M115 5v75" stroke="#EBD8E5" stroke-dasharray="3 4"/><rect x="15" y="18" width="49" height="4" rx="2" fill="#DCBACC"/><path d="M17 47h75m-5-5 6 5-6 5" stroke="#C596B2" stroke-width="2"/><rect x="16" y="65" width="30" height="3" rx="1.5" fill="#EAD8E4"/><path d="M130 25v35m6-35v35m5-35v35m8-35v35" stroke="#D6B5CA" stroke-width="3"/></g></g><g class="float-ticket second"><g transform="translate(313 197) rotate(13)"><rect width="84" height="58" rx="8" fill="#FFFCFE" stroke="#E2C8D8"/><rect x="13" y="12" width="27" height="4" rx="2" fill="#D9AFC7"/><path d="M13 29h56m-56 7h40m-40 7h45" stroke="#E7D3E0" stroke-width="3" stroke-linecap="round"/></g></g><g class="hero-spy"><g transform="translate(98 179) rotate(-7)">${duckSvg({spy:true,width:110})}</g></g><g class="hero-duck"><g transform="translate(219 125)">${duckSvg({look:true,width:145})}</g></g><path class="hero-spark" d="m110 88 5-13 5 13 13 5-13 5-5 13-5-13-13-5z" fill="#D2A0BA"/><path class="hero-spark" d="m359 136 3-8 3 8 8 3-8 3-3 8-3-8-8-3z" fill="#DAB182"/><circle cx="148" cy="145" r="3" fill="#D5B3C8"/><circle cx="376" cy="277" r="3" fill="#D7B5C8"/></svg>`;}

function setView(view, criterion){
 state.view = ['analysis', 'upload', 'criteria', 'method'].includes(view)? view: 'analysis';

 document.querySelectorAll('.view').forEach(node=>node.hidden=node.id!==`${state.view}View`);
 document.querySelectorAll('.nav-item').forEach(node=>{node.classList.toggle('active',node.dataset.view===state.view);node.setAttribute('aria-current',node.dataset.view===state.view?'page':'false');});
$('pageTitle').textContent = {
  analysis: 'Проверка пассажиров',
  upload: 'Анализ',
  criteria: 'Как работают признаки',
  method: 'Как считаются баллы'
}[state.view];
 document.querySelector('.sidebar').classList.remove('open');$('menuButton').setAttribute('aria-expanded','false');
 if(criterion)state.selectedCriterion=criterion;
 if(state.view==='criteria')renderAcademy();
 history.replaceState(null,'',`#${state.view}${state.view==='criteria'?'/'+state.selectedCriterion:''}`);
}
function renderTeasers(){
 $('teaserGrid').innerHTML=['high_freq','route_tail','card_multi'].map(id=>{const item=byId[id];return `<button class="teaser" data-criterion-link="${id}"><div class="teaser-top"><span class="teaser-icon">${icon(item.icon)}</span><span class="teaser-weight">+${weight(id)} баллов</span></div><h3>${item.title}</h3><p>${item.text}</p><div class="teaser-bottom">Разобрать на примере ${icon('arrow',15)}</div></button>`;}).join('');
}
function renderAcademy(){
 const current=byId[state.selectedCriterion]||byId.route_tail;
 $('criterionMenu').innerHTML=CRITERIA.map((item,index)=>`<button class="criterion-tab ${item.id===current.id?'active':''}" data-criterion-select="${item.id}" aria-pressed="${item.id===current.id}"><span class="tab-index">${String(index+1).padStart(2,'0')}</span>${icon(item.icon,18)}<span class="tab-label">${item.title}</span><span class="tab-weight">+${weight(item.id)}</span></button>`).join('');
 $('academyCard').innerHTML=`<div class="academy-kicker"><span class="criterion-icon">${icon(current.icon)}</span><span class="academy-number">ПРИЗНАК ${String(CRITERIA.indexOf(current)+1).padStart(2,'0')} / 10</span><span class="weight-badge">+${weight(current.id)} баллов</span></div><h2>${current.title}</h2><p class="academy-description">${current.text}</p><criterion-explainer criterion="${current.id}" weight="${weight(current.id)}"></criterion-explainer><p class="rule-line">${icon('check',16)}<span>${current.rule}</span></p><p class="context-note">${current.note}</p>`;
}
function renderMethod(){
 $('weightsList').innerHTML=CRITERIA.map(item=>`<div class="method-weight-row"><span>${icon(item.icon,18)}</span><span>${item.title}</span><strong>${weight(item.id)}</strong></div>`).join('')+`<div class="method-sum"><span>Максимальная сумма</span><strong>${state.rules.reduce((sum,rule)=>sum+rule.weight,0)} баллов</strong></div>`;
}
async function loadStatus(){
 try{
  const status=await api('/api/status');
  $('connectionStatus').className=`connection-status ${status.connected?'connected':'error'}`;
  $('connectionStatus').innerHTML=`<i></i><span>${status.connected?'База подключена':'База недоступна'}</span>`;
  if(status.job?.status==='running'&&!state.calculating){setCalculating(true);pollJob(status.job.id);}
  if(status.has_results&&!$('openLastButton')){
   const button=document.createElement('button');button.id='openLastButton';button.className='text-button';button.innerHTML='Последний расчёт <span>↗</span>';
   button.addEventListener('click',showResults);document.querySelector('.hero-actions').append(button);
  }
 }catch{$('connectionStatus').className='connection-status error';$('connectionStatus').innerHTML='<i></i><span>Сервер недоступен</span>';}
}
function setCalculating(running){
 state.calculating=running;$('calculateButton').disabled=running;
 $('calculateButton').querySelector('.calculate-label').textContent=running?'Считаем…':'Рассчитать шпионов';
 $('calculationNotice').hidden=!running;
 if(running)$('calculationNotice').innerHTML=`<span class="small-duck">${duckSvg({spy:true,width:42})}</span><div><strong>Уточки изучают историю перелётов…</strong><small>Читаем готовые признаки и суммируем веса. Рейтинг появится здесь.</small></div><span class="loading-spinner"></span>`;
}
async function calculate(){
 $('pageError').hidden=true;setView('analysis');setCalculating(true);
 try{const job=await api('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});pollJob(job.id);}
 catch(error){setCalculating(false);showError(error.message);}
}
async function pollJob(id, failures=0){
 try{
  const job=await api(`/api/jobs/${id}`);
  if(job.status==='running'){setTimeout(()=>pollJob(id),900);return;}
  setCalculating(false);
  if(job.status==='error'){showError(job.message);return;}
  state.rules=(await api('/api/config')).rules;renderTeasers();renderMethod();
  await showResults();toast('Рейтинг готов. Нажми на пассажира, чтобы увидеть объяснение.');
 }catch(error){if(failures<3){setTimeout(()=>pollJob(id,failures+1),1800);}else{setCalculating(false);showError(error.message);}}
}
async function showResults(){
 state.showResults=true;$('analysisView').classList.add('compact');$('resultsSection').hidden=false;$('beforeResults').hidden=true;
 await loadResults();
 if(state.view==='analysis')$('resultsSection').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
}
async function loadResults(){
 state.listController?.abort();state.listController=new AbortController();
 const params=new URLSearchParams({q:state.query,filter:state.filter,offset:state.offset,limit:state.limit,sort:state.sort});
 $('peopleRows').setAttribute('aria-busy','true');
 try{
  const result=await api(`/api/results?${params}`,{signal:state.listController.signal});
  state.total=result.total;
  $('resultTotal').textContent=number(result.summary.people);
  $('summaryStrip').innerHTML=[['name',result.summary.people,'профилей в готовой базе'],['spark',result.summary.with_signals,'профилей с сигналами'],['route',result.summary.identity_review,'связей требуют проверки']].map(([symbol,value,label])=>`<div class="summary-item"><span class="summary-icon">${icon(symbol,18)}</span><div><strong>${number(value)}</strong><span class="summary-label">${label}</span></div></div>`).join('');
  $('peopleRows').innerHTML=result.items.map((person,index)=>{
   const tags=person.triggered_criteria.slice(0,2).map(id=>`<span class="signal-chip">${escape(byId[id]?.short||id)}</span>`).join('');
   return `<tr data-person="${person.person_id}"><td>${state.offset+index+1}</td><td><div class="person-cell"><span class="person-avatar">${escape(initials(person.name))}</span><div style="min-width:0"><button class="person-name" data-person="${person.person_id}">${escape(person.name)}</button><span class="person-id">ID ${person.person_id}${person.identity_resolved===false?'<span class="identity-dot" title="Сопоставление между источниками не подтверждено"></span>':''}</span></div></div></td><td><div class="score-value">${person.score==null?'—':number(person.score)}<small>${person.score==null?'':'/ 100'}</small></div><div class="score-track"><span style="width:${person.score??0}%"></span></div></td><td class="signal-column"><div class="signal-chips">${tags||'<span class="signal-clear">Без срабатываний</span>'}${person.triggered_criteria.length>2?`<span class="signal-extra">+${person.triggered_criteria.length-2}</span>`:''}</div></td><td class="row-arrow-cell"><span class="row-chevron">${icon('chevron',14)}</span></td></tr>`;
  }).join('');
  $('resultsEmpty').hidden=result.items.length>0;$('resultsEmpty').textContent='Ничего не найдено. Попробуй другое имя, ID или фильтр.';
  $('paginationLabel').textContent=result.total?`${number(state.offset+1)}–${number(Math.min(state.offset+state.limit,result.total))} из ${number(result.total)}`:'0 результатов';
  $('pageNumber').textContent=number(Math.floor(state.offset/state.limit)+1);
  $('previousPage').disabled=state.offset===0;$('nextPage').disabled=state.offset+state.limit>=result.total;
 }catch(error){if(error.name!=='AbortError')showError(error.message);}
 finally{$('peopleRows').setAttribute('aria-busy','false');}
}
function modalTop(){return `<div class="dialog-topbar"><span>${icon('name',16)} Карточка пассажира</span><button class="icon-button" data-close-dialog aria-label="Закрыть карточку">${icon('close')}</button></div>`;}
async function openPerson(id){
 state.personController?.abort();state.personController=new AbortController();state.person=null;
 $('personContent').innerHTML=modalTop()+`<div class="dialog-loading"><span class="loading-spinner"></span>Собираем понятное объяснение…</div>`;
 if(!$('personDialog').open)$('personDialog').showModal();
 try{
  const card=await api(`/api/people/${id}`,{signal:state.personController.signal});state.person=card;renderPerson(card);
 }catch(error){if(error.name!=='AbortError')$('personContent').innerHTML=modalTop()+`<div class="dialog-error">${escape(error.message)}<br><button class="text-button" data-retry-person="${id}">Попробовать ещё раз ↗</button></div>`;}
}
function renderPerson(card){
 const assessment=card.assessment, person=card.person||{}, f=card.features;
 const rawName=person.name_forum||person.name_sirena||person.name_pointz||`Профиль № ${f.person_id}`;
 const mainName=String(rawName).split(/\s*[;|]\s*/)[0];
 const score=assessment.score;
 const kinds={card:'Связь по картам',flight_match:'Связь по перелётам',forum_profile:'Профиль Forum',sirena_doc:'Документ Sirena'};
 const criterionList=[...assessment.criteria].sort((a,b)=>(a.triggered===true?0:a.triggered===false?1:2)-(b.triggered===true?0:b.triggered===false?1:2));
 $('personContent').innerHTML=modalTop()+`<header class="person-header"><span class="person-avatar">${escape(initials(mainName))}</span><div class="person-header-main"><h2 id="personDialogTitle">${escape(mainName)}</h2><div class="profile-label">Профиль № ${f.person_id}<span class="profile-kind">${escape(kinds[assessment.identity_kind]||'Запись из витрины')}</span></div></div></header><section class="person-score-card"><div class="score-dial"><svg viewBox="0 0 90 90" aria-hidden="true"><circle cx="45" cy="45" r="38" fill="none" stroke="#EAD7E3" stroke-width="5"/><circle cx="45" cy="45" r="38" fill="none" stroke="#B56B96" stroke-width="5" stroke-linecap="round" stroke-dasharray="${(score||0)*2.3876} 238.76"/></svg><span>${score==null?'—':number(score)}<small>${score==null?'':'%'}</small></span></div><div class="score-card-copy"><h3>Индекс по правилам</h3><p>${score==null?`Не хватает данных для полной оценки. Диапазон: ${assessment.score_min}–${assessment.score_max} баллов.`:`${assessment.triggered_criteria.length} из 10 критериев добавили ${number(score)} баллов из 100.`}<br>Это приоритет проверки, а не вероятность шпиона.</p></div></section>${assessment.needs_identity_review?`<aside class="identity-note">${icon('info',16)}<span>Сопоставление между источниками не подтверждено. Признаки посчитаны по имеющейся истории; сам этот статус баллов не добавляет.</span></aside>`:''}<div class="drawer-body"><div class="drawer-section-title"><h3>Почему получился такой результат</h3><span>Нажми на признак ↓</span></div><div id="personCriteria">${criterionList.map(criterion=>{
   const meta=byId[criterion.id];if(!meta)return '';
   return `<section class="signal-accordion ${criterion.triggered?'triggered':''}" data-signal="${criterion.id}"><button class="signal-toggle" data-expand="${criterion.id}" aria-expanded="false"><span class="criterion-icon">${icon(meta.icon,18)}</span><span class="signal-toggle-main"><strong>${meta.title}</strong><small>${criterion.triggered===true?'Сработал':criterion.triggered===false?'Не сработал':'Недостаточно данных'}</small></span><span class="signal-contribution">${criterion.points==null?'—':`+${number(criterion.points)}`} баллов</span><span class="chevron">${icon('chevron',14)}</span></button><div class="signal-detail" hidden></div></section>`;
  }).join('')}</div><button class="text-button" data-download-person>${icon('download',14)} Скачать подробное объяснение</button></div>`;
 const first=criterionList.find(item=>item.triggered)||criterionList[0];if(first)expandCriterion(first.id);
}
function evidenceHtml(meta,evidence){
 if(!evidence)return '<p class="empty-evidence">В готовой БД нет отдельного пояснения для этой записи.</p>';
 const fields=Object.entries(evidence).filter(([key,value])=>key.startsWith(meta.evidence)&&value!==null&&value!==''&&!(meta.id==='route_tail'&&key.startsWith('route_tail_rare')));
 if(!fields.length)return '<p class="empty-evidence">Отдельные ссылки для этого критерия не сохранены в витрине.</p>';
 return `<details class="evidence-details"><summary>Исходные ссылки и даты (${fields.length})</summary><div class="evidence-list">${fields.map(([key,value])=>{
  let label=key.includes('from_date')?'Начало окна':key.includes('to_date')?'Конец окна':key.includes('leader')?'Связанные профили':key.includes('skyteam')?'Рейсы SkyTeam':key.includes('forum')?'Записи Forum':key.includes('pointz')?'Записи Pointz':key.includes('sirena')?'Записи Sirena':'Связанные записи';
  const full=String(value), display=full.length>500?full.slice(0,500)+'… (список сокращён)':full;
  return `<div class="evidence-row"><b>${label}</b>${escape(display)}</div>`;
 }).join('')}</div></details>`;
}
function expandCriterion(id){
 const section=$('personCriteria')?.querySelector(`[data-signal="${id}"]`);if(!section||!state.person)return;
 const button=section.querySelector('.signal-toggle'), detail=section.querySelector('.signal-detail');
 const opening=button.getAttribute('aria-expanded')!=='true';
 $('personCriteria').querySelectorAll('.signal-accordion').forEach(other=>{other.querySelector('.signal-toggle').setAttribute('aria-expanded','false');other.querySelector('.signal-detail').hidden=true;other.querySelector('.signal-detail').innerHTML='';});
 if(!opening)return;
 button.setAttribute('aria-expanded','true');detail.hidden=false;
 const meta=byId[id], card=state.person, criterion=card.assessment.criteria.find(item=>item.id===id);
 detail.innerHTML=`<p>${meta.text}</p><div class="facts">${Object.entries(meta.fields).map(([field,label])=>`<div class="fact"><small>${label}</small><strong>${card.features[field]==null?'Нет данных':number(card.features[field])}</strong></div>`).join('')}</div><criterion-explainer criterion="${id}" weight="${criterion.weight}"></criterion-explainer><p class="rule-line">${icon('check',16)}<span>${meta.rule}</span></p><p class="context-note">${meta.note}</p>${evidenceHtml(meta,card.evidence)}`;
}

document.addEventListener('click',event=>{
 const view=event.target.closest('[data-view]');if(view){setView(view.dataset.view);return;}
 const teaser=event.target.closest('[data-criterion-link]');if(teaser){setView('criteria',teaser.dataset.criterionLink);window.scrollTo({top:0,behavior:'smooth'});return;}
 const tab=event.target.closest('[data-criterion-select]');if(tab){setView('criteria',tab.dataset.criterionSelect);return;}
 const filter=event.target.closest('[data-filter]');if(filter){state.filter=filter.dataset.filter;state.offset=0;document.querySelectorAll('[data-filter]').forEach(button=>{const active=button===filter;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});loadResults();return;}
 const person=event.target.closest('[data-person]');if(person){openPerson(Number(person.dataset.person));return;}
 if(event.target.closest('[data-close-dialog]')){$('personDialog').close();return;}
 const retry=event.target.closest('[data-retry-person]');if(retry){openPerson(Number(retry.dataset.retryPerson));return;}
 const expand=event.target.closest('[data-expand]');if(expand){expandCriterion(expand.dataset.expand);return;}
 if(event.target.closest('[data-download-person]')&&state.person){const url=URL.createObjectURL(new Blob([JSON.stringify(state.person,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`profile-${state.person.features.person_id}-explanation.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
});
$('personDialog').addEventListener('close',()=>{state.personController?.abort();$('personContent').innerHTML='';state.person=null;});
$('personDialog').addEventListener('click',event=>{if(event.target===$('personDialog')){const bounds=$('personDialog').getBoundingClientRect();if(event.clientX<bounds.left||event.clientX>bounds.right)$('personDialog').close();}});
$('calculateButton').addEventListener('click',calculate);
$('searchInput').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.query=$('searchInput').value;state.offset=0;loadResults();},250);});
$('previousPage').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-state.limit);loadResults();});
$('nextPage').addEventListener('click',()=>{state.offset+=state.limit;loadResults();});
$('sortButton').addEventListener('click',()=>{state.sort=state.sort==='score'?'score_asc':'score';$('sortButton').querySelector('span').textContent=state.sort==='score'?'↓':'↑';state.offset=0;loadResults();});
$('menuButton').addEventListener('click',()=>{const open=document.querySelector('.sidebar').classList.toggle('open');$('menuButton').setAttribute('aria-expanded',String(open));});
document.addEventListener('click',event=>{if(!event.target.closest('.sidebar')&&!event.target.closest('#menuButton')){document.querySelector('.sidebar').classList.remove('open');$('menuButton').setAttribute('aria-expanded','false');}});
window.addEventListener('hashchange',()=>{const [view,criterion]=location.hash.slice(1).split('/');setView(view||'analysis',byId[criterion]?criterion:undefined);});
const duckStyles=document.createElement('style');duckStyles.textContent=duckMotionCss;document.head.append(duckStyles);
$('brandDuck').innerHTML=duckSvg({width:35});$('academyDuck').innerHTML=duckSvg({look:true,width:83});$('heroArt').innerHTML=heroArtwork();fillIcons();
try{
 state.rules=(await api('/api/config')).rules;
 renderTeasers();renderMethod();
 const [view,criterion]=location.hash.slice(1).split('/');setView(view||'analysis',byId[criterion]?criterion:undefined);
 await loadStatus();
}catch(error){showError('Интерфейс открыт, но сервер данных недоступен. Запустите приложение командой serve.');}
