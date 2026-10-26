// DOM integration tests. No fixture is saved into the public market-data files.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync('site/index.html','utf8');
const feed=JSON.parse(fs.readFileSync('site/data/snapshots.json','utf8'));
const research=JSON.parse(fs.readFileSync('site/data/research.json','utf8'));
(async()=>{
const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://example.test/'});
const w=dom.window; const errors=[];
w.addEventListener('error',e=>errors.push(e.message));
w.fetch=async url=>({ok:true,json:async()=>String(url).includes('config.json')?{same_origin_api:false}:String(url).includes('research.json')?research:String(url).includes('plans.json')?JSON.parse(fs.readFileSync('site/data/plans.json','utf8')):structuredClone(feed)});
w.AbortController=AbortController;
w.eval(fs.readFileSync('site/app.js','utf8')+'\nwindow.__test={selectTicker,freshness,state};');
await new Promise(r=>setTimeout(r,50));
assert.equal(w.document.getElementById('dashboard').hidden,false);
let visited=0;
for(const tab of w.document.querySelectorAll('.tab')){
 tab.click();if(tab.dataset.tab==='forecast'){assert.match(w.document.getElementById('view').textContent,/The price plan/);assert.match(w.document.getElementById('view').textContent,/Historical re-analysis/);assert(!w.document.getElementById('view').textContent.includes('ATR ×'));}assert.equal(tab.getAttribute('aria-selected'),'true');assert(w.document.getElementById('view').textContent.length>30);visited++;
}
assert.equal(visited,8);assert.deepEqual(errors,[]);
w.eval("window.__test.selectTicker('../etc/passwd',false)");assert.match(w.document.getElementById('status').textContent,/valid US or Canadian/);
await w.eval("window.__test.selectTicker('NOTCOVERED',false)");assert(w.document.getElementById('dashboard').hidden);
assert.match(w.document.getElementById('status').textContent,/no published snapshot/);
const status=w.eval(`window.__test.freshness({analysis_version:'rules-v2.0.0',minute_bar_utc:'2026-12-25T16:00:00Z',session_schedule:[{date:'2026-12-24',open_utc:'2026-12-24T14:30:00Z',close_utc:'2026-12-24T18:00:00Z'},{date:'2026-12-28',open_utc:'2026-12-28T14:30:00Z',close_utc:'2026-12-28T21:00:00Z'}]},Date.parse('2026-12-25T16:01:00Z'))`);
assert.equal(status.open,false);assert.equal(status.live,false);
const future=w.eval(`window.__test.freshness({analysis_version:'rules-v2.0.0',minute_bar_utc:'2026-10-19T15:05:00Z',session_schedule:[{date:'2026-10-19',open_utc:'2026-10-19T13:30:00Z',close_utc:'2026-10-19T20:00:00Z'}]},Date.parse('2026-10-19T15:00:00Z'))`);
assert.equal(future.live,false);
// Hosted path: an arbitrary ticker must call the backend with the service token.
w.__test.state.config={api_url:'https://backend.example.test',personal_access_required:true};
let requested=0;
w.fetch=async (url,options)=>{requested++;assert.equal(url,'https://backend.example.test/api/analyze?symbol=AAPL');assert.equal(options.headers.Authorization,'Bearer fixture-token');const x=structuredClone(feed.tickers.NVDA);x.ticker='AAPL';return {ok:true,json:async()=>({ticker:x})};};
await w.__test.selectTicker('AAPL');assert.equal(requested,0);assert.match(w.document.getElementById('status').textContent,/access token/);
w.document.getElementById('access-token').value='fixture-token';
await w.__test.selectTicker('AAPL');assert.equal(requested,1);assert.equal(w.document.getElementById('dashboard').hidden,false);assert.match(w.document.getElementById('status').textContent,/AAPL/);
console.log(JSON.stringify({tabs:visited,uncaughtErrors:errors.length,invalidSymbols:'pass',unknownTicker:'pass',holiday:'pass',futureTimestamp:'pass'}));
dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
