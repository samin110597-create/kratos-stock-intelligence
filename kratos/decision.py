"""Public decision entry point for closed-bar structural research."""
from .price_plan import build_plan

def propose_setup(t: dict, freshness: dict) -> dict:
    return build_plan(t.get('frames', {'1D':t.get('daily')}), live_enough=freshness.get('live_enough',False))
