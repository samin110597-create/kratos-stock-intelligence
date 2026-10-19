"""Kratos-inspired one-orchestrator / many deterministic skills.

NOT the upstream Microsoft Foundry/Copilot SDK agent. See KRATOS_INTEGRATION.md.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from .patterns import inspect
from .data import fetch_snapshot, MarketSnapshot
from .decision import propose_setup
from .fundamentals import report
from .technicals import build_technicals

@dataclass
class ResearchResult:
    snapshot: MarketSnapshot
    technical: dict
    decision: dict
    freshness: dict
    facts: list
    valuation_note: str


def analyze(ticker: str, *, snapshot: MarketSnapshot | None = None) -> ResearchResult:
    snap = snapshot if snapshot is not None else fetch_snapshot(ticker)
    tech = build_technicals(snap.daily, snap.hourly, quarter=snap.quarter, symbol=snap.ticker)
    tech["structure"] = {key:inspect(frame) for key,frame in tech["frames"].items()}
    freshness = snap.freshness()
    decision = propose_setup(tech, freshness)
    tech["observation_reference"] = snap.quote
    tech["provenance"] = snap.provenance
    tech["corporate_actions"] = snap.actions
    facts, note = report(snap.fundamentals)
    return ResearchResult(snap, tech, decision, freshness, facts, note)
