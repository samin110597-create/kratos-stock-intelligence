import pandas as pd
from unittest.mock import patch
from kratos.calendar import weekly_closed, schedule


def test_weekly_calendar_uses_one_lookup_and_preserves_holiday_close():
    # Good Friday is closed: the completed week is available after Thursday close.
    index=pd.date_range('2024-01-05','2026-04-10',freq='W-FRI')
    frame=pd.DataFrame({'Close':100.},index=index)
    with patch('kratos.calendar.schedule',wraps=schedule) as lookup:
        closed=weekly_closed(frame,pd.Timestamp('2026-04-02T20:01:00Z'),'AAPL')
    assert lookup.call_count==1
    assert closed.index[-1]==pd.Timestamp('2026-04-03')
    assert pd.Timestamp('2026-04-10') not in closed.index
