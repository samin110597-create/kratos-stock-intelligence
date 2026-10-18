"""Kratos-inspired one-orchestrator / many deterministic skills.

NOT the upstream Microsoft Foundry/Copilot SDK agent. See KRATOS_INTEGRATION.md.
"""
from dataclasses import dataclass
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
    tech = build_technicals(snap.daily, snap.hourly)
    freshness = snap.freshness()
    decision = propose_setup(tech, freshness)
    facts, note = report(snap.fundamentals)
    return ResearchResult(snap, tech, decision, freshness, facts, note)
