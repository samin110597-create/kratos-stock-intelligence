"""Source-conscious fundamental facts and *scenario* multiples, not invented intrinsic values."""
import math

_FIELDS = [
    ("longName", "Company", "str"), ("sector", "Sector", "str"),
    ("currency", "Currency", "str"), ("marketCap", "Market capitalization", "money"),
    ("totalRevenue", "Revenue (ttm)", "money"),
    ("freeCashflow", "Free cash flow (reported)", "money"),
    ("totalCash", "Total cash", "money"), ("totalDebt", "Total debt", "money"),
    ("revenueGrowth", "Revenue growth", "percent"),
    ("earningsGrowth", "Earnings growth", "percent"),
    ("profitMargins", "Net profit margin", "percent"),
    ("returnOnEquity", "Return on equity", "percent"),
    ("trailingPE", "Trailing P/E", "number"),
    ("forwardPE", "Forward P/E", "number"),
    ("priceToBook", "Price/book", "number"),
    ("forwardEps", "Forward EPS", "number"),
    ("trailingEps", "Trailing EPS", "number"),
]


def pretty(v, fmt):
    if v is None or v == "":
        return "Unavailable"
    if fmt == "str":
        return str(v)
    try:
        v = float(v)
        if not math.isfinite(v):
            return "Unavailable"
        if fmt == "percent": return f"{v*100:.1f}%"
        if fmt == "money":
            for unit, div in (("T", 1e12), ("B",1e9), ("M",1e6)):
                if abs(v) >= div: return f"{v/div:,.2f}{unit}"
            return f"{v:,.0f}"
        return f"{v:,.2f}"
    except (TypeError, ValueError):
        return "Unavailable"


def report(info: dict) -> tuple[list[tuple[str, str]], str]:
    info = info or {}
    facts = [(label, pretty(info.get(k), kind)) for k,label,kind in _FIELDS]
    fwd_eps = info.get("forwardEps")
    sector = str(info.get("sector") or "").lower()
    # Deliberately do NOT apply P/E to banks, pre-revenue firms, or loss makers.
    if "financial" in sector or "bank" in sector:
        note = ("Bank/financial business: P/E scenarios and generic cash-flow DCF deliberately omitted. "
                "Use verified tangible book, normalized ROTCE, capital and credit-loss analysis before pricing.")
    else:
        try:
            eps = float(fwd_eps)
            if eps > 0 and math.isfinite(eps):
                scenarios = ", ".join(f"{m}× P/E → {eps*m:,.2f}" for m in (12,16,20))
                note = ("Illustrative forward-EPS multiple SENSITIVITY ONLY (not intrinsic value, "
                        "not a buy recommendation; currency per info if available): " + scenarios +
                        ". Assumptions are arbitrary illustrative multiples, not peer-derived.")
            else:
                note = "Forward EPS absent/nonpositive: meaningful EPS valuation scenario unavailable. No fair value asserted."
        except (TypeError, ValueError):
            note = "Forward EPS unavailable: no fair value asserted."
    if not info:
        note = "Fundamental provider returned no usable facts. No valuation conclusion possible."
    return facts, note
