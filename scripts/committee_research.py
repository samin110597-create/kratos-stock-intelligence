"""Run the actual upstream committee with a local free model on a hosted runner.

Opinion text is retained for audit but is not promoted to verified market facts.
"""
import json, os
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
config=DEFAULT_CONFIG.copy()
config.update(llm_provider='ollama',deep_think_llm='qwen2.5:3b',quick_think_llm='qwen2.5:3b',
 backend_url='http://localhost:11434/v1',max_debate_rounds=1,max_risk_discuss_rounds=1,
 max_tool_rounds=2,max_recur_limit=50,max_tokens=768,temperature=0,checkpoint_enabled=False,
 data_vendors={'core_stock_apis':'yfinance','technical_indicators':'yfinance','fundamental_data':'yfinance','news_data':'yfinance'})
started=datetime.now(timezone.utc).isoformat()
symbol='NVDA';day=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
committee=TradingAgentsGraph(selected_analysts=['market','fundamentals'],debug=False,config=config)
state,decision=committee.propagate(symbol,day)
reports={k:state.get(k) for k in ['market_report','fundamentals_report','investment_debate_state','risk_debate_state','investment_plan','trader_investment_plan','final_trade_decision']}
if not reports['market_report'] or not reports['final_trade_decision']:
 raise RuntimeError('Committee did not complete; no operational result published')
record={'symbol':symbol,'source':'TradingAgents tools / Yahoo Finance; AI opinions not independently verified',
 'data_last_session':day,'source_retrieved_at_utc':started,'calculated_at_utc':datetime.now(timezone.utc).isoformat(),
 'engines':{'tradingagents':{'status':'operational_historical','version':os.environ['TRADINGAGENTS_REVISION'],
 'method':'Actual TradingAgentsGraph market/fundamental analysts, bull/bear debate and risk committee with local Ollama qwen2.5:3b',
 'report_status':'UNVERIFIED_AI_OPINION_NOT_A_TRADE_SIGNAL','reports':reports,
 'limitations':['Small local model can make factual and reasoning errors. No accuracy or probability established.',
 'AI recommendations are withheld from the main trading plan; reports are audit material only.',
 'Only NVDA was run, with two analysts and limited tool/debate rounds. News analyst not included.']}}}
root=Path('site/data');(root/'committee-runs').mkdir(parents=True,exist_ok=True)
encoded=json.dumps(record,default=str,indent=2)
import hashlib
(root/'committee-runs'/(hashlib.sha256(encoded.encode()).hexdigest()+'.json')).write_text(encoded+'\n')
(root/'committee-latest.json').write_text(json.dumps({'tickers':{symbol:record}},default=str,indent=2)+'\n')
print('Actual committee completed; unverified opinions archived, no recommendation promoted.')
