import {byId, icon} from '../data/criteria.js';
import {duckSvg, duckMotionCss} from './duck-art.js';

const defaults = {
 high_freq:{flights:8}, spike:{previous:3,current:8}, route_gap:{gaps:4},
 quick_return:{days:1,repeats:1}, flight_conflict:{conflict:1}, name_conflict:{extras:3},
 doc_conflict:{same:1,documents:2}, card_multi:{owners:2}, route_tail:{delay:3,repeats:3},
 route_tail_rare:{delay:3,observations:4},
};
const controls = {
 high_freq:[['flights','Рейсов за 30 дней',0,16]],
 spike:[['previous','В предыдущие 30 дней',0,12],['current','В последние 30 дней',0,24]],
 route_gap:[['gaps','Разрывов в истории',0,7]],
 quick_return:[['days','Дней между рейсами',0,5],['repeats','Зеркальных пар рейсов',0,4]],
 flight_conflict:[['conflict','Сведения источников', [['0','Совпадают'],['1','Различаются']]]],
 name_conflict:[['extras','Написаний сверх первого',0,5]],
 doc_conflict:[['same','Типы документов', [['1','Одинаковый тип'],['0','Разные типы']]],['documents','Разных документов',1,3]],
 card_multi:[['owners','Профилей на одной карте',1,4]],
 route_tail:[['delay','Задержка, дней',0,10],['repeats','Повторений маршрута',1,5]],
 route_tail_rare:[['delay','Задержка, дней',0,10],['observations','Наблюдений направления',4,12]],
};
function status(id, s) {
 switch(id){
  case 'high_freq':return s.flights>=8;
  case 'spike':return s.previous===0?null:s.current>=5 && s.current>=2*s.previous;
  case 'route_gap':return s.gaps>3;
  case 'quick_return':return s.days<=1 && s.repeats>0;
  case 'flight_conflict':return !!s.conflict;
  case 'name_conflict':return s.extras>2;
  case 'doc_conflict':return !!s.same && s.documents>1;
  case 'card_multi':return s.owners>=2;
  case 'route_tail':return s.delay>=1&&s.delay<=7&&s.repeats>=2;
  case 'route_tail_rare':return s.delay>=1&&s.delay<=7&&s.observations<=4;
 }
}
function narrative(id,s){
 switch(id){
  case 'high_freq':return `${s.flights} рейсов в одном 30-дневном окне`;
  case 'spike':return s.previous?`${s.previous} → ${s.current} рейсов за соседние периоды`:'Нет предыстории для сравнения';
  case 'route_gap':return s.gaps?`Прилёт в B, следующий вылет из C · разрывов: ${s.gaps}`:'Прилёт и следующий вылет стыкуются';
  case 'quick_return':return `A → B → A · между рейсами ${s.days} дн.`;
  case 'flight_conflict':return s.conflict?'Одинаковые дата и рейс, но разные аэропорты назначения':'Источники описывают один маршрут';
  case 'name_conflict':return `${s.extras+1} написаний · «лишних» вариантов: ${s.extras}`;
  case 'doc_conflict':return s.same?`${s.documents} разных номера одного типа`:'Документы разных типов — это обычная комбинация';
  case 'card_multi':return `Одна бонусная карта связана с ${s.owners} профилями`;
  case 'route_tail':return `${s.repeats} повторения · задержка ${s.delay} дн. · направление: 40 наблюдений`;
  case 'route_tail_rare':return `2 повторения · задержка ${s.delay} дн. · направление: ${s.observations} наблюдений`;
 }
}
const plane = `<path d="m-15 0 12 3 16-11 3 3-13 12 3 12-4 1-7-9-8 2-2-2 2-8-8-7z" fill="#AF527E"/>`;
function routeGapScene(gaps){
 const duck=duckSvg({width:65}).replace('<svg ','<svg x="-32" y="-62" ');
 const flight=(className,path,keyPoints,keyTimes,opacity,decoration='')=>`<g class="${className}">${duck}${decoration}<animateMotion dur="9s" repeatCount="indefinite" calcMode="linear" keyPoints="${keyPoints}" keyTimes="${keyTimes}" path="${path}"/><animate attributeName="opacity" dur="9s" repeatCount="indefinite" values="${opacity}" keyTimes="0;.34;.42;.51;.57;.88;.96;1"/></g>`;
 const portal=(x,y,arrival)=>`<circle class="teleport-ring" cx="${x}" cy="${y-25}" r="12" fill="none" stroke="#C18AAA" stroke-width="2" stroke-dasharray="3 5" opacity="0"><animate attributeName="r" dur="9s" repeatCount="indefinite" values="12;12;32;40;40" keyTimes="${arrival?'0;.45;.52;.60;1':'0;.32;.40;.48;1'}"/><animate attributeName="opacity" dur="9s" repeatCount="indefinite" values="0;0;.85;0;0" keyTimes="${arrival?'0;.45;.52;.60;1':'0;.32;.40;.48;1'}"/></circle>`;
 const labels=`<g fill="#857080" font-family="Segoe UI,Arial,sans-serif" font-size="12" text-anchor="middle"><text x="65" y="190">A · вылет</text><text x="240" y="34">B · прилёт</text>${gaps?'<text x="365" y="197">C · новый вылет</text>':''}<text x="540" y="34">${gaps?'D':'C'} · прилёт</text></g>`;
 const nextPath=gaps?'M365 155Q440 60 540 105':'M240 105Q390 25 540 105';
 const firstPath='M65 150Q140 50 240 105';
 const questions=`<g class="teleport-questions" transform="translate(0 -91)" opacity="0"><rect x="-25" y="-20" width="50" height="31" rx="14" fill="#FFF" stroke="#EAD5E2"/><path d="m-5 10 5 7 5-7" fill="#FFF"/><text x="0" y="2" fill="#AF638B" font-family="Segoe UI,Arial,sans-serif" font-size="22" font-weight="600" text-anchor="middle">??</text><animate attributeName="opacity" dur="9s" repeatCount="indefinite" values="0;0;1;1;0;0" keyTimes="0;.51;.56;.67;.73;1"/><animateTransform attributeName="transform" type="translate" dur="9s" repeatCount="indefinite" values="0 -86;0 -86;0 -94;0 -94;0 -100;0 -100" keyTimes="0;.51;.56;.67;.73;1"/></g>`;
 return `<svg class="scene-svg route-gap-scene" viewBox="0 0 600 220" role="img" aria-label="${gaps?'Уточка летит из A в B, исчезает и появляется в C с двумя вопросиками, затем летит в D':'Уточка летит из A через B в C без разрывов'}"><path d="${firstPath}" class="route"/><path d="${nextPath}" class="route"/>${gaps?'<path d="M240 105Q300 110 365 155" class="gap"/>':''}<circle cx="65" cy="150" r="7" class="node"/><circle cx="240" cy="105" r="7" class="node"/><circle cx="540" cy="105" r="7" class="node"/>${gaps?'<circle cx="365" cy="155" r="7" class="node"/>':''}${labels}${gaps?portal(240,105,false)+portal(365,155,true)+flight('gap-flight-first',firstPath,'0;1;1','0;.34;1','1;1;0;0;0;0;0;0')+flight('gap-flight-next',nextPath,'0;0;0;1;1','0;.51;.64;.88;1','0;0;0;0;1;1;0;0',questions):flight('gap-flight-continuous',firstPath+'Q390 25 540 105','0;1;1','0;.88;1','1;1;1;1;1;1;0;0')}</svg>`;
}
function scene(id,s){
 if(id==='high_freq'){
  const days = new Set(Array.from({length:s.flights},(_,i)=>Math.floor(i*29/Math.max(1,s.flights))));
  return `<div class="calendar-scene"><div class="calendar"><div class="calendar-title">30 дней <span>одно окно</span></div><div class="calendar-days">${Array.from({length:30},(_,i)=>`<div class="day ${days.has(i)?'has-flight':''}"><span>${i+1}</span>${days.has(i)?icon('plane',12):''}</div>`).join('')}</div></div><div class="calendar-buddy">${duckSvg({width:105})}<span class="bubble">${s.flights} рейсов!</span></div></div>`;
 }
 if(id==='spike')return `<div class="bars-scene"><div class="bar-column"><b>${s.previous}</b><div class="bar previous" style="height:${12+s.previous*5}px"></div><span>Раньше</span></div><div class="bar-arrow">${icon('arrow',28)}</div><div class="bar-column"><b>${s.current}</b><div class="bar current" style="height:${12+s.current*5}px"><div class="bar-duck">${duckSvg({width:66})}</div></div><span>Сейчас</span></div></div>`;
 if(id==='route_gap')return routeGapScene(s.gaps);
 if(id==='quick_return')return `<div class="path-labels"><span>A · дома</span><span class="trip-time">Визит: ${s.days} дн.</span><span>B · в гостях</span></div><svg class="scene-svg" viewBox="0 0 600 190" aria-label="Перелёт туда и обратно"><path d="M90 115Q300 -10 510 115" class="route"/><path d="M510 125Q300 215 90 125" class="route return-route"/><circle cx="90" cy="120" r="8" class="node"/><circle cx="510" cy="120" r="8" class="node"/><g>${plane}<animateMotion dur="9s" repeatCount="indefinite" rotate="auto" path="M90 115Q300 -10 510 115Q300 215 90 125"/></g><g transform="translate(250 65)">${duckSvg({width:85})}</g></svg>`;
 if(id==='flight_conflict')return `<div class="tickets-scene"><div class="ticket"><small>ИСТОЧНИК A</small><b>Рейс AA 123</b><div>SVO <span>→</span> CDG</div><em>12 октября · пример</em></div><div class="ticket ${s.conflict?'different':''}"><small>ИСТОЧНИК B</small><b>Рейс AA 123</b><div>SVO <span>→</span> ${s.conflict?'FCO':'CDG'}</div><em>12 октября · пример</em></div><div class="ticket-duck">${duckSvg({look:true,width:74})}</div></div>`;
 if(id==='name_conflict'){
  const names=['ANNA ORLOVA','ANNA ORLOWA','ANNA ORLOFF','A. ORLOVA','ANNA ORLOVА','ANNA ORLОVA'];
  return `<div class="names-scene"><div class="name-tags">${names.slice(0,s.extras+1).map((name,i)=>`<div class="name-tag" style="--i:${i}">${icon('name',16)} ${name}</div>`).join('')}</div><div class="names-duck">${duckSvg({look:true,width:86})}</div><span class="names-caption">Один профиль · несколько написаний</span></div>`;
 }
 if(id==='doc_conflict')return `<div class="passports-scene">${Array.from({length:s.documents},(_,i)=>`<div class="passport ${s.same?'same-type':'other-type'}" style="--i:${i}">${icon('passport',30)}<small>${!s.same&&i?'ЗАГРАН':'ПАСПОРТ РФ'}</small><strong>•••• ${1284+i*211}</strong></div>`).join('')}<div class="passport-duck">${duckSvg({width:67})}</div></div>`;
 if(id==='card_multi'){
  const positions=[[85,45],[440,45],[85,165],[440,165]];
  return `<svg class="scene-svg" viewBox="0 0 600 230" aria-label="Одна карта связана с несколькими профилями">${positions.slice(0,s.owners).map(([x,y])=>`<path d="M300 115L${x+35} ${y+22}" class="connection"/><circle cx="${x+35}" cy="${y+22}" r="34" fill="#FFF"/>${duckSvg({width:62}).replace('<svg ',`<svg x="${x+5}" y="${y-14}" `)}`).join('')}<rect x="215" y="73" width="170" height="100" rx="16" fill="#B65D87"/><circle cx="246" cy="103" r="13" fill="#F5D37D"/><path d="M240 103h13m-7-6v12" stroke="#B65D87" stroke-width="2"/><rect x="238" y="142" width="99" height="5" rx="2" fill="#FFF" opacity=".7"/><rect x="333" y="92" width="27" height="20" rx="4" fill="#E6BDC9"/></svg>`;
 }
 const rare=id==='route_tail_rare';
 const gap=65+s.delay*10;
 return `<div class="chase-labels"><span>${rare?'Редкое направление':'Одно направление'}</span><span>${s.delay} дн. спустя</span></div><svg class="scene-svg chase-svg" viewBox="0 0 600 230" aria-label="Уточка оглядывается, за ней следует уточка в очках">${rare?'<circle cx="310" cy="112" r="90" class="radar-ring"/><circle cx="310" cy="112" r="66" class="radar-ring inner"/><path d="m78 48 4-10 4 10 10 4-10 4-4 10-4-10-10-4z" fill="#EBCB7C"/><path d="m513 64 3-7 3 7 7 3-7 3-3 7-3-7-7-3z" fill="#D8AEC3"/>':''}<path d="M40 191H560" stroke="#DDD0D8" stroke-width="2" stroke-dasharray="5 10"/><g class="chase-pack"><g transform="translate(330 66)">${duckSvg({width:103,look:true})}</g><g transform="translate(${330-gap} 76)">${duckSvg({width:94,spy:true})}</g><g class="look-bubble" transform="translate(394 37)"><rect width="38" height="25" rx="12" fill="#FFF"/><circle cx="12" cy="12" r="2" fill="#9A7F91"/><circle cx="19" cy="12" r="2" fill="#9A7F91"/><circle cx="26" cy="12" r="2" fill="#9A7F91"/></g></g></svg>`;
}

class CriterionExplainer extends HTMLElement {
 constructor(){super();this.attachShadow({mode:'open'});this.paused=matchMedia('(prefers-reduced-motion: reduce)').matches;}
 connectedCallback(){this.idKey=this.getAttribute('criterion')||'route_tail';this.state={...(defaults[this.idKey]||defaults.route_tail)};this.render();}
 render(){
  const criterion=byId[this.idKey];if(!criterion)return;
  const weight=Number(this.getAttribute('weight')||criterion.weight);
  const matched=status(this.idKey,this.state);
  this.shadowRoot.innerHTML=`<style>${styles}${duckMotionCss}</style><section class="explainer ${this.paused?'paused':''}"><div class="demo-heading"><span><i></i> Учебный пример</span><button class="play-button" aria-label="${this.paused?'Включить':'Приостановить'} анимацию">${this.paused?icon('play',15):'<span class="pause-icon">Ⅱ</span>'} ${this.paused?'Продолжить':'Пауза'}</button></div><div class="scene">${scene(this.idKey,this.state)}</div><p class="scene-caption">${narrative(this.idKey,this.state)}</p><div class="controls">${controls[this.idKey].map(([key,label,min,max])=>Array.isArray(min)?`<label>${label}<select data-key="${key}">${min.map(([value,text])=>`<option value="${value}" ${Number(value)===this.state[key]?'selected':''}>${text}</option>`).join('')}</select></label>`:`<label><span>${label}<output>${this.state[key]}</output></span><input data-key="${key}" aria-label="${label}" type="range" min="${min}" max="${max}" value="${this.state[key]}"/></label>`).join('')}</div><div class="outcome ${matched===null?'unknown':matched?'yes':'no'}" aria-live="polite">${icon(matched?'check':'info',17)}<span>${matched===null?'Недостаточно истории для сравнения':matched?`В примере сработало · +${weight} баллов`:'В примере критерий не сработал'}</span></div><p class="demo-footnote">Параметры примера не меняют баллы пассажира.</p></section>`;
  this.shadowRoot.querySelector('.play-button').addEventListener('click',()=>{this.paused=!this.paused;this.applyPause();});
  this.shadowRoot.querySelectorAll('[data-key]').forEach(input=>input.addEventListener(input.tagName==='SELECT'?'change':'input',()=>{
   const key=input.dataset.key, value=Number(input.value);
   this.state[key]=value;
   const output=input.closest('label').querySelector('output');
   if(output)output.textContent=value;
   this.shadowRoot.querySelector('.scene').innerHTML=scene(this.idKey,this.state);
   this.shadowRoot.querySelector('.scene-caption').textContent=narrative(this.idKey,this.state);
   const matched=status(this.idKey,this.state), outcome=this.shadowRoot.querySelector('.outcome');
   outcome.className=`outcome ${matched===null?'unknown':matched?'yes':'no'}`;
   outcome.innerHTML=`${icon(matched?'check':'info',17)}<span>${matched===null?'Недостаточно истории для сравнения':matched?`В примере сработало · +${weight} баллов`:'В примере критерий не сработал'}</span>`;
   this.applyPause();
  }));
  this.applyPause();
 }
 applyPause(){
  this.shadowRoot.querySelector('.explainer')?.classList.toggle('paused',this.paused);
  const button=this.shadowRoot.querySelector('.play-button');
  if(button){button.innerHTML=`${this.paused?icon('play',15):'<span class="pause-icon">Ⅱ</span>'} ${this.paused?'Продолжить':'Пауза'}`;button.setAttribute('aria-label',`${this.paused?'Включить':'Приостановить'} анимацию`);}
  this.shadowRoot.querySelectorAll('svg').forEach(svg=>{if(this.paused)svg.pauseAnimations?.();else svg.unpauseAnimations?.();});
 }
}

const styles=`
:host{display:block;font:14px/1.5 'Segoe UI',Arial,sans-serif;color:#463747}*{box-sizing:border-box}.explainer{background:#FAF5F7;border:1px solid #EDE1E7;border-radius:17px;overflow:hidden}.demo-heading{display:flex;align-items:center;justify-content:space-between;padding:13px 17px 0;gap:10px}.demo-heading>span{display:flex;align-items:center;gap:7px;font-size:11px;letter-spacing:.07em;text-transform:uppercase;font-weight:700;color:#83717F}.demo-heading i{width:5px;height:5px;background:#BC7798;border-radius:50%}.play-button{border:0;background:#FFF;border-radius:8px;min-height:33px;padding:5px 9px;color:#786272;display:flex;align-items:center;gap:5px;font:11px inherit;cursor:pointer}.play-button:focus-visible{outline:2px solid #B75B86;outline-offset:3px}.pause-icon{font-weight:700}.scene{position:relative;min-height:200px;display:grid;align-items:center;padding:5px 18px 0;overflow:hidden}.scene-svg{display:block;width:100%;max-height:220px}.route{fill:none;stroke:#BA7196;stroke-width:3;stroke-linecap:round;stroke-dasharray:5 7}.return-route{stroke:#BFB4C0}.node{fill:#FFF;stroke:#B56D92;stroke-width:3}.gap{fill:none;stroke:#D5A25E;stroke-width:3;stroke-dasharray:4 8;animation:dash 6s linear infinite}.connection{stroke:#CC9DB5;stroke-width:2;stroke-dasharray:5 5;animation:dash 4s linear infinite}.scene-caption{margin:0;padding:0 16px 14px;text-align:center;font-size:12px;color:#796777}.path-labels,.chase-labels{display:flex;justify-content:space-between;gap:7px;color:#857080;font-size:11px;padding:8px 8px 0}.trip-time{color:#9D5A7C;background:#F1E2EA;border-radius:20px;padding:2px 8px}.controls{padding:15px 18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;background:#FFF9FC;border-top:1px solid #EDE1E7}.controls label{font-size:12px;color:#786474;display:flex;flex-direction:column;gap:7px;min-width:0}.controls label>span{display:flex;justify-content:space-between;gap:6px}output{font-weight:700;color:#9C4973}input{width:100%;accent-color:#AD5C85;cursor:pointer}select{font:13px 'Segoe UI',sans-serif;color:#614C5E;border:1px solid #E1D0DB;border-radius:8px;padding:8px;background:#FFF;min-height:38px;width:100%}.outcome{display:flex;align-items:center;gap:7px;margin:0 17px 12px;border-radius:9px;padding:9px 11px;font-size:12px}.yes{background:#EFE2EA;color:#985376}.no{background:#EFEEF2;color:#756F7B}.unknown{background:#F4EDDE;color:#957041}.demo-footnote{font-size:10px;text-align:center;color:#958591;margin:0 16px 13px}.paused *{animation-play-state:paused!important}.calendar-scene{display:flex;align-items:center;justify-content:center;gap:20px;padding:12px 0}.calendar{background:#FFF;border:1px solid #E9DEE4;border-radius:12px;padding:12px;width:285px;box-shadow:0 5px 18px #63415406}.calendar-title{font-size:13px;font-weight:700;display:flex;justify-content:space-between;margin-bottom:9px}.calendar-title span{font-size:10px;font-weight:400;color:#A08B99}.calendar-days{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}.day{height:23px;border-radius:5px;font-size:9px;color:#AD9AA7;padding:2px 4px;display:flex;justify-content:space-between;align-items:center}.day.has-flight{background:#EED5E2;color:#A6547E}.calendar-buddy{position:relative;align-self:flex-end;padding-bottom:12px}.bubble{position:absolute;right:1px;top:-18px;font-size:11px;white-space:nowrap;background:#FFF;padding:5px 9px;border-radius:12px;transform:rotate(6deg);color:#A2748C}.bars-scene{height:205px;display:flex;align-items:flex-end;justify-content:center;gap:35px;padding:30px 18px 0}.bar-column{display:flex;flex-direction:column;align-items:center;gap:5px;min-width:75px}.bar-column b{font-size:21px;font-weight:600}.bar{position:relative;width:70px;border-radius:8px 8px 0 0;min-height:12px;transition:height .35s}.previous{background:#DAD2DE}.current{background:#CC91B0}.bar-column>span{font-size:11px;color:#8A7585}.bar-duck{position:absolute;bottom:100%;left:40px}.bar-arrow{align-self:center;margin-top:35px;color:#C8B8C3}.tickets-scene{position:relative;display:flex;gap:12px;justify-content:center;padding:26px 0 48px}.ticket{display:flex;flex-direction:column;gap:6px;background:#FFF;border:1px solid #E3D7DE;padding:16px 20px;border-radius:12px;transform:rotate(-3deg);min-width:0;box-shadow:0 8px 16px #6D536908}.ticket:nth-child(2){transform:rotate(4deg)}.ticket small{font-size:9px;color:#9B8796;letter-spacing:.1em}.ticket b{font-size:12px;font-weight:500}.ticket>div{font-size:23px;font-weight:600;white-space:nowrap}.ticket div span{color:#BAA8B5;font-size:16px}.ticket em{font-size:9px;font-style:normal;color:#9B8796}.ticket.different{border-color:#CA91AD;background:#FFF8FB}.ticket-duck{position:absolute;bottom:0;left:calc(50% - 30px)}.names-scene{height:205px;position:relative;display:flex;align-items:flex-start;justify-content:center;padding:25px 5px 58px}.name-tags{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;max-width:370px}.name-tag{font-size:10px;background:#FFF;padding:7px 9px;border:1px solid #E6D7E1;border-radius:7px;display:flex;gap:5px;align-items:center;transform:rotate(calc((var(--i) - 2)*1.7deg));animation:float 5s ease-in-out infinite;animation-delay:calc(var(--i)*-.6s)}.names-duck{position:absolute;bottom:14px;left:calc(50% - 43px)}.names-caption{position:absolute;bottom:4px;font-size:10px;color:#9B8495}.passports-scene{position:relative;height:205px;display:flex;gap:12px;align-items:center;justify-content:center;padding-bottom:25px}.passport{height:115px;min-width:94px;padding:13px 11px;display:flex;flex-direction:column;gap:10px;align-items:center;border-radius:4px 9px 9px 4px;box-shadow:inset 5px 0 #00000009,0 6px 10px #6753660A;background:#91647F;color:#F5E4CE;transform:rotate(calc((var(--i) - .5)*8deg))}.passport.other-type:nth-child(2){background:#57756D}.passport small{font-size:8px;letter-spacing:.05em}.passport strong{font-size:10px;letter-spacing:.07em}.passport-duck{position:absolute;bottom:0;right:18%}.chase-svg{overflow:visible}.chase-pack{animation:chase 10s ease-in-out infinite}.look-bubble{animation:bubble 5s ease-in-out infinite}.radar-ring{stroke:#DCC0D1;fill:#F0E0E912;stroke-width:1;stroke-dasharray:3 7;transform-origin:310px 112px;animation:radar 30s linear infinite}.radar-ring.inner{animation-direction:reverse}@keyframes dash{to{stroke-dashoffset:-60}}@keyframes float{50%{translate:0 -4px}}@keyframes chase{0%,100%{transform:translateX(-40px)}50%{transform:translateX(50px)}}@keyframes bubble{0%,25%,70%,100%{opacity:0}34%,56%{opacity:1}}@keyframes radar{to{transform:rotate(360deg)}}@media(max-width:420px){.scene{padding-left:9px;padding-right:9px;min-height:180px}.calendar-scene{gap:0}.calendar{width:235px;padding:9px}.calendar-buddy{width:70px}.calendar-buddy svg{width:75px}.bubble{right:0;font-size:9px}.controls{grid-template-columns:1fr;padding:13px 15px;gap:13px}.ticket{padding:12px 10px}.ticket>div{font-size:19px}.tickets-scene{gap:8px}.passport{min-width:78px}.scene-caption{font-size:11px}.bar-arrow{display:none}.bars-scene{gap:40px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
`;
customElements.define('criterion-explainer',CriterionExplainer);
