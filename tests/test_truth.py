"""KRATOS truth-contract tests: synthetic data are fixtures, NEVER market quotes."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from kratos.truth import EvidenceError, build_evidence_report

NOW=datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)


def sample(*, retrieved=NOW, minute_time=None, asof="2026-10-19", decision=None):
    timestamp=minute_time or NOW-timedelta(minutes=3)
    minute=pd.DataFrame({"Close":[100.]}, index=pd.DatetimeIndex([timestamp]))
    snap=SimpleNamespace(
        ticker="NVDA", provider="TEST FIXTURE — NOT MARKET DATA",
        retrieved_at=retrieved, minute=minute
    )
    technical={"close":100., "asof_bar_date":asof}
    decision=decision or {"classification":"WAIT","grade":"NO RELIABLE EDGE"}
    return snap,technical,decision


def test_explicit_classification_and_no_smart_money_or_accuracy_claims():
    report=build_evidence_report(*sample(), now=NOW+timedelta(seconds=1))
    assert report["status"]=="RESEARCH_ONLY_NOT_VALIDATED_FOR_TRADING"
    assert not report["verified_live_entitlement"]
    assert not report["verified_dealer_positions"]
    assert not report["calibrated_prediction_probabilities"]
    assert not report["measured_executable_trading_edge"]
    assert {"PROVIDER_REPORTED","CALCULATED","HYPOTHESIS","UNAVAILABLE"} == {
        x["level"] for x in report["observations"]
    }


def test_future_retrieval_is_not_relabelled_fresh():
    with pytest.raises(EvidenceError, match="future"):
        build_evidence_report(*sample(retrieved=NOW+timedelta(minutes=6)),
                              now=NOW)


def test_future_market_bar_is_rejected():
    with pytest.raises(EvidenceError, match="after retrieval"):
        build_evidence_report(*sample(minute_time=NOW+timedelta(minutes=3)),
                              now=NOW)


def test_incomplete_daily_date_is_rejected():
    with pytest.raises(EvidenceError, match="after provider retrieval"):
        build_evidence_report(*sample(asof="2026-11-01"), now=NOW)


def test_invalid_reference_price_is_rejected():
    snap,tech,dec=sample()
    tech["close"]=float("nan")
    with pytest.raises(EvidenceError, match="reference price"):
        build_evidence_report(snap,tech,dec,now=NOW)


def test_unsupported_buy_grade_or_probability_are_rejected():
    snap,tech,dec=sample()
    with pytest.raises(EvidenceError, match="BUY"):
        build_evidence_report(snap,tech,{"classification":"BUY SETUP"},now=NOW)
    with pytest.raises(EvidenceError, match="confidence"):
        build_evidence_report(snap,tech,{"classification":"WAIT","probability_up":0.9},now=NOW)


def test_missing_provider_or_naive_datetime_rejected():
    snap,tech,dec=sample()
    snap.provider=""
    with pytest.raises(EvidenceError, match="provider"):
        build_evidence_report(snap,tech,dec,now=NOW)
    snap.provider="TEST FIXTURE"
    snap.retrieved_at=datetime(2026,10,20,16)
    with pytest.raises(EvidenceError, match="timezone"):
        build_evidence_report(snap,tech,dec,now=NOW)
