"""Offline, deterministic option-greek and signed-OI scenario tests.

No network, licensing, or claimed dealer positioning involved.
"""
from datetime import datetime, timezone
from math import isclose
from kratos.options_research import greeks, exposure_book

NOW=datetime(2026,10,15,15,0,tzinfo=timezone.utc)


def sample(strike=100.0, call_oi=1000, put_oi=1000):
    return [
        {"expiry":"2026-11-20","type":"call","strike":strike,
         "open_interest":call_oi,"iv":0.3,"bid":4,"ask":5},
        {"expiry":"2026-11-20","type":"put","strike":strike,
         "open_interest":put_oi,"iv":0.3,"bid":3,"ask":4}
    ]


def test_greeks_call_put_gamma_same_sign_and_delta_differs():
    call=greeks(100,100,.3,.1,"call")
    put=greeks(100,100,.3,.1,"put")
    assert 0<call["delta"]<1
    assert -1<put["delta"]<0
    assert isclose(call["gamma"], put["gamma"], rel_tol=1e-12)
    assert all(abs(call[k])<2 for k in ("vanna","charm_per_day"))


def test_identical_call_put_gamma_cancel_only_in_assumed_sign_scenario():
    b=exposure_book(100,sample(),asof=NOW)
    assert b["valid_contracts"]==2
    assert abs(b["net_scenario_gex_1pct_usd"])<1e-6
    assert b["king_strike_by_gross_gex"]==100
    assert b["call_wall_strike"]==100
    assert b["put_wall_strike"]==100
    assert b["net_scenario_dex_usd"] != 0
    assert "unverified" in b["scenario_assumption"]


def test_dominant_call_does_not_establish_dealer_direction():
    b=exposure_book(100,sample(call_oi=4000,put_oi=100),asof=NOW)
    assert b["net_scenario_gex_1pct_usd"]>0
    assert "NOT" in b["interpretation"] or "not" in b["interpretation"]
    assert b["atm_straddle"]["illustrative_85pct_straddle_move"]==6.8


def test_invalid_chain_contracts_rejected():
    rows=sample()+[
       {"expiry":"2026-11-20","type":"call","strike":100,"iv":-3,"open_interest":99},
       {"expiry":"2026-11-20","type":"put","strike":100,"iv":0.2,"open_interest":0},
       {"expiry":"2020-01-01","type":"call","strike":100,"iv":.2,"open_interest":123}
    ]
    b=exposure_book(100,rows,asof=NOW)
    assert b["valid_contracts"]==2
    assert b["rejected_contracts"]==3


def test_no_bid_ask_means_no_straddle_move():
    rows=sample()
    rows[0]["bid"]=0
    b=exposure_book(100,rows,asof=NOW)
    assert b["atm_straddle"] is None


def test_flip_is_unknown_when_no_zero_crossing():
    b=exposure_book(100,sample(call_oi=1000,put_oi=0),asof=NOW)
    assert b["scenario_gamma_flip"] is None


def test_time_must_be_aware():
    try:
        exposure_book(100,sample(),asof=datetime(2026,10,15))
    except ValueError:
        pass
    else:
        assert False, "naive timestamps must be rejected"


def test_completely_empty_book_has_no_levels():
    b=exposure_book(100,[],asof=NOW)
    assert b["valid_contracts"]==0
    assert b["king_strike_by_gross_gex"] is None
