(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const s of document.querySelectorAll('link[rel="modulepreload"]'))o(s);new MutationObserver(s=>{for(const a of s)if(a.type==="childList")for(const i of a.addedNodes)i.tagName==="LINK"&&i.rel==="modulepreload"&&o(i)}).observe(document,{childList:!0,subtree:!0});function n(s){const a={};return s.integrity&&(a.integrity=s.integrity),s.referrerPolicy&&(a.referrerPolicy=s.referrerPolicy),s.crossOrigin==="use-credentials"?a.credentials="include":s.crossOrigin==="anonymous"?a.credentials="omit":a.credentials="same-origin",a}function o(s){if(s.ep)return;s.ep=!0;const a=n(s);fetch(s.href,a)}})();function oe(t={}){let e={...t};const n=new Set,o=new Map;function s(){return e}function a(u){const p=e;typeof u=="function"?e={...e,...u(e)}:e={...e,...u},n.forEach(c=>{try{c(e,p)}catch(v){console.error("State listener error:",v)}}),o.forEach(c=>{c.forEach(({selector:v,callback:h})=>{const b=v(p),M=v(e);if(!se(b,M))try{h(M,b)}catch(Z){console.error("Selector listener error:",Z)}})})}function i(u){return n.add(u),()=>n.delete(u)}function r(u,p){const c=u.toString();o.has(c)||o.set(c,new Set);const v={selector:u,callback:p};return o.get(c).add(v),()=>{const h=o.get(c);h&&(h.delete(v),h.size===0&&o.delete(c))}}function l(){a({...t})}return{getState:s,update:a,subscribe:i,subscribeSelector:r,reset:l}}function se(t,e){if(t===e)return!0;if(t==null||e==null||typeof t!=typeof e)return!1;if(Array.isArray(t)&&Array.isArray(e))return t.length!==e.length?!1:t.every((n,o)=>n===e[o]);if(typeof t=="object"){const n=Object.keys(t),o=Object.keys(e);return n.length!==o.length?!1:n.every(s=>t[s]===e[s])}return!1}const k={verizon:{id:"verizon",name:"Verizon",abbr:"VZ"},att:{id:"att",name:"AT&T",abbr:"AT"},target:{id:"target",name:"Target",abbr:"TG"},tmobile:{id:"tmobile",name:"T-Mobile",abbr:"TM"},walmart:{id:"walmart",name:"Walmart",abbr:"WM"},bestbuy:{id:"bestbuy",name:"Best Buy",abbr:"BB"}},ae={isLoading:!0,error:null,lastUpdate:null,summary:{totalStores:0,activeRetailers:0,totalRetailers:6,overallProgress:0,activeScrapers:0},retailers:{},changes:{new:0,closed:0,modified:0},ui:{configModalOpen:!1,logModalOpen:!1,currentLogRetailer:null,currentLogRunId:null,expandedCards:new Set,changePanelOpen:!1,liveLogEnabled:!1,liveLogPaused:!1,logLineCount:0,logIsActive:!1}},f=oe(ae),g={setStatusData(t){const{summary:e,retailers:n}=t;f.update({isLoading:!1,error:null,lastUpdate:Date.now(),summary:{totalStores:e?.total_stores??0,activeRetailers:e?.active_retailers??0,totalRetailers:e?.total_retailers??6,overallProgress:e?.overall_progress??0,activeScrapers:e?.active_scrapers??0},retailers:n||{}})},setError(t){f.update({isLoading:!1,error:t?.message||String(t)})},setLoading(t){f.update({isLoading:t})},toggleConfigModal(t){f.update(e=>({ui:{...e.ui,configModalOpen:t??!e.ui.configModalOpen}}))},openLogModal(t,e){f.update(n=>({ui:{...n.ui,logModalOpen:!0,currentLogRetailer:t,currentLogRunId:e}}))},closeLogModal(){f.update(t=>({ui:{...t.ui,logModalOpen:!1,currentLogRetailer:null,currentLogRunId:null}}))},toggleCardExpansion(t){f.update(e=>{const n=new Set(e.ui.expandedCards);return n.has(t)?n.delete(t):n.add(t),{ui:{...e.ui,expandedCards:n}}})},toggleChangePanel(t){f.update(e=>({ui:{...e.ui,changePanelOpen:t??!e.ui.changePanelOpen}}))},setChanges(t){f.update({changes:t})},setLiveLogEnabled(t){f.update(e=>({ui:{...e.ui,liveLogEnabled:t}}))},setLiveLogPaused(t){f.update(e=>({ui:{...e.ui,liveLogPaused:t}}))},setLogLineCount(t){f.update(e=>({ui:{...e.ui,logLineCount:t}}))},setLogIsActive(t){f.update(e=>({ui:{...e.ui,logIsActive:t}}))},resetLiveLogState(){f.update(t=>({ui:{...t.ui,liveLogEnabled:!1,liveLogPaused:!1,logLineCount:0,logIsActive:!1}}))}},at="/api";let Q=null;async function re(){if(Q)return Q;try{const t=await fetch(`${at}/csrf-token`);if(t.ok)return Q=(await t.json()).csrf_token,Q}catch(t){console.warn("Failed to fetch CSRF token:",t)}return null}async function It(){const t=await re();return t?{"X-CSRFToken":t}:{}}async function Dt(t,e={}){const n=`${at}${t}`;let o={};e.method&&e.method!=="GET"&&(o=await It());const s={headers:{"Content-Type":"application/json",...o,...e.headers},...e};try{const a=await fetch(n,s);let i;const r=a.headers.get("content-type");if(r&&r.includes("application/json")?i=await a.json():i=await a.text(),!a.ok){const l=new Error(i.error||`HTTP ${a.status}: ${a.statusText}`);throw l.status=a.status,l.data=i,l}return i}catch(a){if(a.status)throw a;const i=new Error(`Network error: ${a.message}`);throw i.isNetworkError=!0,i}}function F(t){return Dt(t,{method:"GET"})}function rt(t,e){return Dt(t,{method:"POST",body:JSON.stringify(e)})}function ie(){return F("/status")}function le(t){return F(`/status/${t}`)}function ce(t,e={}){return rt("/scraper/start",{retailer:t,resume:e.resume??!0,incremental:e.incremental??!1,limit:e.limit??null,test:e.test??!1,proxy:e.proxy??"direct",render_js:e.renderJs??!1,proxy_country:e.proxyCountry??"us",verbose:e.verbose??!1})}function de(t,e=30){return rt("/scraper/stop",{retailer:t,timeout:e})}function ue(t,e={}){return rt("/scraper/restart",{retailer:t,resume:e.resume??!0,timeout:e.timeout??30,proxy:e.proxy??"direct"})}function fe(t,e=10){return F(`/runs/${t}?limit=${e}`)}function pe(t,e,n={}){const o=new URLSearchParams;n.tail&&o.append("tail",n.tail),n.offset&&o.append("offset",n.offset);const s=o.toString();return F(`/logs/${t}/${e}${s?"?"+s:""}`)}function ge(){return F("/config")}function me(t){return rt("/config",{content:t})}function ve(){return F("/export/formats")}async function he(t,e){const n=`${at}/export/${t}/${e}`,o=await fetch(n);if(!o.ok){const u=await o.json().catch(()=>({}));throw new Error(u.error||`Export failed: ${o.statusText}`)}const s=o.headers.get("Content-Disposition");let a=`${t}_stores.${e==="excel"?"xlsx":e}`;if(s){const u=s.match(/filename="?([^";\n]+)"?/);u&&(a=u[1])}const i=await o.blob(),r=window.URL.createObjectURL(i),l=document.createElement("a");l.href=r,l.download=a,document.body.appendChild(l),l.click(),document.body.removeChild(l),window.URL.revokeObjectURL(r)}async function Ot(t,e,n=!0){const o=`${at}/export/multi`,s=await It(),a=await fetch(o,{method:"POST",headers:{"Content-Type":"application/json",...s},body:JSON.stringify({retailers:t,format:e,combine:n})});if(!a.ok){const c=await a.json().catch(()=>({}));throw new Error(c.error||`Export failed: ${a.statusText}`)}const i=a.headers.get("Content-Disposition");let r=`stores_combined.${e==="excel"?"xlsx":e}`;if(i){const c=i.match(/filename="?([^";\n]+)"?/);c&&(r=c[1])}const l=await a.blob(),u=window.URL.createObjectURL(l),p=document.createElement("a");p.href=u,p.download=r,document.body.appendChild(p),p.click(),document.body.removeChild(p),window.URL.revokeObjectURL(u)}const w={getStatus:ie,getRetailerStatus:le,startScraper:ce,stopScraper:de,restartScraper:ue,getRunHistory:fe,getLogs:pe,getConfig:ge,updateConfig:me,getExportFormats:ve,exportRetailer:he,exportMulti:Ot};function O(t,e={}){if(t==null||isNaN(t))return"—";const{decimals:n=0,prefix:o="",suffix:s=""}=e,a=t.toLocaleString("en-US",{minimumFractionDigits:n,maximumFractionDigits:n});return`${o}${a}${s}`}function Pt(t,e=1){return t==null||isNaN(t)?"0%":`${t.toFixed(e)}%`}function ye(){const t=new Date,e=t.getUTCHours().toString().padStart(2,"0"),n=t.getUTCMinutes().toString().padStart(2,"0"),o=t.getUTCSeconds().toString().padStart(2,"0");return`${e}:${n}:${o} UTC`}function be(t){if(!t)return"";const e=Date.now(),n=Math.floor((e-new Date(t).getTime())/1e3);if(n<5)return"just now";if(n<60)return`${n} seconds ago`;if(n<3600){const s=Math.floor(n/60);return`${s} minute${s>1?"s":""} ago`}if(n<86400){const s=Math.floor(n/3600);return`${s} hour${s>1?"s":""} ago`}const o=Math.floor(n/86400);return`${o} day${o>1?"s":""} ago`}function U(t,e,n,o=500,s=O){if(!t)return;const a=e||0,i=n||0,r=i-a;if(r===0){t.textContent=s(i);return}const l=performance.now();function u(p){const c=p-l,v=Math.min(c/o,1),h=1-Math.pow(1-v,3),b=Math.round(a+r*h);t.textContent=s(b),v<1?requestAnimationFrame(u):t.textContent=s(i)}requestAnimationFrame(u)}function d(t){if(!t)return"";const e=document.createElement("div");return e.textContent=t,e.innerHTML}let tt=null;function Ct(t,e){const{activeScrapers:n,activeRetailers:o,totalRetailers:s,overallProgress:a}=e,i=n>0?`${n} ACTIVE`:"ALL IDLE",r=o-n;t.innerHTML=`
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
  `}function Bt(){const t=document.getElementById("current-time");t&&(t.textContent=ye())}function xe(){const t=document.getElementById("header-status"),e=document.getElementById("config-btn");f.subscribe(o=>{t&&Ct(t,o.summary)}),e&&e.addEventListener("click",()=>{g.toggleConfigModal(!0)}),Bt(),tt=setInterval(Bt,1e3);const n=f.getState();t&&Ct(t,n.summary)}function Le(){tt&&(clearInterval(tt),tt=null)}const we={init:xe,destroy:Le};let D={stores:0,requests:0},E=null,B=null;function Ee(t){if(t<0||!Number.isFinite(t))return"00:00:00";const e=Math.floor(t/3600),n=Math.floor(t%3600/60),o=Math.floor(t%60);return`${e.toString().padStart(2,"0")}:${n.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`}function Tt(){const t=document.getElementById("metric-duration");if(t)if(E){const e=Math.floor((Date.now()-E)/1e3);t.textContent=Ee(e)}else t.textContent="00:00:00"}function _e(t){let e=0,n=0,o=0;return Object.values(t).forEach(s=>{const i=(s.progress?.text||"").match(/^([\d,]+)/);i&&(e+=parseInt(i[1].replace(/,/g,""),10)||0),s.status==="running"&&o++;const r=s.stats||{};if(r.stat3_value&&r.stat3_value!=="—"){const l=parseInt(String(r.stat3_value).replace(/,/g,""),10);isNaN(l)||(n+=l)}}),{stores:e,requests:n,activeRetailers:o}}function kt(t){const{retailers:e,summary:n}=t,o=_e(e),s=n.activeScrapers>0;if(s&&!E)E=Date.now(),B||(B=setInterval(Tt,1e3));else if(!s&&E){E=null,B&&(clearInterval(B),B=null);const l=document.getElementById("metric-duration");l&&(l.textContent="00:00:00")}const a=document.getElementById("metric-stores");a&&o.stores!==D.stores&&U(a,D.stores,o.stores,500,l=>O(l));const i=document.getElementById("metric-requests");i&&o.requests!==D.requests&&U(i,D.requests,o.requests,500,l=>O(l)),Tt();const r=document.getElementById("metric-rate");if(r)if(s&&E&&o.stores>0){const l=Math.max(1,(Date.now()-E)/1e3),u=(o.stores/l).toFixed(1);r.textContent=`${u}/sec`}else r.textContent="—/sec";a&&(s?a.classList.add("metric__value--highlight"):a.classList.remove("metric__value--highlight")),D={stores:o.stores,requests:o.requests,duration:0,rate:0}}function Se(){f.subscribe(t=>{kt(t)}),kt(f.getState())}function $e(){D={stores:0,requests:0,duration:0,rate:0},E=null,B&&(clearInterval(B),B=null)}const Ce={init:Se,destroy:$e},Be=5e3,W=new Map;let Te=0;function qt(){let t=document.getElementById("toast-container");return t||(t=document.createElement("div"),t.id="toast-container",t.style.cssText=`
      position: fixed;
      top: var(--space-4);
      right: var(--space-4);
      z-index: var(--z-toast);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
      pointer-events: none;
    `,document.body.appendChild(t)),t}function ke(t,e,n){const o=document.createElement("div");o.id=`toast-${n}`,o.className="toast toast-enter",o.setAttribute("role","alert"),o.setAttribute("aria-live","polite");let s="";switch(e){case"success":s="✓";break;case"error":s="✕";break;case"warning":s="!";break;default:s="i"}o.innerHTML=`
    <span class="toast__icon">${s}</span>
    <span class="toast__message">${Me(t)}</span>
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
    `,r.addEventListener("click",()=>{it(n)}),r.addEventListener("mouseenter",()=>{r.style.color="var(--text-primary)"}),r.addEventListener("mouseleave",()=>{r.style.color="var(--text-muted)"})),o}function Me(t){if(!t)return"";const e=document.createElement("div");return e.textContent=t,e.innerHTML}function m(t,e="info",n=Be){const o=qt(),s=++Te,a=ke(t,e,s);if(o.appendChild(a),W.set(s,{element:a,timeoutId:null}),n>0){const i=setTimeout(()=>{it(s)},n);W.get(s).timeoutId=i}return s}function it(t){const e=W.get(t);if(!e)return;const{element:n,timeoutId:o}=e;o&&clearTimeout(o),n.style.animation="slide-out-right var(--duration-normal) var(--ease-out) forwards",setTimeout(()=>{n.remove(),W.delete(t)},300)}function Nt(){W.forEach((t,e)=>{it(e)})}function Re(t){return m(t,"success")}function Ae(t){return m(t,"error")}function Ie(t){return m(t,"warning")}function De(t){return m(t,"info")}function Oe(){qt()}function Pe(){Nt()}const R={init:Oe,destroy:Pe,showToast:m,dismissToast:it,dismissAllToasts:Nt,showSuccess:Re,showError:Ae,showWarning:Ie,showInfo:De},qe={verizon:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M1.734 0L0 3.82l9.566 20.178L14.69 14.1 22.136.002h-3.863l-4.6 9.2-3.462-6.934H3.467L6.2 8.2l3.366 6.733L4.35 3.82l1.25-2.5H1.734z"/></svg>',att:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4c-4.4 0-8 3.6-8 8s3.6 8 8 8c1.8 0 3.5-.6 4.9-1.6L12 12V4z"/></svg>',target:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2.5"/></svg>',tmobile:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 6h20v3H2V6zm7 5h6v10h-2v-8h-2v8H9V11z"/></svg>',walmart:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7h-4.8L12 2zm0 20l-2.4-7h4.8L12 22zm-10-10l7-2.4v4.8L2 12zm20 0l-7 2.4v-4.8L22 12zM4.9 4.9l6.2 3.6-2.4 2.4-3.8-6zm14.2 0l-3.6 6.2-2.4-2.4 6-3.8zM4.9 19.1l3.6-6.2 2.4 2.4-6 3.8zm14.2 0l-6.2-3.6 2.4-2.4 3.8 6z"/></svg>',bestbuy:'<svg viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 8h4v3H7V8zm0 5h4v3H7v-3zm6-5h4v3h-4V8zm0 5h4v3h-4v-3z"/></svg>'};let gt=!1;const x=new Map,L=new Map;let V=null;function Ne(t){if(t<0||!Number.isFinite(t))return"00:00:00";const e=Math.floor(t/3600),n=Math.floor(t%3600/60),o=Math.floor(t%60);return`${e.toString().padStart(2,"0")}:${n.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`}function He(){const t=Date.now();x.forEach((e,n)=>{const o=document.querySelector(`.retailer-card[data-retailer="${n}"] [data-field="duration"]`);if(o){const s=Math.floor((t-e)/1e3);o.textContent=Ne(s)}})}function Ht(t,e){const n=L.get(t);return n==="starting"&&e==="running"?(L.delete(t),"running"):n==="stopping"&&e!=="running"?(L.delete(t),e):n||e}function mt(t){return{running:"running",starting:"starting",stopping:"stopping",complete:"complete",pending:"pending",disabled:"disabled",error:"error",failed:"error"}[t]||"pending"}function vt(t){return{running:"SCRAPING",starting:"STARTING",stopping:"STOPPING",complete:"READY",pending:"READY",disabled:"DISABLED",error:"ERROR",failed:"ERROR"}[t]||"READY"}function Ft(t){if(!t||t.length===0)return"—";const e=t.find(s=>s.status==="in_progress");if(e)return e.name;if(t.every(s=>s.status==="complete")&&t.length>0)return"✓ All phases";const o=t.find(s=>s.status==="pending");return o?o.name:"—"}function zt(t){if(!t)return"—";const e=t.match(/^([\d,]+)/);return e?e[1]:"—"}function Fe(t,e){const n=k[t];if(!n)return"";const o=e.status||"pending",s=Ht(t,o),a=mt(s),i=vt(s),r=e.progress?.percentage||0,l=e.progress?.text||"No data",u=zt(l),p=e.phases||[],c=Ft(p),h=(e.stats||{}).stat2_value||"—",b=s==="running"||s==="starting",M=qe[t]||"";return`
    <div class="retailer-card retailer-card--${t} card-enter" data-retailer="${d(t)}">
      <div class="retailer-card__header">
        <div class="retailer-card__identity">
          <div class="retailer-card__accent"></div>
          <div class="retailer-card__logo">${M}</div>
          <span class="retailer-card__name">${d(n.name)}</span>
        </div>
        <span class="retailer-card__status retailer-card__status--${a}" data-field="status">
          ${i}
        </span>
      </div>

      <div class="retailer-card__body">
        <div class="retailer-card__progress">
          <div class="retailer-card__progress-header">
            <span class="retailer-card__progress-percent" data-field="percent">${Pt(r)}</span>
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
            <div class="retailer-card__stat-value" data-field="duration">${d(h)}</div>
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
        ${jt(t,s,r)}
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
  `}function jt(t,e,n){const o=e==="running";return e==="disabled"?`
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
  `}function ze(t,e){const n=document.querySelector(`.retailer-card[data-retailer="${t}"]`);if(!n)return;const o=e.status||"pending",s=Ht(t,o),a=mt(s),i=vt(s),r=e.progress?.percentage||0,l=e.progress?.text||"No data",u=zt(l),p=e.phases||[],c=Ft(p);(e.stats||{}).stat2_value;const h=s==="running"||s==="starting",b=n.querySelector('[data-field="status"]');b&&(b.textContent=i,b.className=`retailer-card__status retailer-card__status--${a}`);const M=n.querySelector('[data-field="percent"]');M&&(M.textContent=Pt(r));const Z=n.querySelector('[data-field="store-text"]');Z&&(Z.textContent=`${u} stores`);const bt=n.querySelector('[data-field="progress-bar"]');bt&&(bt.className=`progress ${h?"progress--active":""}`);const ut=n.querySelector('[data-field="progress-fill"]');ut&&(ut.style.width=`${r}%`,ut.className=`progress__fill progress__fill--${h?"live":r>=100?"done":"idle"}`);const xt=n.querySelector('[data-field="stores"]');xt&&(xt.textContent=u);const Lt=n.querySelector('[data-field="duration"]');Lt&&(h?x.has(t)||x.set(t,Date.now()):(x.delete(t),Lt.textContent="—"));const wt=n.querySelector('[data-field="phase-text"]');wt&&(wt.textContent=c);const z=n.querySelector('[data-field="actions"]');if(z){const ne=s==="disabled",Et=z.querySelector('[data-action="restart"]'),_t=!ne&&!h&&r>=100;if(Et&&!_t||!Et&&_t)z.innerHTML=jt(t,s,r);else{const St=z.querySelector('[data-action="start"]'),$t=z.querySelector('[data-action="stop"]');St&&(St.disabled=h),$t&&($t.disabled=!h)}}}function Mt(t){const e=document.getElementById("operations-grid");if(!e)return;let n="";Object.keys(k).forEach(o=>{const s=t[o]||{status:"pending"};n+=Fe(o,s),s.status==="running"&&!x.has(o)&&x.set(o,Date.now())}),e.innerHTML=n,gt=!0}function je(t){Object.keys(k).forEach(e=>{const n=t[e]||{status:"pending"};ze(e,n)})}async function Ue(t){const e=document.getElementById(`history-list-${t}`);if(e){e.innerHTML=`
    <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
      Loading...
    </div>
  `;try{const n=await w.getRunHistory(t,5);if(!n.runs||n.runs.length===0){e.innerHTML=`
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
    `}}}async function Ut(t){const e=t.target.closest("[data-action]");if(!e)return;const n=e.dataset.action,o=e.dataset.retailer,s=e.dataset.runId,a=e.dataset.format;switch(n){case"start":await Ve(o);break;case"stop":await Ge(o);break;case"restart":await Ke(o);break;case"toggle-history":Je(o);break;case"view-logs":We(o,s);break;case"toggle-export":Ye(o);break;case"export":await Xe(o,a);break}}function A(t,e){const n=document.querySelector(`.retailer-card[data-retailer="${t}"]`);if(!n)return;const o=n.querySelector('[data-field="status"]');o&&(o.textContent=vt(e),o.className=`retailer-card__status retailer-card__status--${mt(e)}`);const s=e==="running"||e==="starting",a=n.querySelector('[data-action="start"]'),i=n.querySelector('[data-action="stop"]');a&&(a.disabled=s||e==="stopping"),i&&(i.disabled=!s);const r=n.querySelector('[data-field="progress-bar"]');r&&(r.className=`progress ${s?"progress--active":""}`)}async function Ve(t){L.set(t,"starting"),A(t,"starting"),x.set(t,Date.now());try{await w.startScraper(t,{resume:!0}),m(`Started ${k[t]?.name||t} scraper`,"success")}catch(e){L.delete(t),x.delete(t),A(t,"error"),m(`Failed to start scraper: ${e.message}`,"error")}}async function Ge(t){L.set(t,"stopping"),A(t,"stopping");try{await w.stopScraper(t),x.delete(t),m(`Stopped ${k[t]?.name||t} scraper`,"success")}catch(e){L.delete(t),A(t,"error"),m(`Failed to stop scraper: ${e.message}`,"error")}}async function Ke(t){L.set(t,"stopping"),A(t,"stopping");try{await w.restartScraper(t,{resume:!0}),x.set(t,Date.now()),L.set(t,"starting"),A(t,"starting"),m(`Restarted ${k[t]?.name||t} scraper`,"success")}catch(e){L.delete(t),A(t,"error"),m(`Failed to restart scraper: ${e.message}`,"error")}}function Je(t){const e=document.querySelector(`.run-history[data-retailer="${t}"]`);if(!e)return;const n=e.classList.toggle("run-history--open"),o=e.querySelector(".run-history__toggle");o&&(o.textContent=n?"▲ Hide Run History":"▼ View Run History"),n&&Ue(t)}function We(t,e){g.openLogModal(t,e)}function Ye(t){document.querySelectorAll(".export-dropdown--open").forEach(n=>{n.dataset.retailer!==t&&n.classList.remove("export-dropdown--open")});const e=document.querySelector(`.export-dropdown[data-retailer="${t}"]`);e&&e.classList.toggle("export-dropdown--open")}async function Xe(t,e){const n=document.querySelector(`.export-dropdown[data-retailer="${t}"]`);n&&n.classList.remove("export-dropdown--open");const o=k[t]?.name||t;try{m(`Exporting ${o} data as ${e.toUpperCase()}...`,"info"),await w.exportRetailer(t,e),m(`${o} exported as ${e.toUpperCase()}`,"success")}catch(s){m(`Export failed: ${s.message}`,"error")}}function Ze(){const t=document.getElementById("operations-grid");t&&(V||(V=setInterval(He,1e3)),f.subscribe(e=>{gt?je(e.retailers):Mt(e.retailers)}),t.addEventListener("click",Ut),Mt(f.getState().retailers))}function Qe(){const t=document.getElementById("operations-grid");t&&t.removeEventListener("click",Ut),V&&(clearInterval(V),V=null),x.clear(),L.clear(),gt=!1}const tn={init:Ze,destroy:Qe};let _={new:0,closed:0,modified:0};function Rt(t){const e=document.getElementById("change-new"),n=document.getElementById("change-closed"),o=document.getElementById("change-modified");e&&t.new!==_.new&&U(e,_.new,t.new,500,s=>`+${O(s)}`),n&&t.closed!==_.closed&&U(n,_.closed,t.closed,500,s=>`-${O(s)}`),o&&t.modified!==_.modified&&U(o,_.modified,t.modified,500,s=>`~${O(s)}`),_={...t}}function Vt(){const t=document.getElementById("change-panel");if(!t)return;const e=t.classList.toggle("change-panel--open");g.toggleChangePanel(e)}function en(){const t=document.getElementById("change-panel-toggle"),e=document.getElementById("change-panel");t&&t.addEventListener("click",Vt),f.subscribe(n=>{Rt(n.changes),e&&(n.ui.changePanelOpen?e.classList.add("change-panel--open"):e.classList.remove("change-panel--open"))}),Rt(f.getState().changes)}function nn(){const t=document.getElementById("change-panel-toggle");t&&t.removeEventListener("click",Vt),_={new:0,closed:0,modified:0}}const on={init:en,destroy:nn},sn=[{value:"json",label:"JSON",description:"Standard JSON format"},{value:"csv",label:"CSV",description:"Comma-separated values"},{value:"excel",label:"Excel",description:"Multi-sheet workbook"},{value:"geojson",label:"GeoJSON",description:"Geographic data format"}];let I="excel",lt=!0,Y=!1;function Gt(){const e=f.getState().retailers||{};return Object.entries(e).filter(([n,o])=>(o.phases||[]).some(a=>a.total>0)).map(([n])=>n)}function H(){const t=document.getElementById("export-panel");if(!t)return;const e=Gt(),n=e.length>0;t.innerHTML=`
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
              ${sn.map(o=>`
                <button
                  class="export-panel__format-btn ${I===o.value?"export-panel__format-btn--active":""}"
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
                ${lt?"checked":""}
                ${n?"":"disabled"}
              />
              <span>Combine into single file</span>
            </label>
            <span class="export-panel__hint">
              ${I==="excel"?"Creates multi-sheet workbook (one sheet per retailer)":"Merges all stores with retailer field"}
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
            ${!n||Y?"disabled":""}
          >
            ${Y?'<span class="spinner"></span> Exporting...':"Export All Retailers"}
          </button>
        </div>
      </div>
    </div>
  `,an()}function an(){const t=document.getElementById("export-panel-toggle");t&&t.addEventListener("click",Kt),document.querySelectorAll(".export-panel__format-btn").forEach(s=>{s.addEventListener("click",a=>{I=a.target.dataset.format,H()})});const n=document.getElementById("export-combine");n&&n.addEventListener("change",s=>{lt=s.target.checked,H()});const o=document.getElementById("export-all-btn");o&&o.addEventListener("click",rn)}function Kt(){const t=document.getElementById("export-panel");t&&t.classList.toggle("export-panel--open")}async function rn(){const t=Gt();if(t.length===0){R.showWarning("No retailers have data to export");return}Y=!0,H();try{R.showInfo(`Generating ${I.toUpperCase()} export for ${t.length} retailers...`),await Ot(t,I,lt),R.showSuccess(`Export complete! Downloaded ${I.toUpperCase()} file.`)}catch(e){console.error("Export failed:",e),R.showError(`Export failed: ${e.message}`)}finally{Y=!1,H()}}function ln(){H(),f.subscribe(()=>{const t=document.getElementById("export-panel");t&&t.classList.contains("export-panel--open")&&H()})}function cn(){const t=document.getElementById("export-panel-toggle");t&&t.removeEventListener("click",Kt),I="excel",lt=!0,Y=!1}const dn={init:ln,destroy:cn};let y=new Set(["ALL"]),G=null,T=[],K=0,P=!1,J=!1,S=0,$=2e3;const et=2e3,un=1e4,fn=1.5;async function Jt(){const t=document.getElementById("config-modal"),e=document.getElementById("config-editor"),n=document.getElementById("config-alert");if(!(!t||!e)){t.classList.add("modal-overlay--open"),g.toggleConfigModal(!0),n&&(n.style.display="none"),e.value="Loading configuration...",e.disabled=!0;try{const o=await w.getConfig();e.value=o.content||"",e.disabled=!1}catch(o){e.value="",e.disabled=!1,j(`Failed to load configuration: ${o.message}`,"error")}}}function q(){const t=document.getElementById("config-modal");t&&t.classList.remove("modal-overlay--open"),g.toggleConfigModal(!1)}async function pn(){const t=document.getElementById("config-editor"),e=document.getElementById("config-save");if(!t)return;const n=t.value;if(!n||n.trim().length===0){j("Configuration cannot be empty","error");return}if(!n.includes("retailers:")){j('Configuration must contain "retailers:" key',"error");return}e&&(e.disabled=!0,e.textContent="Saving...");try{const o=await w.updateConfig(n);j(`Configuration saved successfully!
Backup created at: ${o.backup||"unknown"}`,"success"),m("Configuration updated successfully","success"),setTimeout(()=>{q()},2e3)}catch(o){let s=o.message||"Unknown error";o.data?.details&&Array.isArray(o.data.details)&&(s+=`

Details:
`+o.data.details.map(a=>`• ${a}`).join(`
`)),j(`Failed to save configuration:
${s}`,"error")}finally{e&&(e.disabled=!1,e.textContent="Save Configuration")}}function j(t,e="info"){const n=document.getElementById("config-alert");n&&(n.className=`alert alert--${e}`,n.textContent=t,n.style.display="block")}async function Wt(t,e){const n=document.getElementById("log-modal"),o=document.getElementById("log-modal-title"),s=document.getElementById("log-content");if(document.getElementById("log-stats"),!n||!s)return;y=new Set(["ALL"]),Xt(),T=[],K=0,P=!1,J=!1,g.resetLiveLogState();const a=k[t]?.name||t;o&&(o.textContent=`Logs — ${a} — ${e}`),n.classList.add("modal-overlay--open"),g.openLogModal(t,e),s.innerHTML=`
    <div style="text-align: center; padding: var(--space-8); color: var(--text-muted);">
      Loading logs...
    </div>
  `;try{const i=await w.getLogs(t,e);T=(i.content||"").split(`
`).filter(u=>u.trim()).map(u=>Yt(u)),K=i.total_lines||T.length,hn(T),ht(),i.is_active?(g.setLogIsActive(!0),g.setLiveLogEnabled(!0),N(!0),gn(t,e),ct()):N(!1)}catch(i){s.innerHTML=`
      <div class="alert alert--error">
        Error loading logs: ${d(i.message)}
      </div>
    `}}function gn(t,e){C(),S=0,$=et,G=setInterval(async()=>{if(J)return;const n=f.getState();if(!n.ui.logModalOpen){C();return}if(!n.ui.liveLogPaused){J=!0;try{const o=await w.getLogs(t,e,{offset:K}),s=f.getState();if(!s.ui.logModalOpen||s.ui.currentLogRetailer!==t||s.ui.currentLogRunId!==e){C();return}if(!o.is_active){C(),g.setLogIsActive(!1),g.setLiveLogEnabled(!1),N(!1),m("Scraper completed","info");return}if(o.lines>0&&o.total_lines>K){const r=(o.content||"").split(`
`).filter(l=>l.trim()).map(l=>Yt(l));mn(r),K=o.total_lines,ht(),P||ct()}S=0,$=et}catch(o){if(console.error("Error fetching live logs:",o),o.status===429){if(S++,$=Math.min(et*Math.pow(fn,S),un),console.warn(`Rate limited (429). Slowing polling to ${($/1e3).toFixed(1)}s`),m(`Log polling rate limited. Slowing down to ${($/1e3).toFixed(1)}s intervals`,"warning"),S>=3){console.error("Repeated rate limiting - stopping live log polling"),C(),g.setLiveLogEnabled(!1),N(!1),m("Live log polling stopped due to repeated rate limiting. Refresh to try again.","error");return}C(),G=setInterval(arguments.callee,$)}else(o.status>=500||o.isNetworkError)&&(S++,S>=5&&(console.error("Too many polling errors - stopping"),C(),g.setLiveLogEnabled(!1),N(!1),m("Live log polling stopped due to server errors","error")))}finally{J=!1}}},$)}function C(){G&&(clearInterval(G),G=null),J=!1,S=0,$=et}function mn(t){const e=document.getElementById("log-content");if(!e)return;T=[...T,...t];const n=t.map(o=>{const a=y.has("ALL")||y.has(o.level)?"":"hidden",i=o.level.toLowerCase();let r=d(o.raw);return o.timestamp&&(r=r.replace(d(o.timestamp),`<span class="log-timestamp">${d(o.timestamp)}</span>`)),o.level&&(r=r.replace(new RegExp(`\\b${d(o.level)}\\b`),`<span class="log-level">${d(o.level)}</span>`)),`<div class="log-line log-line--${i} log-line--new ${a}" data-level="${d(o.level)}">${r}</div>`}).join("");e.insertAdjacentHTML("beforeend",n),setTimeout(()=>{e.querySelectorAll(".log-line--new").forEach(s=>s.classList.remove("log-line--new"))},500)}function ct(){const t=document.getElementById("log-content");t&&(t.scrollTop=t.scrollHeight)}function N(t){const e=document.getElementById("live-indicator"),n=document.getElementById("log-live-controls");if(e&&(e.style.display=t?"inline-flex":"none"),n&&(n.style.display=t?"flex":"none"),t){const o=document.getElementById("log-pause-btn");o&&(o.textContent="⏸ Pause",o.classList.remove("btn--paused"))}}function vn(){const e=!f.getState().ui.liveLogPaused;g.setLiveLogPaused(e);const n=document.getElementById("log-pause-btn");n&&(e?(n.textContent="▶ Resume",n.classList.add("btn--paused")):(n.textContent="⏸ Pause",n.classList.remove("btn--paused"),P=!1,ct()))}function ht(){const t=document.getElementById("log-stats"),e=f.getState();if(t){const n=document.querySelectorAll(".log-line:not(.hidden)").length,o=T.length;e.ui.logIsActive?t.textContent=`${n} of ${o} lines (live)`:t.textContent=`${n} of ${o} lines`}g.setLogLineCount(T.length)}function st(){C(),g.resetLiveLogState(),N(!1);const t=document.getElementById("log-modal");t&&t.classList.remove("modal-overlay--open"),g.closeLogModal()}function Yt(t){const e=t.match(/\b(DEBUG|INFO|WARNING|ERROR)\b/),n=e?e[1]:"INFO",o=t.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/),s=o?o[1]:null;return{raw:t,level:n,timestamp:s}}function hn(t){const e=document.getElementById("log-content");if(!e)return;const n=t.map(o=>{const a=y.has("ALL")||y.has(o.level)?"":"hidden",i=o.level.toLowerCase();let r=d(o.raw);return o.timestamp&&(r=r.replace(d(o.timestamp),`<span class="log-timestamp">${d(o.timestamp)}</span>`)),o.level&&(r=r.replace(new RegExp(`\\b${d(o.level)}\\b`),`<span class="log-level">${d(o.level)}</span>`)),`<div class="log-line log-line--${i} ${a}" data-level="${d(o.level)}">${r}</div>`}).join("");e.innerHTML=n||'<div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">No logs found</div>'}function yn(t){t==="ALL"?(y.clear(),y.add("ALL")):(y.delete("ALL"),y.has(t)?y.delete(t):y.add(t),y.size===0&&y.add("ALL")),Xt(),bn()}function Xt(){document.querySelectorAll(".log-filter-btn").forEach(e=>{const n=e.dataset.level;y.has(n)?e.classList.add("active"):e.classList.remove("active")})}function bn(){document.querySelectorAll(".log-line").forEach(e=>{const n=e.dataset.level;y.has("ALL")||y.has(n)?e.classList.remove("hidden"):e.classList.add("hidden")}),ht()}function xn(){const t=document.getElementById("config-btn"),e=document.getElementById("config-modal-close"),n=document.getElementById("config-cancel"),o=document.getElementById("config-save"),s=document.getElementById("config-modal");t&&t.addEventListener("click",Jt),e&&e.addEventListener("click",q),n&&n.addEventListener("click",q),o&&o.addEventListener("click",pn),s&&s.addEventListener("click",c=>{c.target===s&&q()});const a=document.getElementById("log-modal-close"),i=document.getElementById("log-modal"),r=document.getElementById("log-content");a&&a.addEventListener("click",st),i&&i.addEventListener("click",c=>{c.target===i&&st()}),document.querySelectorAll(".log-filter-btn").forEach(c=>{c.addEventListener("click",()=>{yn(c.dataset.level)})});const u=document.getElementById("log-pause-btn"),p=document.getElementById("log-scroll-btn");u&&u.addEventListener("click",vn),p&&p.addEventListener("click",()=>{P=!1,ct()}),r&&r.addEventListener("scroll",()=>{const c=f.getState();if(!c.ui.liveLogEnabled)return;const v=r.scrollHeight-r.scrollTop<=r.clientHeight+50;!v&&!c.ui.liveLogPaused?P=!0:v&&(P=!1)}),f.subscribe(c=>{if(c.ui.logModalOpen&&c.ui.currentLogRetailer&&c.ui.currentLogRunId){const v=document.getElementById("log-modal");v&&!v.classList.contains("modal-overlay--open")&&Wt(c.ui.currentLogRetailer,c.ui.currentLogRunId)}})}function Ln(){}const wn={init:xn,destroy:Ln,openConfigModal:Jt,closeConfigModal:q,openLogModal:Wt,closeLogModal:st},X=new Map;let dt=!0;function nt(t,e,n={}){const o=Qt(t);X.set(o,{callback:e,preventDefault:n.preventDefault??!0,description:n.description||""})}function En(t){const e=Qt(t);X.delete(e)}function _n(){dt=!0}function Sn(){dt=!1}function $n(){return dt}function Zt(){return Array.from(X.entries()).map(([t,e])=>({key:t,description:e.description}))}function Qt(t){return t.toLowerCase().replace(/\s+/g,"")}function Cn(t){const e=[];(t.ctrlKey||t.metaKey)&&e.push("ctrl"),t.altKey&&e.push("alt"),t.shiftKey&&e.push("shift");let n=t.key.toLowerCase();return n===" "&&(n="space"),["control","alt","shift","meta"].includes(n)||e.push(n),e.join("+")}function Bn(t){const e=t.target.tagName.toLowerCase(),n=t.target.isContentEditable;return e==="input"||e==="textarea"||e==="select"||n}function te(t){if(!dt||Bn(t)&&t.key!=="Escape")return;const e=Cn(t),n=X.get(e);n&&(n.preventDefault&&t.preventDefault(),n.callback(t))}function Tn(){document.addEventListener("keydown",te),nt("escape",()=>{const t=document.getElementById("log-modal");t&&t.classList.contains("modal-overlay--open")&&st();const e=document.getElementById("config-modal");e&&e.classList.contains("modal-overlay--open")&&q()},{description:"Close modal"}),nt("?",()=>{console.log("Keyboard shortcuts:",Zt())},{description:"Show keyboard shortcuts"}),nt("r",()=>{window.dispatchEvent(new CustomEvent("manual-refresh"))},{description:"Refresh data"})}function kn(){document.removeEventListener("keydown",te),X.clear()}const Mn={init:Tn,destroy:kn,registerShortcut:nt,unregisterShortcut:En,enable:_n,disable:Sn,isActive:$n,getShortcuts:Zt},Rn=5e3,An=1e4;let ot=null,ft=!1;async function pt(){try{const t=await w.getStatus();return g.setStatusData(t),!0}catch(t){return console.error("Failed to fetch status:",t),g.setError(t),!1}}function yt(){ft||(ft=!0,pt(),ot=setInterval(async()=>{await pt()||(ee(),setTimeout(()=>{yt()},An))},Rn))}function ee(){ft=!1,ot&&(clearInterval(ot),ot=null)}function In(){document.hidden?ee():yt()}function Dn(){pt(),R.showInfo("Refreshing data...")}function On(){const t=document.getElementById("footer-timestamp"),e=f.getState();t&&e.lastUpdate&&(t.textContent=be(e.lastUpdate))}function At(){console.log("Initializing Retail Scraper Command Center..."),R.init(),we.init(),Ce.init(),tn.init(),on.init(),dn.init(),wn.init(),Mn.init(),document.addEventListener("visibilitychange",In),window.addEventListener("manual-refresh",Dn),setInterval(On,1e3),yt(),f.subscribe((t,e)=>{t.error&&t.error!==e?.error&&R.showError(`Connection error: ${t.error}`)}),console.log("Dashboard initialized")}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",At):At();
