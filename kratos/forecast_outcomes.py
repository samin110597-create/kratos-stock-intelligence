"""Score only forecasts recorded before the outcome session began."""
from datetime import datetime, timedelta, timezone
import pandas as pd
from .calendar import schedule


def resolve(record, completed_rows, now=None):
    forecast=record.get('engines',{}).get('qlib',{}).get('experimental_forecast')
    if not forecast:return None
    asof=pd.Timestamp(forecast['asof']).date()
    sessions=schedule(record['symbol'],asof+timedelta(days=1),asof+timedelta(days=14))
    if sessions.empty:return None
    target=sessions.iloc[0];day=str(sessions.index[0].date())
    recorded=pd.Timestamp(record['calculated_at_utc'])
    # A forecast created after the target session started is not a clean forward test.
    if recorded>=target.market_open:return None
    current=pd.Timestamp(now or datetime.now(timezone.utc))
    if current<target.market_close:return None
    row=next((r for r in completed_rows if r['time'][:10]==day),None)
    if row is None:return None
    actual=float(row['close'])/float(forecast['reference_close'])-1
    prediction=float(forecast['predicted_return'])
    return {'symbol':record['symbol'],'forecast_recorded_at_utc':record['calculated_at_utc'],
        'reference_session':str(asof),'outcome_session':day,
        'predicted_return':prediction,'actual_close_return':actual,
        'absolute_error':abs(actual-prediction),'no_change_absolute_error':abs(actual),
        'direction_correct':(prediction>0)==(actual>0) if prediction!=0 and actual!=0 else None,
        'evaluated_at_utc':current.isoformat(),
        'meaning':'Endpoint forecast error, not executable trading profit. Vendor history may be revised.'}
