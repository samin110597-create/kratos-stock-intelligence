"""Daily-only account adapter. Missing intraday coverage remains unavailable."""
from datetime import datetime, timezone
import pandas as pd
from .connectors import Connectors

class AlphaDailyProvider:
    name='Alpha Vantage compact daily (account feed)'
    def fetch(self,ticker):
        from .data import MarketSnapshot,tidy
        from .calendar import calendar_name
        if calendar_name(ticker)!='NYSE': raise ValueError('TSX symbol mapping unverified for this adapter')
        response=Connectors().fetch('alpha_vantage',ticker)
        values=response['payload']['Time Series (Daily)']
        frame=pd.DataFrame.from_dict(values,orient='index').rename(columns={'1. open':'Open','2. high':'High','3. low':'Low','4. close':'Close','5. volume':'Volume'})
        frame.index=pd.to_datetime(frame.index);frame=tidy(frame.sort_index())
        empty=tidy(None)
        return MarketSnapshot(ticker,frame,empty,empty,{},self.name,datetime.fromisoformat(response['retrieved_at_utc']),
            ['Daily-only compact history; intraday analysis and current quote unavailable.',
             'No point-in-time corporate-action archive; probabilities remain unvalidated.'],quarter=empty,
            provenance={'calendar':'NYSE','currency':None,'reported_delay_minutes':None,'entitlement':'Daily endpoint retrieval verified; live entitlement unavailable','price_adjustment':'TIME_SERIES_DAILY raw OHLC; provider revisions possible'})
