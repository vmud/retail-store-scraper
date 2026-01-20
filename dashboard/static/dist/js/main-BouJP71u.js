(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const s of document.querySelectorAll('link[rel="modulepreload"]'))o(s);new MutationObserver(s=>{for(const a of s)if(a.type==="childList")for(const i of a.addedNodes)i.tagName==="LINK"&&i.rel==="modulepreload"&&o(i)}).observe(document,{childList:!0,subtree:!0});function n(s){const a={};return s.integrity&&(a.integrity=s.integrity),s.referrerPolicy&&(a.referrerPolicy=s.referrerPolicy),s.crossOrigin==="use-credentials"?a.credentials="include":s.crossOrigin==="anonymous"?a.credentials="omit":a.credentials="same-origin",a}function o(s){if(s.ep)return;s.ep=!0;const a=n(s);fetch(s.href,a)}})();function te(t={}){let e={...t};const n=new Set,o=new Map;function s(){return e}function a(u){const p=e;typeof u=="function"?e={...e,...u(e)}:e={...e,...u},n.forEach(c=>{try{c(e,p)}catch(g){console.error("State listener error:",g)}}),o.forEach(c=>{c.forEach(({selector:g,callback:v})=>{const b=g(p),B=g(e);if(!ee(b,B))try{v(B,b)}catch(J){console.error("Selector listener error:",J)}})})}function i(u){return n.add(u),()=>n.delete(u)}function r(u,p){const c=u.toString();o.has(c)||o.set(c,new Set);const g={selector:u,callback:p};return o.get(c).add(g),()=>{const v=o.get(c);v&&(v.delete(g),v.size===0&&o.delete(c))}}function l(){a({...t})}return{getState:s,update:a,subscribe:i,subscribeSelector:r,reset:l}}function ee(t,e){if(t===e)return!0;if(t==null||e==null||typeof t!=typeof e)return!1;if(Array.isArray(t)&&Array.isArray(e))return t.length!==e.length?!1:t.every((n,o)=>n===e[o]);if(typeof t=="object"){const n=Object.keys(t),o=Object.keys(e);return n.length!==o.length?!1:n.every(s=>t[s]===e[s])}return!1}const C={verizon:{id:"verizon",name:"Verizon",abbr:"VZ"},att:{id:"att",name:"AT&T",abbr:"AT"},target:{id:"target",name:"Target",abbr:"TG"},tmobile:{id:"tmobile",name:"T-Mobile",abbr:"TM"},walmart:{id:"walmart",name:"Walmart",abbr:"WM"},bestbuy:{id:"bestbuy",name:"Best Buy",abbr:"BB"}},ne={isLoading:!0,error:null,lastUpdate:null,summary:{totalStores:0,activeRetailers:0,totalRetailers:6,overallProgress:0,activeScrapers:0},retailers:{},changes:{new:0,closed:0,modified:0},ui:{configModalOpen:!1,logModalOpen:!1,currentLogRetailer:null,currentLogRunId:null,expandedCards:new Set,changePanelOpen:!1,liveLogEnabled:!1,liveLogPaused:!1,logLineCount:0,logIsActive:!1}},f=te(ne),m={setStatusData(t){const{summary:e,retailers:n}=t;f.update({isLoading:!1,error:null,lastUpdate:Date.now(),summary:{totalStores:e?.total_stores??0,activeRetailers:e?.active_retailers??0,totalRetailers:e?.total_retailers??6,overallProgress:e?.overall_progress??0,activeScrapers:e?.active_scrapers??0},retailers:n||{}})},setError(t){f.update({isLoading:!1,error:t?.message||String(t)})},setLoading(t){f.update({isLoading:t})},toggleConfigModal(t){f.update(e=>({ui:{...e.ui,configModalOpen:t??!e.ui.configModalOpen}}))},openLogModal(t,e){f.update(n=>({ui:{...n.ui,logModalOpen:!0,currentLogRetailer:t,currentLogRunId:e}}))},closeLogModal(){f.update(t=>({ui:{...t.ui,logModalOpen:!1,currentLogRetailer:null,currentLogRunId:null}}))},toggleCardExpansion(t){f.update(e=>{const n=new Set(e.ui.expandedCards);return n.has(t)?n.delete(t):n.add(t),{ui:{...e.ui,expandedCards:n}}})},toggleChangePanel(t){f.update(e=>({ui:{...e.ui,changePanelOpen:t??!e.ui.changePanelOpen}}))},setChanges(t){f.update({changes:t})},setLiveLogEnabled(t){f.update(e=>({ui:{...e.ui,liveLogEnabled:t}}))},setLiveLogPaused(t){f.update(e=>({ui:{...e.ui,liveLogPaused:t}}))},setLogLineCount(t){f.update(e=>({ui:{...e.ui,logLineCount:t}}))},setLogIsActive(t){f.update(e=>({ui:{...e.ui,logIsActive:t}}))},resetLiveLogState(){f.update(t=>({ui:{...t.ui,liveLogEnabled:!1,liveLogPaused:!1,logLineCount:0,logIsActive:!1}}))}},nt="/api";let W=null;async function oe(){if(W)return W;try{const t=await fetch(`${nt}/csrf-token`);if(t.ok)return W=(await t.json()).csrf_token,W}catch(t){console.warn("Failed to fetch CSRF token:",t)}return null}async function Mt(){const t=await oe();return t?{"X-CSRFToken":t}:{}}async function Rt(t,e={}){const n=`${nt}${t}`;let o={};e.method&&e.method!=="GET"&&(o=await Mt());const s={headers:{"Content-Type":"application/json",...o,...e.headers},...e};try{const a=await fetch(n,s);let i;const r=a.headers.get("content-type");if(r&&r.includes("application/json")?i=await a.json():i=await a.text(),!a.ok){const l=new Error(i.error||`HTTP ${a.status}: ${a.statusText}`);throw l.status=a.status,l.data=i,l}return i}catch(a){if(a.status)throw a;const i=new Error(`Network error: ${a.message}`);throw i.isNetworkError=!0,i}}function P(t){return Rt(t,{method:"GET"})}function ot(t,e){return Rt(t,{method:"POST",body:JSON.stringify(e)})}function se(){return P("/status")}function ae(t){return P(`/status/${t}`)}function re(t,e={}){return ot("/scraper/start",{retailer:t,resume:e.resume??!0,incremental:e.incremental??!1,limit:e.limit??null,test:e.test??!1,proxy:e.proxy??null,render_js:e.renderJs??!1,proxy_country:e.proxyCountry??"us",verbose:e.verbose??!1})}function ie(t,e=30){return ot("/scraper/stop",{retailer:t,timeout:e})}function le(t,e={}){return ot("/scraper/restart",{retailer:t,resume:e.resume??!0,timeout:e.timeout??30})}function ce(t,e=10){return P(`/runs/${t}?limit=${e}`)}function de(t,e,n={}){const o=new URLSearchParams;n.tail&&o.append("tail",n.tail),n.offset&&o.append("offset",n.offset);const s=o.toString();return P(`/logs/${t}/${e}${s?"?"+s:""}`)}function ue(){return P("/config")}function fe(t){return ot("/config",{content:t})}function pe(){return P("/export/formats")}async function ge(t,e){const n=`${nt}/export/${t}/${e}`,o=await fetch(n);if(!o.ok){const u=await o.json().catch(()=>({}));throw new Error(u.error||`Export failed: ${o.statusText}`)}const s=o.headers.get("Content-Disposition");let a=`${t}_stores.${e==="excel"?"xlsx":e}`;if(s){const u=s.match(/filename="?([^";\n]+)"?/);u&&(a=u[1])}const i=await o.blob(),r=window.URL.createObjectURL(i),l=document.createElement("a");l.href=r,l.download=a,document.body.appendChild(l),l.click(),document.body.removeChild(l),window.URL.revokeObjectURL(r)}async function At(t,e,n=!0){const o=`${nt}/export/multi`,s=await Mt(),a=await fetch(o,{method:"POST",headers:{"Content-Type":"application/json",...s},body:JSON.stringify({retailers:t,format:e,combine:n})});if(!a.ok){const c=await a.json().catch(()=>({}));throw new Error(c.error||`Export failed: ${a.statusText}`)}const i=a.headers.get("Content-Disposition");let r=`stores_combined.${e==="excel"?"xlsx":e}`;if(i){const c=i.match(/filename="?([^";\n]+)"?/);c&&(r=c[1])}const l=await a.blob(),u=window.URL.createObjectURL(l),p=document.createElement("a");p.href=u,p.download=r,document.body.appendChild(p),p.click(),document.body.removeChild(p),window.URL.revokeObjectURL(u)}const L={getStatus:se,getRetailerStatus:ae,startScraper:re,stopScraper:ie,restartScraper:le,getRunHistory:ce,getLogs:de,getConfig:ue,updateConfig:fe,getExportFormats:pe,exportRetailer:ge,exportMulti:At};function A(t,e={}){if(t==null||isNaN(t))return"—";const{decimals:n=0,prefix:o="",suffix:s=""}=e,a=t.toLocaleString("en-US",{minimumFractionDigits:n,maximumFractionDigits:n});return`${o}${a}${s}`}function It(t,e=1){return t==null||isNaN(t)?"0%":`${t.toFixed(e)}%`}function me(){const t=new Date,e=t.getUTCHours().toString().padStart(2,"0"),n=t.getUTCMinutes().toString().padStart(2,"0"),o=t.getUTCSeconds().toString().padStart(2,"0");return`${e}:${n}:${o} UTC`}function ve(t){if(!t)return"";const e=Date.now(),n=Math.floor((e-new Date(t).getTime())/1e3);if(n<5)return"just now";if(n<60)return`${n} seconds ago`;if(n<3600){const s=Math.floor(n/60);return`${s} minute${s>1?"s":""} ago`}if(n<86400){const s=Math.floor(n/3600);return`${s} hour${s>1?"s":""} ago`}const o=Math.floor(n/86400);return`${o} day${o>1?"s":""} ago`}function z(t,e,n,o=500,s=A){if(!t)return;const a=e||0,i=n||0,r=i-a;if(r===0){t.textContent=s(i);return}const l=performance.now();function u(p){const c=p-l,g=Math.min(c/o,1),v=1-Math.pow(1-g,3),b=Math.round(a+r*v);t.textContent=s(b),g<1?requestAnimationFrame(u):t.textContent=s(i)}requestAnimationFrame(u)}function d(t){if(!t)return"";const e=document.createElement("div");return e.textContent=t,e.innerHTML}let Y=null;function _t(t,e){const{activeScrapers:n,activeRetailers:o,totalRetailers:s,overallProgress:a}=e,i=n>0?`${n} ACTIVE`:"ALL IDLE",r=o-n;t.innerHTML=`
    <div class="status-indicator ${n>0?"status-indicator--active":"status-indicator--idle"}">
      <span class="status-indicator__dot"></span>
      <span>${i}</span>
    </div>
    ${r>0?`
      <div class="status-indicator status-indicator--idle">
        <span class="status-indicator__dot"></span>
        <span>${r} IDLE</span>
      </div>
    `:""}
    <div class="progress" style="width: 200px; margin-left: var(--space-4);">
      <div class="progress__fill ${n>0?"progress__fill--live":"progress__fill--done"}"
           style="width: ${a}%"></div>
    </div>
    <span style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--text-muted); margin-left: var(--space-2);">
      ${a.toFixed(1)}%
    </span>
  `}function St(){const t=document.getElementById("current-time");t&&(t.textContent=me())}function he(){const t=document.getElementById("header-status"),e=document.getElementById("config-btn");f.subscribe(o=>{t&&_t(t,o.summary)}),e&&e.addEventListener("click",()=>{m.toggleConfigModal(!0)}),St(),Y=setInterval(St,1e3);const n=f.getState();t&&_t(t,n.summary)}function ye(){Y&&(clearInterval(Y),Y=null)}const be={init:he,destroy:ye};let R={stores:0,requests:0},E=null,S=null;function xe(t){if(t<0||!Number.isFinite(t))return"00:00:00";const e=Math.floor(t/3600),n=Math.floor(t%3600/60),o=Math.floor(t%60);return`${e.toString().padStart(2,"0")}:${n.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`}function $t(){const t=document.getElementById("metric-duration");if(t)if(E){const e=Math.floor((Date.now()-E)/1e3);t.textContent=xe(e)}else t.textContent="00:00:00"}function we(t){let e=0,n=0,o=0;return Object.values(t).forEach(s=>{const i=(s.progress?.text||"").match(/^([\d,]+)/);i&&(e+=parseInt(i[1].replace(/,/g,""),10)||0),s.status==="running"&&o++;const r=s.stats||{};if(r.stat3_value&&r.stat3_value!=="—"){const l=parseInt(String(r.stat3_value).replace(/,/g,""),10);isNaN(l)||(n+=l)}}),{stores:e,requests:n,activeRetailers:o}}function Ct(t){const{retailers:e,summary:n}=t,o=we(e),s=n.activeScrapers>0;if(s&&!E)E=Date.now(),S||(S=setInterval($t,1e3));else if(!s&&E){E=null,S&&(clearInterval(S),S=null);const l=document.getElementById("metric-duration");l&&(l.textContent="00:00:00")}const a=document.getElementById("metric-stores");a&&o.stores!==R.stores&&z(a,R.stores,o.stores,500,l=>A(l));const i=document.getElementById("metric-requests");i&&o.requests!==R.requests&&z(i,R.requests,o.requests,500,l=>A(l)),$t();const r=document.getElementById("metric-rate");if(r)if(s&&E&&o.stores>0){const l=Math.max(1,(Date.now()-E)/1e3),u=(o.stores/l).toFixed(1);r.textContent=`${u}/sec`}else r.textContent="—/sec";a&&(s?a.classList.add("metric__value--highlight"):a.classList.remove("metric__value--highlight")),R={stores:o.stores,requests:o.requests,duration:0,rate:0}}function Le(){f.subscribe(t=>{Ct(t)}),Ct(f.getState())}function Ee(){R={stores:0,requests:0,duration:0,rate:0},E=null,S&&(clearInterval(S),S=null)}const _e={init:Le,destroy:Ee},Se=5e3,V=new Map;let $e=0;function Dt(){let t=document.getElementById("toast-container");return t||(t=document.createElement("div"),t.id="toast-container",t.style.cssText=`
      position: fixed;
      top: var(--space-4);
      right: var(--space-4);
      z-index: var(--z-toast);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
      pointer-events: none;
    `,document.body.appendChild(t)),t}function Ce(t,e,n){const o=document.createElement("div");o.id=`toast-${n}`,o.className="toast toast-enter",o.setAttribute("role","alert"),o.setAttribute("aria-live","polite");let s="";switch(e){case"success":s="✓";break;case"error":s="✕";break;case"warning":s="!";break;default:s="i"}o.innerHTML=`
    <span class="toast__icon">${s}</span>
    <span class="toast__message">${Be(t)}</span>
    <button class="toast__close" aria-label="Dismiss">&times;</button>
  `,o.style.cssText=`
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--surface);
    border: var(--border-width) solid var(--border);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
    box-shadow: var(--shadow-lg);
    pointer-events: auto;
    max-width: 400px;
    animation: slide-in-right var(--duration-slow) var(--ease-spring) forwards;
  `;const a=o.querySelector(".toast__icon");if(a)switch(a.style.cssText=`
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--text-xs);
      font-weight: var(--weight-bold);
      flex-shrink: 0;
    `,e){case"success":a.style.background="rgba(34, 197, 94, 0.2)",a.style.color="var(--signal-live)",o.style.borderColor="var(--signal-live)";break;case"error":a.style.background="rgba(239, 68, 68, 0.2)",a.style.color="var(--signal-fail)",o.style.borderColor="var(--signal-fail)";break;case"warning":a.style.background="rgba(234, 179, 8, 0.2)",a.style.color="var(--signal-warn)",o.style.borderColor="var(--signal-warn)";break;default:a.style.background="rgba(59, 130, 246, 0.2)",a.style.color="var(--signal-done)",o.style.borderColor="var(--signal-done)"}const i=o.querySelector(".toast__message");i&&(i.style.cssText="flex: 1; word-break: break-word;");const r=o.querySelector(".toast__close");return r&&(r.style.cssText=`
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: var(--text-lg);
      cursor: pointer;
      padding: 0;
      line-height: 1;
      transition: color var(--duration-fast) var(--ease-out);
    `,r.addEventListener("click",()=>{st(n)}),r.addEventListener("mouseenter",()=>{r.style.color="var(--text-primary)"}),r.addEventListener("mouseleave",()=>{r.style.color="var(--text-muted)"})),o}function Be(t){if(!t)return"";const e=document.createElement("div");return e.textContent=t,e.innerHTML}function y(t,e="info",n=Se){const o=Dt(),s=++$e,a=Ce(t,e,s);if(o.appendChild(a),V.set(s,{element:a,timeoutId:null}),n>0){const i=setTimeout(()=>{st(s)},n);V.get(s).timeoutId=i}return s}function st(t){const e=V.get(t);if(!e)return;const{element:n,timeoutId:o}=e;o&&clearTimeout(o),n.style.animation="slide-out-right var(--duration-normal) var(--ease-out) forwards",setTimeout(()=>{n.remove(),V.delete(t)},300)}function Ot(){V.forEach((t,e)=>{st(e)})}function Te(t){return y(t,"success")}function ke(t){return y(t,"error")}function Me(t){return y(t,"warning")}function Re(t){return y(t,"info")}function Ae(){Dt()}function Ie(){Ot()}const T={init:Ae,destroy:Ie,showToast:y,dismissToast:st,dismissAllToasts:Ot,showSuccess:Te,showError:ke,showWarning:Me,showInfo:Re},De={verizon:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M1.734 0L0 3.82l9.566 20.178L14.69 14.1 22.136.002h-3.863l-4.6 9.2-3.462-6.934H3.467L6.2 8.2l3.366 6.733L4.35 3.82l1.25-2.5H1.734z"/></svg>',att:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4c-4.4 0-8 3.6-8 8s3.6 8 8 8c1.8 0 3.5-.6 4.9-1.6L12 12V4z"/></svg>',target:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2.5"/></svg>',tmobile:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 6h20v3H2V6zm7 5h6v10h-2v-8h-2v8H9V11z"/></svg>',walmart:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7h-4.8L12 2zm0 20l-2.4-7h4.8L12 22zm-10-10l7-2.4v4.8L2 12zm20 0l-7 2.4v-4.8L22 12zM4.9 4.9l6.2 3.6-2.4 2.4-3.8-6zm14.2 0l-3.6 6.2-2.4-2.4 6-3.8zM4.9 19.1l3.6-6.2 2.4 2.4-6 3.8zm14.2 0l-6.2-3.6 2.4-2.4 3.8 6z"/></svg>',bestbuy:'<svg viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 8h4v3H7V8zm0 5h4v3H7v-3zm6-5h4v3h-4V8zm0 5h4v3h-4v-3z"/></svg>'};let ut=!1;const x=new Map,w=new Map;let F=null;function Oe(t){if(t<0||!Number.isFinite(t))return"00:00:00";const e=Math.floor(t/3600),n=Math.floor(t%3600/60),o=Math.floor(t%60);return`${e.toString().padStart(2,"0")}:${n.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`}function Pe(){const t=Date.now();x.forEach((e,n)=>{const o=document.querySelector(`.retailer-card[data-retailer="${n}"] [data-field="duration"]`);if(o){const s=Math.floor((t-e)/1e3);o.textContent=Oe(s)}})}function Pt(t,e){const n=w.get(t);return n==="starting"&&e==="running"?(w.delete(t),"running"):n==="stopping"&&e!=="running"?(w.delete(t),e):n||e}function ft(t){return{running:"running",starting:"starting",stopping:"stopping",complete:"complete",pending:"pending",disabled:"disabled",error:"error",failed:"error"}[t]||"pending"}function pt(t){return{running:"SCRAPING",starting:"STARTING",stopping:"STOPPING",complete:"READY",pending:"READY",disabled:"DISABLED",error:"ERROR",failed:"ERROR"}[t]||"READY"}function qt(t){if(!t||t.length===0)return"—";const e=t.find(s=>s.status==="in_progress");if(e)return e.name;if(t.every(s=>s.status==="complete")&&t.length>0)return"✓ All phases";const o=t.find(s=>s.status==="pending");return o?o.name:"—"}function Nt(t){if(!t)return"—";const e=t.match(/^([\d,]+)/);return e?e[1]:"—"}function qe(t,e){const n=C[t];if(!n)return"";const o=e.status||"pending",s=Pt(t,o),a=ft(s),i=pt(s),r=e.progress?.percentage||0,l=e.progress?.text||"No data",u=Nt(l),p=e.phases||[],c=qt(p),v=(e.stats||{}).stat2_value||"—",b=s==="running"||s==="starting",B=De[t]||"";return`
    <div class="retailer-card retailer-card--${t} card-enter" data-retailer="${d(t)}">
      <div class="retailer-card__header">
        <div class="retailer-card__identity">
          <div class="retailer-card__accent"></div>
          <div class="retailer-card__logo">${B}</div>
          <span class="retailer-card__name">${d(n.name)}</span>
        </div>
        <span class="retailer-card__status retailer-card__status--${a}" data-field="status">
          ${i}
        </span>
      </div>

      <div class="retailer-card__body">
        <div class="retailer-card__progress">
          <div class="retailer-card__progress-header">
            <span class="retailer-card__progress-percent" data-field="percent">${It(r)}</span>
            <span class="retailer-card__progress-text" data-field="store-text">${d(u)} stores</span>
          </div>
          <div class="progress ${b?"progress--active":""}" data-field="progress-bar">
            <div class="progress__fill progress__fill--${b?"live":r>=100?"done":"idle"}"
                 data-field="progress-fill"
                 style="width: ${r}%"></div>
          </div>
        </div>

        <div class="retailer-card__stats">
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value" data-field="stores">${d(u)}</div>
            <div class="retailer-card__stat-label">Stores</div>
          </div>
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value" data-field="duration">${d(v)}</div>
            <div class="retailer-card__stat-label">Duration</div>
          </div>
        </div>

        <div class="retailer-card__phase" data-field="phase">
          <span class="retailer-card__phase-label">Phase:</span>
          <span data-field="phase-text">${d(c)}</span>
        </div>

        <div class="retailer-card__divider"></div>
      </div>

      <div class="retailer-card__actions" data-field="actions">
        ${Ht(t,s,r)}
      </div>

      <div class="run-history" data-retailer="${d(t)}">
        <button class="run-history__toggle" data-action="toggle-history" data-retailer="${d(t)}">
          ▼ View Run History
        </button>
        <div class="run-history__list" id="history-list-${d(t)}">
          <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
            Click to load history
          </div>
        </div>
      </div>
    </div>
  `}function Ht(t,e,n){const o=e==="running";return e==="disabled"?`
      <button class="btn btn--flex" disabled data-tooltip="Scraper disabled in config">
        <span>DISABLED</span>
      </button>
    `:`
    <button class="btn btn--primary btn--flex"
            data-action="start"
            data-retailer="${d(t)}"
            ${o?"disabled":""}
            data-tooltip="Start scraper">
      <span>▶</span>
      <span>START</span>
    </button>
    <button class="btn btn--danger btn--flex"
            data-action="stop"
            data-retailer="${d(t)}"
            ${o?"":"disabled"}
            data-tooltip="Stop scraper">
      <span>■</span>
      <span>STOP</span>
    </button>
    ${!o&&n>=100?`
      <button class="btn btn--flex"
              data-action="restart"
              data-retailer="${d(t)}"
              data-tooltip="Restart scraper">
        <span>↻</span>
        <span>RESTART</span>
      </button>
    `:""}
    <div class="export-dropdown" data-retailer="${d(t)}">
      <button class="btn btn--flex"
              data-action="toggle-export"
              data-retailer="${d(t)}"
              data-tooltip="Export data">
        <span>↓</span>
        <span>EXPORT</span>
      </button>
      <div class="export-dropdown__menu">
        <button class="export-dropdown__item" data-action="export" data-retailer="${d(t)}" data-format="csv">
          CSV
        </button>
        <button class="export-dropdown__item" data-action="export" data-retailer="${d(t)}" data-format="excel">
          Excel
        </button>
        <button class="export-dropdown__item" data-action="export" data-retailer="${d(t)}" data-format="geojson">
          GeoJSON
        </button>
        <button class="export-dropdown__item" data-action="export" data-retailer="${d(t)}" data-format="json">
          JSON
        </button>
      </div>
    </div>
  `}function Ne(t,e){const n=document.querySelector(`.retailer-card[data-retailer="${t}"]`);if(!n)return;const o=e.status||"pending",s=Pt(t,o),a=ft(s),i=pt(s),r=e.progress?.percentage||0,l=e.progress?.text||"No data",u=Nt(l),p=e.phases||[],c=qt(p);(e.stats||{}).stat2_value;const v=s==="running"||s==="starting",b=n.querySelector('[data-field="status"]');b&&(b.textContent=i,b.className=`retailer-card__status retailer-card__status--${a}`);const B=n.querySelector('[data-field="percent"]');B&&(B.textContent=It(r));const J=n.querySelector('[data-field="store-text"]');J&&(J.textContent=`${u} stores`);const vt=n.querySelector('[data-field="progress-bar"]');vt&&(vt.className=`progress ${v?"progress--active":""}`);const lt=n.querySelector('[data-field="progress-fill"]');lt&&(lt.style.width=`${r}%`,lt.className=`progress__fill progress__fill--${v?"live":r>=100?"done":"idle"}`);const ht=n.querySelector('[data-field="stores"]');ht&&(ht.textContent=u);const yt=n.querySelector('[data-field="duration"]');yt&&(v?x.has(t)||x.set(t,Date.now()):(x.delete(t),yt.textContent="—"));const bt=n.querySelector('[data-field="phase-text"]');bt&&(bt.textContent=c);const q=n.querySelector('[data-field="actions"]');if(q){const Qt=s==="disabled",xt=q.querySelector('[data-action="restart"]'),wt=!Qt&&!v&&r>=100;if(xt&&!wt||!xt&&wt)q.innerHTML=Ht(t,s,r);else{const Lt=q.querySelector('[data-action="start"]'),Et=q.querySelector('[data-action="stop"]');Lt&&(Lt.disabled=v),Et&&(Et.disabled=!v)}}}function Bt(t){const e=document.getElementById("operations-grid");if(!e)return;let n="";Object.keys(C).forEach(o=>{const s=t[o]||{status:"pending"};n+=qe(o,s),s.status==="running"&&!x.has(o)&&x.set(o,Date.now())}),e.innerHTML=n,ut=!0}function He(t){Object.keys(C).forEach(e=>{const n=t[e]||{status:"pending"};Ne(e,n)})}async function ze(t){const e=document.getElementById(`history-list-${t}`);if(e){e.innerHTML=`
    <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
      Loading...
    </div>
  `;try{const n=await L.getRunHistory(t,5);if(!n.runs||n.runs.length===0){e.innerHTML=`
        <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
          No runs found
        </div>
      `;return}e.innerHTML=n.runs.map(o=>{const s=o.run_id||"unknown",a=o.status||"unknown",i=o.started_at?new Date(o.started_at).toLocaleString():"—",r={complete:"live",failed:"fail",canceled:"warn",running:"live"}[a]||"idle";return`
        <div class="run-item">
          <div class="run-item__info">
            <span class="run-item__id">${d(s)}</span>
            <span class="run-item__time">${d(i)}</span>
          </div>
          <div class="run-item__actions">
            <span class="badge badge--${r}">
              ${d(a)}
            </span>
            <button class="btn"
                    data-action="view-logs"
                    data-retailer="${d(t)}"
                    data-run-id="${d(s)}">
              Logs
            </button>
          </div>
        </div>
      `}).join("")}catch{e.innerHTML=`
      <div style="text-align: center; padding: var(--space-4); color: var(--signal-fail);">
        Failed to load run history
      </div>
    `}}}async function zt(t){const e=t.target.closest("[data-action]");if(!e)return;const n=e.dataset.action,o=e.dataset.retailer,s=e.dataset.runId,a=e.dataset.format;switch(n){case"start":await Fe(o);break;case"stop":await je(o);break;case"restart":await Ue(o);break;case"toggle-history":Ve(o);break;case"view-logs":Ge(o,s);break;case"toggle-export":Ke(o);break;case"export":await Je(o,a);break}}function k(t,e){const n=document.querySelector(`.retailer-card[data-retailer="${t}"]`);if(!n)return;const o=n.querySelector('[data-field="status"]');o&&(o.textContent=pt(e),o.className=`retailer-card__status retailer-card__status--${ft(e)}`);const s=e==="running"||e==="starting",a=n.querySelector('[data-action="start"]'),i=n.querySelector('[data-action="stop"]');a&&(a.disabled=s||e==="stopping"),i&&(i.disabled=!s);const r=n.querySelector('[data-field="progress-bar"]');r&&(r.className=`progress ${s?"progress--active":""}`)}async function Fe(t){w.set(t,"starting"),k(t,"starting"),x.set(t,Date.now());try{await L.startScraper(t,{resume:!0}),y(`Started ${C[t]?.name||t} scraper`,"success")}catch(e){w.delete(t),x.delete(t),k(t,"error"),y(`Failed to start scraper: ${e.message}`,"error")}}async function je(t){w.set(t,"stopping"),k(t,"stopping");try{await L.stopScraper(t),x.delete(t),y(`Stopped ${C[t]?.name||t} scraper`,"success")}catch(e){w.delete(t),k(t,"error"),y(`Failed to stop scraper: ${e.message}`,"error")}}async function Ue(t){w.set(t,"stopping"),k(t,"stopping");try{await L.restartScraper(t,{resume:!0}),x.set(t,Date.now()),w.set(t,"starting"),k(t,"starting"),y(`Restarted ${C[t]?.name||t} scraper`,"success")}catch(e){w.delete(t),k(t,"error"),y(`Failed to restart scraper: ${e.message}`,"error")}}function Ve(t){const e=document.querySelector(`.run-history[data-retailer="${t}"]`);if(!e)return;const n=e.classList.toggle("run-history--open"),o=e.querySelector(".run-history__toggle");o&&(o.textContent=n?"▲ Hide Run History":"▼ View Run History"),n&&ze(t)}function Ge(t,e){m.openLogModal(t,e)}function Ke(t){document.querySelectorAll(".export-dropdown--open").forEach(n=>{n.dataset.retailer!==t&&n.classList.remove("export-dropdown--open")});const e=document.querySelector(`.export-dropdown[data-retailer="${t}"]`);e&&e.classList.toggle("export-dropdown--open")}async function Je(t,e){const n=document.querySelector(`.export-dropdown[data-retailer="${t}"]`);n&&n.classList.remove("export-dropdown--open");const o=C[t]?.name||t;try{y(`Exporting ${o} data as ${e.toUpperCase()}...`,"info"),await L.exportRetailer(t,e),y(`${o} exported as ${e.toUpperCase()}`,"success")}catch(s){y(`Export failed: ${s.message}`,"error")}}function We(){const t=document.getElementById("operations-grid");t&&(F||(F=setInterval(Pe,1e3)),f.subscribe(e=>{ut?He(e.retailers):Bt(e.retailers)}),t.addEventListener("click",zt),Bt(f.getState().retailers))}function Ye(){const t=document.getElementById("operations-grid");t&&t.removeEventListener("click",zt),F&&(clearInterval(F),F=null),x.clear(),w.clear(),ut=!1}const Xe={init:We,destroy:Ye};let _={new:0,closed:0,modified:0};function Tt(t){const e=document.getElementById("change-new"),n=document.getElementById("change-closed"),o=document.getElementById("change-modified");e&&t.new!==_.new&&z(e,_.new,t.new,500,s=>`+${A(s)}`),n&&t.closed!==_.closed&&z(n,_.closed,t.closed,500,s=>`-${A(s)}`),o&&t.modified!==_.modified&&z(o,_.modified,t.modified,500,s=>`~${A(s)}`),_={...t}}function Ft(){const t=document.getElementById("change-panel");if(!t)return;const e=t.classList.toggle("change-panel--open");m.toggleChangePanel(e)}function Ze(){const t=document.getElementById("change-panel-toggle"),e=document.getElementById("change-panel");t&&t.addEventListener("click",Ft),f.subscribe(n=>{Tt(n.changes),e&&(n.ui.changePanelOpen?e.classList.add("change-panel--open"):e.classList.remove("change-panel--open"))}),Tt(f.getState().changes)}function Qe(){const t=document.getElementById("change-panel-toggle");t&&t.removeEventListener("click",Ft),_={new:0,closed:0,modified:0}}const tn={init:Ze,destroy:Qe},en=[{value:"json",label:"JSON",description:"Standard JSON format"},{value:"csv",label:"CSV",description:"Comma-separated values"},{value:"excel",label:"Excel",description:"Multi-sheet workbook"},{value:"geojson",label:"GeoJSON",description:"Geographic data format"}];let M="excel",at=!0,G=!1;function jt(){const e=f.getState().retailers||{};return Object.entries(e).filter(([n,o])=>(o.phases||[]).some(a=>a.total>0)).map(([n])=>n)}function O(){const t=document.getElementById("export-panel");if(!t)return;const e=jt(),n=e.length>0;t.innerHTML=`
    <div class="export-panel__header" id="export-panel-toggle">
      <span class="export-panel__title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Export Data
      </span>
      <span class="export-panel__toggle">▼</span>
    </div>
    <div class="export-panel__content">
      <div class="export-panel__body">
        <div class="export-panel__options">
          <div class="export-panel__option-group">
            <label class="export-panel__label">Format</label>
            <div class="export-panel__format-grid">
              ${en.map(o=>`
                <button
                  class="export-panel__format-btn ${M===o.value?"export-panel__format-btn--active":""}"
                  data-format="${o.value}"
                  data-tooltip="${o.description}"
                >
                  ${o.label}
                </button>
              `).join("")}
            </div>
          </div>

          <div class="export-panel__option-group">
            <label class="export-panel__checkbox">
              <input
                type="checkbox"
                id="export-combine"
                ${at?"checked":""}
                ${n?"":"disabled"}
              />
              <span>Combine into single file</span>
            </label>
            <span class="export-panel__hint">
              ${M==="excel"?"Creates multi-sheet workbook (one sheet per retailer)":"Merges all stores with retailer field"}
            </span>
          </div>
        </div>

        <div class="export-panel__actions">
          <div class="export-panel__retailers-info">
            ${n?`<span class="export-panel__count">${e.length}</span> retailers with data`:'<span class="export-panel__no-data">No data available</span>'}
          </div>
          <button
            class="btn btn--primary export-panel__export-btn"
            id="export-all-btn"
            ${!n||G?"disabled":""}
          >
            ${G?'<span class="spinner"></span> Exporting...':"Export All Retailers"}
          </button>
        </div>
      </div>
    </div>
  `,nn()}function nn(){const t=document.getElementById("export-panel-toggle");t&&t.addEventListener("click",Ut),document.querySelectorAll(".export-panel__format-btn").forEach(s=>{s.addEventListener("click",a=>{M=a.target.dataset.format,O()})});const n=document.getElementById("export-combine");n&&n.addEventListener("change",s=>{at=s.target.checked,O()});const o=document.getElementById("export-all-btn");o&&o.addEventListener("click",on)}function Ut(){const t=document.getElementById("export-panel");t&&t.classList.toggle("export-panel--open")}async function on(){const t=jt();if(t.length===0){T.showWarning("No retailers have data to export");return}G=!0,O();try{T.showInfo(`Generating ${M.toUpperCase()} export for ${t.length} retailers...`),await At(t,M,at),T.showSuccess(`Export complete! Downloaded ${M.toUpperCase()} file.`)}catch(e){console.error("Export failed:",e),T.showError(`Export failed: ${e.message}`)}finally{G=!1,O()}}function sn(){O(),f.subscribe(()=>{const t=document.getElementById("export-panel");t&&t.classList.contains("export-panel--open")&&O()})}function an(){const t=document.getElementById("export-panel-toggle");t&&t.removeEventListener("click",Ut),M="excel",at=!0,G=!1}const rn={init:sn,destroy:an};let h=new Set(["ALL"]),X=null,$=[],j=0,I=!1,U=!1;const ln=2e3;async function Vt(){const t=document.getElementById("config-modal"),e=document.getElementById("config-editor"),n=document.getElementById("config-alert");if(!(!t||!e)){t.classList.add("modal-overlay--open"),m.toggleConfigModal(!0),n&&(n.style.display="none"),e.value="Loading configuration...",e.disabled=!0;try{const o=await L.getConfig();e.value=o.content||"",e.disabled=!1}catch(o){e.value="",e.disabled=!1,N(`Failed to load configuration: ${o.message}`,"error")}}}function D(){const t=document.getElementById("config-modal");t&&t.classList.remove("modal-overlay--open"),m.toggleConfigModal(!1)}async function cn(){const t=document.getElementById("config-editor"),e=document.getElementById("config-save");if(!t)return;const n=t.value;if(!n||n.trim().length===0){N("Configuration cannot be empty","error");return}if(!n.includes("retailers:")){N('Configuration must contain "retailers:" key',"error");return}e&&(e.disabled=!0,e.textContent="Saving...");try{const o=await L.updateConfig(n);N(`Configuration saved successfully!
Backup created at: ${o.backup||"unknown"}`,"success"),y("Configuration updated successfully","success"),setTimeout(()=>{D()},2e3)}catch(o){let s=o.message||"Unknown error";o.data?.details&&Array.isArray(o.data.details)&&(s+=`

Details:
`+o.data.details.map(a=>`• ${a}`).join(`
`)),N(`Failed to save configuration:
${s}`,"error")}finally{e&&(e.disabled=!1,e.textContent="Save Configuration")}}function N(t,e="info"){const n=document.getElementById("config-alert");n&&(n.className=`alert alert--${e}`,n.textContent=t,n.style.display="block")}async function Gt(t,e){const n=document.getElementById("log-modal"),o=document.getElementById("log-modal-title"),s=document.getElementById("log-content");if(document.getElementById("log-stats"),!n||!s)return;h=new Set(["ALL"]),Jt(),$=[],j=0,I=!1,U=!1,m.resetLiveLogState();const a=C[t]?.name||t;o&&(o.textContent=`Logs — ${a} — ${e}`),n.classList.add("modal-overlay--open"),m.openLogModal(t,e),s.innerHTML=`
    <div style="text-align: center; padding: var(--space-8); color: var(--text-muted);">
      Loading logs...
    </div>
  `;try{const i=await L.getLogs(t,e);$=(i.content||"").split(`
`).filter(u=>u.trim()).map(u=>Kt(u)),j=i.total_lines||$.length,pn($),gt(),i.is_active?(m.setLogIsActive(!0),m.setLiveLogEnabled(!0),tt(!0),dn(t,e),rt()):tt(!1)}catch(i){s.innerHTML=`
      <div class="alert alert--error">
        Error loading logs: ${d(i.message)}
      </div>
    `}}function dn(t,e){H(),X=setInterval(async()=>{if(U)return;const n=f.getState();if(!n.ui.logModalOpen){H();return}if(!n.ui.liveLogPaused){U=!0;try{const o=await L.getLogs(t,e,{offset:j}),s=f.getState();if(!s.ui.logModalOpen||s.ui.currentLogRetailer!==t||s.ui.currentLogRunId!==e){H();return}if(!o.is_active){H(),m.setLogIsActive(!1),m.setLiveLogEnabled(!1),tt(!1),y("Scraper completed","info");return}if(o.lines>0&&o.total_lines>j){const r=(o.content||"").split(`
`).filter(l=>l.trim()).map(l=>Kt(l));un(r),j=o.total_lines,gt(),I||rt()}}catch(o){console.error("Error fetching live logs:",o)}finally{U=!1}}},ln)}function H(){X&&(clearInterval(X),X=null),U=!1}function un(t){const e=document.getElementById("log-content");if(!e)return;$=[...$,...t];const n=t.map(o=>{const a=h.has("ALL")||h.has(o.level)?"":"hidden",i=o.level.toLowerCase();let r=d(o.raw);return o.timestamp&&(r=r.replace(d(o.timestamp),`<span class="log-timestamp">${d(o.timestamp)}</span>`)),o.level&&(r=r.replace(new RegExp(`\\b${d(o.level)}\\b`),`<span class="log-level">${d(o.level)}</span>`)),`<div class="log-line log-line--${i} log-line--new ${a}" data-level="${d(o.level)}">${r}</div>`}).join("");e.insertAdjacentHTML("beforeend",n),setTimeout(()=>{e.querySelectorAll(".log-line--new").forEach(s=>s.classList.remove("log-line--new"))},500)}function rt(){const t=document.getElementById("log-content");t&&(t.scrollTop=t.scrollHeight)}function tt(t){const e=document.getElementById("live-indicator"),n=document.getElementById("log-live-controls");if(e&&(e.style.display=t?"inline-flex":"none"),n&&(n.style.display=t?"flex":"none"),t){const o=document.getElementById("log-pause-btn");o&&(o.textContent="⏸ Pause",o.classList.remove("btn--paused"))}}function fn(){const e=!f.getState().ui.liveLogPaused;m.setLiveLogPaused(e);const n=document.getElementById("log-pause-btn");n&&(e?(n.textContent="▶ Resume",n.classList.add("btn--paused")):(n.textContent="⏸ Pause",n.classList.remove("btn--paused"),I=!1,rt()))}function gt(){const t=document.getElementById("log-stats"),e=f.getState();if(t){const n=document.querySelectorAll(".log-line:not(.hidden)").length,o=$.length;e.ui.logIsActive?t.textContent=`${n} of ${o} lines (live)`:t.textContent=`${n} of ${o} lines`}m.setLogLineCount($.length)}function et(){H(),m.resetLiveLogState(),tt(!1);const t=document.getElementById("log-modal");t&&t.classList.remove("modal-overlay--open"),m.closeLogModal()}function Kt(t){const e=t.match(/\b(DEBUG|INFO|WARNING|ERROR)\b/),n=e?e[1]:"INFO",o=t.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/),s=o?o[1]:null;return{raw:t,level:n,timestamp:s}}function pn(t){const e=document.getElementById("log-content");if(!e)return;const n=t.map(o=>{const a=h.has("ALL")||h.has(o.level)?"":"hidden",i=o.level.toLowerCase();let r=d(o.raw);return o.timestamp&&(r=r.replace(d(o.timestamp),`<span class="log-timestamp">${d(o.timestamp)}</span>`)),o.level&&(r=r.replace(new RegExp(`\\b${d(o.level)}\\b`),`<span class="log-level">${d(o.level)}</span>`)),`<div class="log-line log-line--${i} ${a}" data-level="${d(o.level)}">${r}</div>`}).join("");e.innerHTML=n||'<div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">No logs found</div>'}function gn(t){t==="ALL"?(h.clear(),h.add("ALL")):(h.delete("ALL"),h.has(t)?h.delete(t):h.add(t),h.size===0&&h.add("ALL")),Jt(),mn()}function Jt(){document.querySelectorAll(".log-filter-btn").forEach(e=>{const n=e.dataset.level;h.has(n)?e.classList.add("active"):e.classList.remove("active")})}function mn(){document.querySelectorAll(".log-line").forEach(e=>{const n=e.dataset.level;h.has("ALL")||h.has(n)?e.classList.remove("hidden"):e.classList.add("hidden")}),gt()}function vn(){const t=document.getElementById("config-btn"),e=document.getElementById("config-modal-close"),n=document.getElementById("config-cancel"),o=document.getElementById("config-save"),s=document.getElementById("config-modal");t&&t.addEventListener("click",Vt),e&&e.addEventListener("click",D),n&&n.addEventListener("click",D),o&&o.addEventListener("click",cn),s&&s.addEventListener("click",c=>{c.target===s&&D()});const a=document.getElementById("log-modal-close"),i=document.getElementById("log-modal"),r=document.getElementById("log-content");a&&a.addEventListener("click",et),i&&i.addEventListener("click",c=>{c.target===i&&et()}),document.querySelectorAll(".log-filter-btn").forEach(c=>{c.addEventListener("click",()=>{gn(c.dataset.level)})});const u=document.getElementById("log-pause-btn"),p=document.getElementById("log-scroll-btn");u&&u.addEventListener("click",fn),p&&p.addEventListener("click",()=>{I=!1,rt()}),r&&r.addEventListener("scroll",()=>{const c=f.getState();if(!c.ui.liveLogEnabled)return;const g=r.scrollHeight-r.scrollTop<=r.clientHeight+50;!g&&!c.ui.liveLogPaused?I=!0:g&&(I=!1)}),f.subscribe(c=>{if(c.ui.logModalOpen&&c.ui.currentLogRetailer&&c.ui.currentLogRunId){const g=document.getElementById("log-modal");g&&!g.classList.contains("modal-overlay--open")&&Gt(c.ui.currentLogRetailer,c.ui.currentLogRunId)}})}function hn(){}const yn={init:vn,destroy:hn,openConfigModal:Vt,closeConfigModal:D,openLogModal:Gt,closeLogModal:et},K=new Map;let it=!0;function Z(t,e,n={}){const o=Yt(t);K.set(o,{callback:e,preventDefault:n.preventDefault??!0,description:n.description||""})}function bn(t){const e=Yt(t);K.delete(e)}function xn(){it=!0}function wn(){it=!1}function Ln(){return it}function Wt(){return Array.from(K.entries()).map(([t,e])=>({key:t,description:e.description}))}function Yt(t){return t.toLowerCase().replace(/\s+/g,"")}function En(t){const e=[];(t.ctrlKey||t.metaKey)&&e.push("ctrl"),t.altKey&&e.push("alt"),t.shiftKey&&e.push("shift");let n=t.key.toLowerCase();return n===" "&&(n="space"),["control","alt","shift","meta"].includes(n)||e.push(n),e.join("+")}function _n(t){const e=t.target.tagName.toLowerCase(),n=t.target.isContentEditable;return e==="input"||e==="textarea"||e==="select"||n}function Xt(t){if(!it||_n(t)&&t.key!=="Escape")return;const e=En(t),n=K.get(e);n&&(n.preventDefault&&t.preventDefault(),n.callback(t))}function Sn(){document.addEventListener("keydown",Xt),Z("escape",()=>{const t=document.getElementById("log-modal");t&&t.classList.contains("modal-overlay--open")&&et();const e=document.getElementById("config-modal");e&&e.classList.contains("modal-overlay--open")&&D()},{description:"Close modal"}),Z("?",()=>{console.log("Keyboard shortcuts:",Wt())},{description:"Show keyboard shortcuts"}),Z("r",()=>{window.dispatchEvent(new CustomEvent("manual-refresh"))},{description:"Refresh data"})}function $n(){document.removeEventListener("keydown",Xt),K.clear()}const Cn={init:Sn,destroy:$n,registerShortcut:Z,unregisterShortcut:bn,enable:xn,disable:wn,isActive:Ln,getShortcuts:Wt},Bn=5e3,Tn=1e4;let Q=null,ct=!1;async function dt(){try{const t=await L.getStatus();return m.setStatusData(t),!0}catch(t){return console.error("Failed to fetch status:",t),m.setError(t),!1}}function mt(){ct||(ct=!0,dt(),Q=setInterval(async()=>{await dt()||(Zt(),setTimeout(()=>{mt()},Tn))},Bn))}function Zt(){ct=!1,Q&&(clearInterval(Q),Q=null)}function kn(){document.hidden?Zt():mt()}function Mn(){dt(),T.showInfo("Refreshing data...")}function Rn(){const t=document.getElementById("footer-timestamp"),e=f.getState();t&&e.lastUpdate&&(t.textContent=ve(e.lastUpdate))}function kt(){console.log("Initializing Retail Scraper Command Center..."),T.init(),be.init(),_e.init(),Xe.init(),tn.init(),rn.init(),yn.init(),Cn.init(),document.addEventListener("visibilitychange",kn),window.addEventListener("manual-refresh",Mn),setInterval(Rn,1e3),mt(),f.subscribe((t,e)=>{t.error&&t.error!==e?.error&&T.showError(`Connection error: ${t.error}`)}),console.log("Dashboard initialized")}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",kt):kt();
