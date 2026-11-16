from kratos.forecast_outcomes import resolve


def record(time):
    return {'symbol':'NVDA','calculated_at_utc':time,'engines':{'qlib':{'experimental_forecast':{
        'asof':'2026-11-13T05:00:00Z','reference_close':100,'predicted_return':.02}}}}


def test_no_scoring_for_forecast_created_after_outcome_session_started():
    rows=[{'time':'2026-11-16T05:00:00Z','close':103}]
    assert resolve(record('2026-11-16T15:00:00Z'),rows,now='2026-11-17T00:00:00Z') is None


def test_missing_or_incomplete_outcome_is_not_a_success():
    r=record('2026-11-13T22:30:00Z')
    assert resolve(r,[],now='2026-11-17T00:00:00Z') is None
    assert resolve(r,[{'time':'2026-11-16T05:00:00Z','close':103}],now='2026-11-16T18:00:00Z') is None


def test_pre_session_forecast_scored_against_actual_close():
    r=resolve(record('2026-11-13T22:30:00Z'),[{'time':'2026-11-16T05:00:00Z','close':103}],now='2026-11-17T00:00:00Z')
    assert r['outcome_session']=='2026-11-16'
    assert abs(r['absolute_error']-.01)<1e-10
    assert r['direction_correct']
