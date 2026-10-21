'use strict';
const state={feed:{tickers:{}},ticker:null,tab:'overview',tf:'1D',bars:60,overlay:true,config:{},research:null,paths:{},request:0};
const el=id=>document.getElementById(id),esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>typeof v==='number'&&Number.isFinite(v);
const val=(v,d=2)=>num(v)?v.toLocaleString('en-CA',{maximumFractionDigits:d}):'Unavailable';
function money(v,c){if(!num(v))return 'Unavailable';return c==='CAD'||c==='USD'?new Intl.NumberFormat('en-CA',{style:'currency',currency:c,maximumFractionDigits:2}).format(v):val(v)+' (currency unverified)'}
function when(iso){if(!iso)return 'Unavailable';let d=new Date(iso);return isNaN(d)?'Invalid timestamp':new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(d)}
const line=(a,b)=>'<div class="statline"><span class="name">'+esc(a)+'</span><span class="num">'+esc(b)+'</span></div>';
const card=(t,c)=>'<article class="card"><h2>'+esc(t)+'</h2>'+c+'</article>';
const badge=s=>'<span class="badge '+(s==='UP'?'up':s==='DOWN'||s==='AVOID'?'down':'wait')+'">'+esc(s)+'</span>';
const stat=(label,value,hint)=>'<div class="kpi"><div class="label">'+esc(label)+'</div><div class="value">'+esc(value)+'</div><div class="hint">'+esc(hint)+'</div></div>';
function freshness(x,now=Date.now()){
 const stamp=Date.parse(x.minute_bar_utc),age=Number.isFinite(stamp)?(now-stamp)/60000:null;
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(now));
 const sessions=x.session_schedule||[];const row=sessions.find(z=>z.date===day);
 const coverage=sessions.length>0&&day>=sessions[0].date&&day<=sessions[sessions.length-1].date;
 const open=!!(row&&now>=Date.parse(row.open_utc)&&now<Date.parse(row.close_utc));
 const live=!!(open&&age!==null&&age>=0&&age<=15&&!x.refresh_failed&&x.analysis_version==='rules-v2.0.0');
 return {age,open,live,status:!coverage?'SESSION UNVERIFIED — no live signal':!open?'MARKET CLOSED — research only':live?'RECENT MINUTE BAR — entitlement unverified':'STALE DATA — NO VALIDATED LIVE TRADE SIGNAL'};
}
function classification(x){return x.decision?.classification==='AVOID'?'AVOID':'WAIT'}
function tickerButtons(){const symbols=Object.keys(state.feed.tickers).filter(k=>!state.feed.tickers[k].error);el('tickers').innerHTML=symbols.map(s=>'<option value="'+esc(s)+'"></option>').join('');el('chips').innerHTML=symbols.map(s=>'<button class="chip" data-symbol="'+esc(s)+'">'+esc(s)+'</button>').join('');document.querySelectorAll('[data-symbol]').forEach(b=>b.onclick=()=>selectTicker(b.dataset.symbol));}
function notify(message,bad=false){el('status').className='notice '+(bad?'warn':'');el('status').textContent=message;}
async function fetchJSON(url,timeout=120000){const c=new AbortController();const timer=setTimeout(()=>c.abort(),timeout);try{const r=await fetch(url,{cache:'no-store',signal:c.signal,headers:url.includes('/api/')&&el('access-token')?.value?{Authorization:'Bearer '+el('access-token').value}:{}});const data=await r.json();if(!r.ok)throw Error(data.detail||'HTTP '+r.status);return data}finally{clearTimeout(timer)}}
function apiBase(){return state.config.same_origin_api?'':state.config.api_url?.replace(/\/$/,'')}
async function selectTicker(raw,fetchNew=true){
 const id=++state.request;let t=String(raw||'').trim().toUpperCase();if(t.startsWith('TSX:'))t=t.slice(4)+'.TO';t=t.replace(/^(NYSE|NASDAQ):/,'');
 if(!/^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$/.test(t)){notify('Enter a valid US or Canadian symbol, such as NVDA or RY.TO.',true);return}
 el('ticker').value=t;const enabled=state.config.same_origin_api||!!state.config.api_url;
 if(enabled&&fetchNew){el('analyze').disabled=true;el('analyze').textContent='Analyzing…';notify('Fetching '+t+' from the Python analysis service…');
  try{const response=await fetchJSON(apiBase()+'/api/analyze?symbol='+encodeURIComponent(t));if(id!==state.request)return;state.feed.tickers[t]=response.ticker;}
  catch(e){if(id!==state.request)return;state.ticker=null;el('dashboard').hidden=true;el('intro').hidden=false;el('intro').textContent='No new result. Retry when the provider or backend is available.';notify('On-demand analysis failed: '+e.message,true);return}
  finally{if(id===state.request){el('analyze').disabled=false;el('analyze').textContent='Analyze →'}}
 }
 const x=state.feed.tickers[t];if(!x||x.error){state.ticker=null;el('dashboard').hidden=true;el('intro').hidden=false;el('intro').textContent=enabled?'No valid result returned.':'This public site currently serves saved snapshots. The tested Python backend must be deployed to enable any-ticker requests here.';notify(x?.error||t+' has no published snapshot. No analysis has been invented.',true);return}
 state.ticker=t;el('dashboard').hidden=false;el('intro').hidden=true;render();
}
function render(){const x=state.feed.tickers[state.ticker];if(!x)return;const t=x.technical||{},d=x.decision||{},f=freshness(x),m=v=>money(v,x.currency);let out='';
 const legacy=x.analysis_version!=='rules-v2.0.0';
 notify(x.ticker+' · '+f.status+' · Minute bar opened: '+when(x.minute_bar_utc)+' · Retrieved: '+when(x.retrieved_at_utc)+' · '+x.provider, !f.live);
 el('kpis').innerHTML=stat('Latest reported minute price',m(x.quote?.price),'Minute bar close, potentially developing; not a live quote')+stat('Last completed daily close',m(x.price),x.last_closed_bar_date)+stat('Research decision',classification(x),'NO RELIABLE EDGE established')+stat('Daily / Weekly',String(t.trends?.['1D']||'UNKNOWN')+' / '+String(t.trends?.['1W']||'UNKNOWN'),'Completed exchange bars');
 document.querySelectorAll('.tab').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===state.tab)));
 if(legacy)out+='<div class="notice warn">Legacy snapshot: generated before the calendar and indicator fixes. Refresh from the upgraded publisher before relying on its technical calculations.</div>';
 if(!x.truth)out+='<div class="notice warn">Evidence report unavailable; source quality and predicted outcomes are not independently verified. No execution signal is established.</div>';
 if(state.tab==='overview'){
  const summary=d.bias==='DOWN'?'The observed trend is weak. A lower price alone does not confirm a bottom. Wait for a closed-bar reversal and reassess the risk.':d.bias==='UP'?'The observed trend is upward. That does not establish a profitable entry. Check support, confirmation, and data age before considering a setup.':'The timeframes do not provide a clear direction. Wait for a more consistent trend or a confirmed reversal.';
  out+='<div class="grid">'+card(classification(x)+' — '+(d.bias||'UNCLEAR')+' context','<p>'+esc(summary)+'</p>'+((d.reasons||[]).map(r=>'<div class="reason">'+esc(r)+'</div>').join('')))+card('Evidence you can inspect',line('Model',x.analysis_version||'Legacy rules-v1')+line('Source',x.provider)+line('Exchange calendar',x.provenance?.calendar||'Unverified')+line('Currency',x.currency||'Unverified')+line('Minute-bar age',f.age===null?'Unavailable':val(f.age,1)+' minutes')+'<p class="hint">Recent retrieval is not evidence of a recent market trade. A calendar cannot detect a trading halt.</p>')+'</div>';
 }

 if(state.tab==='overview'){
   const e=x.truth||{};
   out+=card('TRUTH CHECK · Evidence versus assumptions',
     line('Research verification status',e.status||'NOT VERIFIED')+
     line('Market-data source',e.data_source||x.provider||'Unidentified')+
     line('Independent vendor cross-check',e.independent_source_crosscheck===true?'YES':'NO')+
     line('Licensed live-data access',e.verified_live_entitlement===true?'VERIFIED':'UNVERIFIED')+
     line('Dealer positions',e.verified_dealer_positions===true?'VERIFIED':'UNKNOWN')+
     line('Calibrated probabilities',e.calibrated_prediction_probabilities===true?'YES':'NOT ESTABLISHED')+
     line('Profitable edge after costs',e.measured_executable_trading_edge===true?'VERIFIED':'NOT ESTABLISHED')+
     (e.observations||[]).map(o=>'<div class="reason"><b>'+esc(o.level)+'</b> · '+esc(o.subject)+'<div class="hint">'+esc(o.meaning)+'</div></div>').join('')+
     '<p class="hint">Vendor-reported data is not independent confirmation. A modeled scenario is not a forecast or trade instruction.</p>');
 }
 if(state.tab==='technicals'){
  const structure=t.structure?.[state.tf]||{};
  if(x.market_structure)out+=card('Daily sweep / breakout context',line('Latest closed-bar event',x.market_structure.status)+line('Interpretation',x.market_structure.reason)+line('Volume participation',x.market_structure.participation));
  out+='<div class="grid">'+card('Closed-bar timeframes',Object.entries(t.trends||{}).map(([k,v])=>line(k,v)).join(''))+card('Daily observations',line('RSI (14)',val(t.rsi))+line('ATR (14)',m(t.atr))+line('Volume / 20-bar mean',val(t.volume_ratio))+line('Support: 20-day low',m(t.support20))+line('Resistance: 20-day high',m(t.resistance20)))+'</div>';
  out+=card('Causal structure evidence',line('Session VWAP proxy',m(structure.session_vwap_proxy))+line('Volume / prior 20 bars',val(structure.volume_participation_ratio))+(structure.structure_breaks||[]).map(e=>'<p>'+esc(e.event)+' · '+esc(when(e.bar))+' · '+m(e.level)+'</p>').join('')+'<p class="hint">BOS and CHoCH use previously confirmed pivots and closed-bar crossings. These are descriptive events, not validated trade signals.</p>');
  out+=card('Candles & structure','<div class="chips"><label>Timeframe <select id="timeframe">'+['15M','1H','4H','1D','1W'].map(tf=>'<option '+(tf===state.tf?'selected':'')+'>'+tf+'</option>').join('')+'</select></label><label> Bars <select id="barcount">'+[30,60,100].map(n=>'<option '+(n===state.bars?'selected':'')+'>'+n+'</option>').join('')+'</select></label><label><input type="checkbox" id="overlay" '+(state.overlay?'checked':'')+'> Active FVG patterns</label></div>'+candles(t.candles?.[state.tf]||[],structure.zones||[])+line('Confirmed pivot sequence',structure.structure||'Insufficient data')+(structure.events||[]).map(e=>'<div class="reason">'+esc(e)+'</div>').join('')+'<p class="hint">Hover a candle for OHLC. Pivots require two later closed bars. Final intraday buckets shorten at session close. FVGs describe price gaps; they do not prove institutional orders.</p>');
  out+=card('FVG pattern evidence',(structure.zones||[]).slice(-8).map(z=>'<div class="reason">'+esc(z.type)+' · '+m(z.lower)+' – '+m(z.upper)+' · '+(z.valid?'Valid pattern':'Invalidated')+' · Tests: '+esc(z.tests)+' · Age: '+esc(z.age_bars)+' bars<br><span class="hint">Created '+esc(when(z.created_at))+' · '+'Invalidation rule: '+esc(z.invalidation)+' · Probability unavailable</span></div>').join('')||'<p>No patterns available in this timeframe.</p>');
 }
 if(state.tab==='fundamentals')out+='<div class="grid">'+card('Provider-reported financial facts',(x.fundamentals?.facts||[]).map(z=>line(z.label,z.value)).join(''))+card('Valuation scope','<p>'+esc(x.fundamentals?.valuation_note||'Unavailable')+'</p><p class="hint">Current vendor metadata is not a publication-dated filing history. No independently audited intrinsic value or bank ROTCE model has been implemented.</p>'+line('Corporate actions reported',(x.corporate_actions||[]).length))+'</div>';
 if(state.tab==='institutional')out+=card('Institutional / Options — evidence status',line('Personal options scenarios','Available in the local Gradio Options map tab; not published here')+line('Verified options prints','Unavailable')+line('Dealer GEX / DEX','Unknown; positions cannot be inferred from OI alone')+line('FINRA ATS / short interest','Not integrated')+line('13F / Form 4','Not integrated')+line('OHLCV volume observations','Inferred proxies only')+'<p>No institutional accumulation, distribution, dealer position, or dark-pool transaction is claimed.</p>');
 if(state.tab==='catalysts')out+=card('News & catalysts — unavailable','<p>No publication-dated news or filing feed is connected. Earnings, offerings, customer contracts, and macro releases have not been checked by this analysis.</p><p class="hint">This missing context can materially change the technical interpretation. There are no invented headlines or impact scores.</p>');
 if(state.tab==='forecast'){
  out+=card('Conditional scenarios',Object.entries(d.scenarios||{}).map(([name,text])=>'<h3>'+esc(name.toUpperCase())+'</h3><p>'+esc(text)+'</p>').join('')||'<p>Scenarios unavailable for this legacy snapshot.</p>');
  out+='<div class="grid">'+card('Illustrative daily price references',line('Entry area',d.entry_zone?.length===2?m(d.entry_zone[0])+' – '+m(d.entry_zone[1]):'Unavailable')+line('Invalidation',m(d.stop))+line('Target 1 / 2 / 3',(d.targets||[]).map(m).join(' / '))+line('Resistance / risk',num(d.rr_to_resistance)?val(d.rr_to_resistance)+'R':'Unavailable')+'<p class="hint">Rule-derived references, not validated trade instructions. Gaps, spread and slippage can exceed the planned stop.</p>')+card('Sensitivity, not a price forecast',Object.entries(d.ranges||{}).map(([h,v])=>line(h+' sessions',m(v.lower)+' – '+m(v.upper))).join('')+'<p class="hint">Close ± ATR × √sessions. No calibrated probability, expected target date, or validated Strict/Adaptive grade is available.</p>')+'</div>';
 }
 if(state.tab==='accuracy'){
  const a=state.feed.audit||{};out+=card('INSUFFICIENT VALIDATION',line('New forward observations',a.total||0)+line('Matured outcomes',a.resolved||0)+line('Direction-scored outcomes',a.direction_evaluated||0)+line('Preserved legacy hypotheses',a.legacy_unvalidated_count??'See legacy ledger')+line('Unscored predeployment event archive',a.predeployment_unscored_events||0)+'<p>No profitability or accuracy guarantee is established. Endpoint direction uses a frozen observed reference; this is not executable trade performance.</p><p><a href="./data/events.jsonl">Inspect append-only events</a> · <a href="./data/ledger.json">Legacy archive</a></p>');
  out+=card('Recorded hypotheses','<div style="overflow:auto"><table><thead><tr><th>Symbol</th><th>Recorded ET</th><th>Horizon</th><th>Model</th><th>Outcome</th></tr></thead><tbody>'+(a.recent||[]).map(r=>'<tr><td>'+esc(r.ticker)+'</td><td>'+esc(when(r.recorded_at_utc))+'</td><td>'+esc(r.horizon_sessions)+' sessions</td><td>'+esc(r.model_version||'Legacy')+'</td><td>'+esc(r.status)+'</td></tr>').join('')+'</tbody></table></div>');
 }
 if(state.tab==='accuracy'){
  const path=state.paths[state.ticker];
  out+=card('Target-before-stop research', '<p>Models ask whether a fixed target is reached before invalidation within 5 sessions. Historical tests include assumed transaction costs and separate training, calibration and test periods.</p>'+(state.config.same_origin_api||state.config.api_url?'<button id="run-paths" class="btn">Run private historical test</button>':'<p class="hint">Available in the protected Python backend. No live probability or public result has been invented.</p>')+(path?'<p>'+esc(path.validation_status)+'</p>'+Object.entries(path.metrics||{}).map(([name,m])=>'<h3>'+esc(name)+'</h3>'+line('Test samples',m.samples)+line('Brier score (lower is better)',val(m.brier,4))+line('Trades at fixed 60% threshold',m.trades_at_fixed_0_6_threshold)+line('Net expectancy per selected trade',num(m.net_expectancy_return)?val(m.net_expectancy_return*100,2)+'%':'Unavailable')+line('Net wins / losses',m.wins+' / '+m.losses)).join('')+'<p>'+esc((path.limitations||[]).join(' '))+'</p>':''));
 }
 if(state.tab==='accuracy'&&state.research){
  const experiments=state.research.experiments||{};
  out+=card('Historical walk-forward experiments — separate from forward observations',Object.entries(experiments).map(([symbol,horizons])=>Object.entries(horizons).map(([h,exp])=>'<h3>'+esc(symbol)+' · '+esc(h)+' sessions · '+esc(exp.data_start)+' to '+esc(exp.data_end)+'</h3><div style="overflow:auto"><table><thead><tr><th>Model</th><th>Samples</th><th>Return MAE</th><th>Skill vs no-change</th></tr></thead><tbody>'+Object.entries(exp.metrics).map(([name,metric])=>'<tr><td>'+esc(name)+'</td><td>'+esc(metric.samples)+'</td><td>'+esc(val(metric.mae_return*100,2))+' percentage points</td><td>'+esc(val(metric.mae_skill_vs_no_change*100,1))+'%</td></tr>').join('')+'</tbody></table></div><p class="hint">Positive skill means lower absolute error than no-change in this small historical sample. Negative means worse. No executable P&L, calibrated probabilities or production model promotion.</p>').join('')).join('')+'<a href="./data/research.json">Inspect all test predictions, actuals and methodology</a>');
 }
 if(state.tab==='watchlist')out+=card('Published coverage & alert status',line('Published symbols',Object.keys(state.feed.tickers).join(', '))+line('Backend on demand',state.config.same_origin_api||state.config.api_url?'Configured — any supported ticker':'Not deployed / configured')+line('Alerts','Not enabled; no email or web notifications sent')+'<p>This page checks the saved archive every 15 minutes. New public market-data publication is paused; personal analysis requires the protected backend.</p>');
 out+=card('Source limitations',(x.warnings||[]).map(w=>'<div class="reason">'+esc(w)+'</div>').join('')||'No additional provider warnings.');el('view').innerHTML=out;
 if(el('run-paths'))el('run-paths').onclick=async()=>{const ticker=state.ticker;el('run-paths').disabled=true;try{state.paths[ticker]=await fetchJSON(apiBase()+'/api/paths?symbol='+encodeURIComponent(ticker));if(state.ticker===ticker)render()}catch(e){notify('Historical test unavailable: '+e.message,true);if(el('run-paths'))el('run-paths').disabled=false}};
 if(el('timeframe')){el('timeframe').onchange=e=>{state.tf=e.target.value;render()};el('barcount').onchange=e=>{state.bars=Number(e.target.value);render()};el('overlay').onchange=e=>{state.overlay=e.target.checked;render()};}
}
function candles(data,zones){const rows=data.filter(r=>['open','high','low','close'].every(k=>num(r[k]))).slice(-state.bars);if(rows.length<2)return '<div class="empty">No complete candles available for this timeframe.</div>';
 let low=Math.min(...rows.map(r=>r.low)),high=Math.max(...rows.map(r=>r.high));let range=high-low||1;let y=v=>230-(v-low)/range*190;const dx=650/rows.length,w=Math.max(1,dx*.65);
 let overlay=state.overlay?zones.filter(z=>z.valid&&z.upper>=low&&z.lower<=high).map(z=>'<rect x="40" y="'+y(Math.min(high,z.upper))+'" width="650" height="'+Math.max(1,y(Math.max(low,z.lower))-y(Math.min(high,z.upper)))+'" fill="#ffc980" opacity=".12"/>').join(''):'';
 let ticks=[0,1,2,3].map(i=>{const v=low+range*i/3;return '<line x1="40" y1="'+y(v)+'" x2="690" y2="'+y(v)+'" stroke="#29415a"/><text x="2" y="'+(y(v)-4)+'">'+esc(val(v))+'</text>'}).join('');
 const bars=rows.map((r,i)=>{const x=40+dx*(i+.5),color=r.close>=r.open?'#67e2a9':'#ffa1a1';return '<g><title>'+esc(when(r.time)+' | O '+r.open+' H '+r.high+' L '+r.low+' C '+r.close+' | Volume '+(r.volume??'missing'))+'</title><line x1="'+x+'" x2="'+x+'" y1="'+y(r.high)+'" y2="'+y(r.low)+'" stroke="'+color+'"/><rect x="'+(x-w/2)+'" y="'+Math.min(y(r.open),y(r.close))+'" width="'+w+'" height="'+Math.max(1,Math.abs(y(r.open)-y(r.close)))+'" fill="'+color+'"/></g>'}).join('');
 return '<svg class="chart" viewBox="0 0 710 260" role="img" aria-label="Closed '+esc(state.tf)+' OHLC candles">'+ticks+overlay+bars+'<text x="40" y="255">'+esc(rows[0].time.slice(0,10))+'</text><text x="590" y="255">'+esc(rows.at(-1).time.slice(0,10))+'</text></svg>';
}
async function loadFeed(){const feed=await fetchJSON('./data/snapshots.json',20000);if(!feed?.tickers)throw Error('Invalid snapshot file');for(const [symbol,current] of Object.entries(state.feed.tickers)){const incoming=feed.tickers[symbol];if(!incoming||Date.parse(current.retrieved_at_utc)>Date.parse(incoming.retrieved_at_utc))feed.tickers[symbol]=current;}state.feed=feed;tickerButtons();}
async function boot(){fetchJSON('./data/research.json',10000).then(r=>{state.research=r;if(state.ticker&&state.tab==='accuracy')render()}).catch(()=>{});try{state.config=await fetchJSON('./config.json',10000)}catch{state.config={}};
 if(el('personal-access'))el('personal-access').hidden=!state.config.personal_access_required;
 el('connection').textContent=state.config.same_origin_api||state.config.api_url?'On-demand Python analysis enabled. Any supported US/TSX ticker can be requested.':'Historical archive · Personal-data publication paused · Python hosting not connected';
 try{await loadFeed();const first=new URLSearchParams(location.search).get('ticker')||Object.keys(state.feed.tickers).find(k=>!state.feed.tickers[k].error);if(first)await selectTicker(first,false);else notify('No valid published data available.',true)}catch(e){notify('Published data unavailable: '+e.message,true)}
}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{state.tab=b.dataset.tab;if(state.ticker)render()});
el('search').onsubmit=e=>{e.preventDefault();selectTicker(el('ticker').value)};
setInterval(async()=>{if(document.hidden)return;try{await loadFeed();if(state.ticker)render()}catch(e){notify('Snapshot refresh failed: '+e.message,true)}},900000);
setInterval(()=>{if(state.ticker&&!document.hidden)render()},60000);
boot();
