"""Generate real-source custom-data input and a strictly offline LEAN backtest config."""
import json
from pathlib import Path
from kratos.engine import analyze
from scripts.publish_snapshot import pack
root=Path('lean-work');(root/'prices').mkdir(parents=True,exist_ok=True)
p=pack('NVDA',analyze('NVDA'))
rows=p['technical']['candles']['1D']
for r in rows:
    day=r['time'][:10]
    (root/'prices'/(day+'.csv')).write_text(f'{day}T09:30:00,{r["open"]},0\n{day}T16:00:00,{r["close"]},1\n')
(root/'input.json').write_text(json.dumps({'symbol':'NVDA','source':p['provider'],'data_last_session':p['last_closed_bar_date'],'source_retrieved_at_utc':p['retrieved_at_utc'],'rows':rows}))
config={
 'environment':'backtesting','algorithm-type-name':'KratosResearch','algorithm-language':'Python',
 'algorithm-location':'/kratos/main.py','data-folder':'/Lean/Data','results-destination-folder':'/kratos/results',
 'live-mode':False,'debugging':False,'job-user-id':'0','api-access-token':'','job-organization-id':'',
 'log-handler':'QuantConnect.Logging.CompositeLogHandler','messaging-handler':'QuantConnect.Messaging.Messaging',
 'job-queue-handler':'QuantConnect.Queues.JobQueue','api-handler':'QuantConnect.Api.Api',
 'map-file-provider':'QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider',
 'factor-file-provider':'QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider',
 'data-provider':'QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider',
 'object-store':'QuantConnect.Lean.Engine.Storage.LocalObjectStore',
 'data-channel-provider':'DataChannelProvider',
 'parameters':{'start':rows[0]['time'][:10],'end':rows[-1]['time'][:10]},
 'environments':{'backtesting':{
 'live-mode':False,'setup-handler':'QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler',
 'result-handler':'QuantConnect.Lean.Engine.Results.BacktestingResultHandler',
 'data-feed-handler':'QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed',
 'real-time-handler':'QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler',
 'history-provider':['QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider'],
 'transaction-handler':'QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler'}}}
(root/'config.json').write_text(json.dumps(config))
(root/'main.py').write_text(Path('research/lean/main.py').read_text())
