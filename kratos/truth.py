"""Truth contract for displaying KRATOS market research.

Provenance is NOT an assertion that the upstream provider is accurate or
licensed-live. Block materially inconsistent timestamps; downgrade incomplete
research rather than filling gaps with zeros or invented probabilities.
"""
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo


class EvidenceError(ValueError):
    """Analysis contains internally inconsistent or untraceable data."""


def _utc(value, name):
    if not value:
        raise EvidenceError(f"{name} timestamp is missing")
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise EvidenceError(f"{name} timestamp is invalid") from exc
    if stamp.tzinfo is None:
        raise EvidenceError(f"{name} timestamp has no timezone")
    return stamp.astimezone(timezone.utc)


def _positive(value, name):
    try:
        x = float(value)
        if isfinite(x) and x > 0:
            return x
    except (TypeError, ValueError):
        pass
    raise EvidenceError(f"{name} is unavailable or nonpositive")


def build_evidence_report(snapshot, technical, decision, *, now=None):
    """Classify WHAT each claim actually is, not what it sounds like.

    Returns RESEARCH_ONLY for functioning free-data snapshots. No licensed
    real-time entitlement, dealer position, unverified probability, or
    predictive accuracy is created by this function.
    """
    evaluated = _utc(now or datetime.now(timezone.utc), "evaluation")
    retrieved = _utc(snapshot.retrieved_at, "retrieval")
    if retrieved > evaluated.replace(microsecond=evaluated.microsecond) and (retrieved - evaluated).total_seconds() > 5:
        raise EvidenceError("retrieval time occurs in the future")
    if not snapshot.provider or not str(snapshot.provider).strip():
        raise EvidenceError("market data provider is not identified")
    if not snapshot.ticker:
        raise EvidenceError("ticker is missing")
    _positive(technical.get("close"), "closed-bar reference price")
    bar_date = technical.get("asof_bar_date")
    if not bar_date:
        raise EvidenceError("completed price-bar date missing")
    try:
        closed_date = datetime.fromisoformat(str(bar_date)).date()
    except ValueError as exc:
        raise EvidenceError("completed bar date invalid") from exc
    if closed_date > retrieved.astimezone(ZoneInfo("America/Toronto")).date():
        raise EvidenceError("completed bar dated after provider retrieval")
    if decision.get("classification") == "BUY SETUP":
        raise EvidenceError("Unvalidated rule engine cannot publish an executable BUY SETUP")
    if decision.get("grade", "").startswith(("A+", "A ", "90%")):
        raise EvidenceError("Unvalidated probability/grade is prohibited")
    if any(k in decision for k in ("probability_up", "win_probability", "dealer_position")):
        raise EvidenceError("Unsupported quantitative confidence or institutional position")
    minute = snapshot.minute
    bar_time = None
    if minute is not None and not minute.empty:
        timestamp = minute.index[-1]
        if getattr(timestamp, "tzinfo", None) is None:
            raise EvidenceError("minute bar timezone missing")
        bar_time = _utc(timestamp.to_pydatetime(), "minute bar")
        if (bar_time - retrieved).total_seconds() > 120:
            raise EvidenceError("minute bar timestamp occurs after retrieval")
    source_age = max(0.0, (evaluated - retrieved).total_seconds() / 60)
    return {
        "policy_version": "truth-v1",
        "status": "RESEARCH_ONLY_NOT_VALIDATED_FOR_TRADING",
        "evaluated_at_utc": evaluated.isoformat(),
        "data_source": str(snapshot.provider),
        "data_retrieved_at_utc": retrieved.isoformat(),
        "source_minute_bar_at_utc": bar_time.isoformat() if bar_time else None,
        "retrieval_age_minutes": round(source_age, 1),
        "verified_live_entitlement": False,
        "independent_source_crosscheck": False,
        "verified_dealer_positions": False,
        "calibrated_prediction_probabilities": False,
        "measured_executable_trading_edge": False,
        "observations": [
            {"subject": "completed price history", "level": "PROVIDER_REPORTED",
             "meaning": "Prices reported by the named vendor; not independently cross-checked."},
            {"subject": "RSI/EMA/ATR/structure", "level": "CALCULATED",
             "meaning": "Deterministic formulas applied to vendor bars, not proof of future direction."},
            {"subject": "financial metadata", "level": "PROVIDER_REPORTED",
             "meaning": "May be missing/revised; not publication-dated primary financial filings."},
            {"subject": "buy zones, targets, and ATR sensitivity bands", "level": "HYPOTHESIS",
             "meaning": "Rule-derived illustrations; target order, timing and probabilities unvalidated."},
            {"subject": "dealer inventory / dark pool real-time flow", "level": "UNAVAILABLE",
             "meaning": "Not directly observable with the connected free feeds."},
        ],
        "hard_limits": [
            "No BUY signal or verified predictive edge is asserted.",
            "Recent fetch time is not proof of current exchange price.",
            "No source-backed catalyst verification is performed in this snapshot.",
            "Historical model tests are distinct from live-forward proof.",
        ],
    }
