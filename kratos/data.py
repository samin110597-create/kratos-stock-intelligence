"""Market data ingress. No synthetic prices, silent fallback, or imputed market bars."""
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import re
import pandas as pd

ET = ZoneInfo("America/Toronto")
_SYMBOL = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$")

class MarketDataError(RuntimeError):
    pass


def valid_symbol(symbol: str) -> str:
    ticker = str(symbol).strip().upper()
    if not _SYMBOL.fullmatch(ticker):
        raise ValueError("Enter a valid ticker, e.g. NVDA, CIFR, BRK-B or RY.TO.")
    return ticker


def tidy(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame = frame.copy().sort_index()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in frame.columns for c in required):
        raise MarketDataError("Price data is missing an OHLCV field.")
    frame = frame[required].dropna(subset=["Open", "High", "Low", "Close"])
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketDataError("Price bars have no datetime index.")
    frame = frame.loc[~frame.index.duplicated(keep="last")]
    # Treat missing volume as missing evidence, not fabricated zero-volume prints.
    return frame


def is_regular_session(now: datetime, symbol: str) -> bool:
    """Approximation for US/Canada exchange hours; holiday calendar not implemented.

    Unsupported global tickers return False, so a BUY is never misreported as live.
    """
    now = now.astimezone(ET)
    known = not any(symbol.endswith(ext) for ext in (".L", ".AX", ".HK", ".DE", ".PA", ".NS"))
    return known and now.weekday() < 5 and time(9, 30) <= now.time() < time(16, 0)


@dataclass
class MarketSnapshot:
    ticker: str
    daily: pd.DataFrame
    hourly: pd.DataFrame
    minute: pd.DataFrame
    fundamentals: dict
    provider: str
    retrieved_at: datetime
    warnings: list[str]

    def freshness(self, at: datetime | None = None) -> dict:
        now = at or datetime.now(timezone.utc)
        market_open = is_regular_session(now, self.ticker)
        if self.minute.empty:
            return {"market_open_estimate": market_open, "age_minutes": None,
                    "live_enough": False, "status": "INTRADAY UNAVAILABLE — daily research only",
                    "last_bar": None}
        stamp = self.minute.index[-1].to_pydatetime()
        if stamp.tzinfo is None:
            return {"market_open_estimate": market_open, "age_minutes": None,
                    "live_enough": False, "status": "UNVERIFIED timestamp timezone",
                    "last_bar": str(stamp)}
        raw_delta = (now - stamp.astimezone(timezone.utc)).total_seconds() / 60
        if raw_delta < -2:
            return {"market_open_estimate": market_open, "age_minutes": None,
                    "live_enough": False, "status": "FUTURE BAR TIMESTAMP — clock/provider mismatch",
                    "last_bar": stamp.astimezone(ET).strftime("%Y-%m-%d %I:%M %p %Z")}
        delta = max(0.0, raw_delta)
        if not market_open:
            status = "MARKET CLOSED / session unknown — last reported minute bar"
        elif delta <= 15:
            status = "RECENT reported minute bar (<=15 min); not proof of real-time entitlement"
        else:
            status = "STALE (>15 min) — no live trade signal"
        return {"market_open_estimate": market_open, "age_minutes": round(delta, 1),
                "live_enough": market_open and delta <= 15, "status": status,
                "last_bar": stamp.astimezone(ET).strftime("%Y-%m-%d %I:%M %p %Z")}


def fetch_snapshot(ticker: str) -> MarketSnapshot:
    """Yahoo Finance via yfinance (unofficial), with explicit partial-data warnings."""
    ticker = valid_symbol(ticker)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError("yfinance is not installed. Run pip install -r requirements.txt") from exc
    client = yf.Ticker(ticker)
    warnings = []

    def get_history(period: str, interval: str) -> pd.DataFrame:
        try:
            return tidy(client.history(period=period, interval=interval,
                                       auto_adjust=True, prepost=False,
                                       actions=False, timeout=12))
        except Exception as exc:
            warnings.append(f"{interval} data fetch failed: {type(exc).__name__}: {str(exc)[:130]}")
            return tidy(pd.DataFrame())

    daily = get_history("3y", "1d")
    if len(daily) < 65:
        raise MarketDataError(f"No sufficient real daily bars for {ticker} (need >=65). "
                              "No signal generated. Check symbol/provider availability.")
    hourly = get_history("60d", "60m")
    minute = get_history("5d", "1m")
    try:
        # Quote and fundamentals are independent of prices; failures are not silently hidden.
        fundamentals = client.get_info() or {}
    except Exception as exc:
        fundamentals = {}
        warnings.append(f"Fundamental API unavailable: {type(exc).__name__}")
    return MarketSnapshot(ticker, daily, hourly, minute, fundamentals,
                          "Yahoo Finance (unofficial yfinance feed)",
                          datetime.now(timezone.utc), warnings)
