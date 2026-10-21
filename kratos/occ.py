"""Personal-use OCC daily report retrieval; no invented schema or live OI claims."""
from datetime import date, datetime, timezone
import csv
import hashlib
import io
import httpx
from .connectors import ConnectorError

def fetch_daily_report(report_date,client=None):
    day=date.fromisoformat(report_date)
    if day>=datetime.now(timezone.utc).date(): raise ConnectorError('Use a completed reporting date')
    url='https://marketdata.theocc.com/daily-open-interest'
    try:
        r=(client or httpx.Client(timeout=30,follow_redirects=False)).get(url,params={'reportDate':day.strftime('%m/%d/%Y'),'action':'download','format':'csv'})
        if r.status_code!=200: raise ConnectorError(f'OCC: HTTP {r.status_code}; report unavailable')
        text=r.text
        if '<html' in text[:500].lower() or len(text)>50_000_000: raise ConnectorError('OCC: unexpected report format')
        rows=list(csv.DictReader(io.StringIO(text)))
        if not rows: raise ConnectorError('OCC: empty report')
    except ConnectorError: raise
    except Exception: raise ConnectorError('OCC: retrieval failure') from None
    return {'source':'OCC daily open interest','report_date':report_date,
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'publication_timestamp':None,
            'sha256':hashlib.sha256(text.encode()).hexdigest(),'columns':list(rows[0]),'rows':rows,
            'public_redistribution_enabled':False,'status':'Daily report; native columns require verified mapping before contract joins'}
