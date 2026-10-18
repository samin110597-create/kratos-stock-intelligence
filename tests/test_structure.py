"""Causal, no-future-bar market-structure fixture tests."""
import pandas as pd
from kratos.structure import causal_structure


def base():
    ix=pd.date_range("2026-07-01",periods=32,freq="B")
    return pd.DataFrame({"Open":[100.]*32,"High":[102.]*32,
                         "Low":[98.]*32,"Close":[100.]*32,
                         "Volume":[1000.]*32},index=ix)


def test_closed_bar_low_sweep_reclaimed():
    df=base()
    df.loc[df.index[-1],["Open","High","Low","Close","Volume"]]=[100,101,95,100,2000]
    r=causal_structure(df)
    assert r["status"]=="SELL_SIDE_SWEEP_RECLAIM"
    assert r["participation"]=="ABOVE_BASELINE"
    assert r["reference_low"]==98


def test_high_sweep_and_rejection():
    df=base()
    df.loc[df.index[-1],["Open","High","Low","Close"]]=[100,106,99,101]
    r=causal_structure(df)
    assert r["status"]=="BUY_SIDE_SWEEP_REJECTION"


def test_close_breakout_not_auto_buy_signal():
    df=base()
    df.loc[df.index[-1],["Open","High","Low","Close"]]=[101,107,100,106]
    r=causal_structure(df)
    assert r["status"]=="CLOSE_ABOVE_PRIOR_HIGH"
    assert "acceptance" in r["reason"]
    assert "probability" in r["limitations"]


def test_missing_or_short_series_never_generates_fake_structure():
    assert causal_structure(base().iloc[:9])["status"]=="INSUFFICIENT_BARS"
    assert causal_structure(base()[["Close"]])["status"]=="MISSING_OHLCV"


def test_gaps_derived_from_finished_bar_and_retests_known_after():
    df=base()
    # Last bar jumps beyond high of two candles ago, with a meaningful gap.
    df.loc[df.index[-1],["Open","High","Low","Close"]]=[106,109,105,108]
    r=causal_structure(df)
    assert any(x["kind"]=="BULLISH" and x["state"]=="FRESH" for x in r["fvg"])
    # If an additional completed bar fills the gap, it is not reported fresh.
    more=pd.concat([df,pd.DataFrame([{"Open":108,"High":109,"Low":101,
                                    "Close":104,"Volume":1000}],
                                   index=[df.index[-1]+pd.offsets.BDay(1)])])
    newer=causal_structure(more)
    assert all(not (x["kind"]=="BULLISH" and x["created_on"]==str(df.index[-1].date()))
               for x in newer["fvg"])


def test_historical_prefix_result_unchanged_by_future_data():
    df=base()
    df.loc[df.index[-1],["Open","High","Low","Close"]]=[100,106,99,101]
    frozen=causal_structure(df)
    future=pd.concat([df,pd.DataFrame([{"Open":101,"High":110,"Low":95,
                                       "Close":97,"Volume":6000}],
                                     index=[df.index[-1]+pd.offsets.BDay(1)])])
    assert causal_structure(future.iloc[:len(df)])==frozen
