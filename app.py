"""Jari Tradin Ai — a read-only cryptocurrency market dashboard."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots


# ----------------------------- Easy settings -----------------------------
# Edit this list to add or remove the coins shown in the market table.
WATCH_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "TRXUSDT",
    "TONUSDT",
)

TIMEFRAMES = {
    "15 minutes": "15m",
    "1 hour": "1h",
    "4 hours": "4h",
    "1 day": "1d",
}

# Kraken public REST API. No account or API key is required for these endpoints.
KRAKEN_API_HOST = "https://api.kraken.com"

# JARI keeps its familiar *USDT internal symbols. Kraken uses XBT for Bitcoin.
# If Kraken does not list one of these markets, that coin is simply shown as unavailable.
KRAKEN_PAIRS = {
    "BTCUSDT": "XBTUSDT",
    "ETHUSDT": "ETHUSDT",
    "XRPUSDT": "XRPUSDT",
    "SOLUSDT": "SOLUSDT",
    "BNBUSDT": "BNBUSDT",
    "DOGEUSDT": "DOGEUSDT",
    "ADAUSDT": "ADAUSDT",
    "AVAXUSDT": "AVAXUSDT",
    "LINKUSDT": "LINKUSDT",
    "LTCUSDT": "LTCUSDT",
    "TRXUSDT": "TRXUSDT",
    "TONUSDT": "TONUSDT",
}

KRAKEN_INTERVALS = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

st.set_page_config(
    page_title="Jari Tradin Ai",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(ellipse at 78% 0%, rgba(20, 88, 128, .20), transparent 35%),
            linear-gradient(145deg, #07111d 0%, #091522 55%, #07101b 100%);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: rgba(7, 17, 29, .96);
        border-right: 1px solid rgba(90, 190, 220, .14);
    }
    .block-container {
        max-width: 1500px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(17, 35, 52, .92), rgba(11, 25, 39, .92));
        border: 1px solid rgba(91, 185, 217, .16);
        border-radius: 14px;
        padding: 16px 18px;
        min-height: 112px;
    }
    [data-testid="stMetricLabel"] { color: #91a9bc; }
    [data-testid="stMetricValue"] { color: #edf8ff; }
    [data-testid="stMetricDelta"] { font-size: .9rem; }
    .jari-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 0 0 8px;
    }
    .jari-mark {
        display: grid;
        place-items: center;
        width: 54px;
        height: 54px;
        border: 1px solid rgba(59, 216, 255, .65);
        border-radius: 50%;
        color: #51ddff;
        font-size: 25px;
        box-shadow: 0 0 26px rgba(36, 191, 239, .18), inset 0 0 16px rgba(36, 191, 239, .10);
    }
    .jari-title {
        color: #eaf7ff;
        font-size: clamp(1.8rem, 3vw, 2.55rem);
        font-weight: 700;
        letter-spacing: .08em;
        line-height: 1.1;
    }
    .jari-subtitle {
        color: #86a2b8;
        font-size: .78rem;
        letter-spacing: .17em;
        margin-top: 7px;
        text-transform: uppercase;
    }
    .eyebrow {
        color: #58d9f6;
        font-size: .73rem;
        font-weight: 700;
        letter-spacing: .16em;
        text-transform: uppercase;
    }
    .signal-box {
        border: 1px solid rgba(91, 185, 217, .18);
        border-radius: 15px;
        background: linear-gradient(115deg, rgba(16, 34, 50, .96), rgba(10, 23, 37, .96));
        padding: 20px 22px;
        margin: 2px 0 18px;
    }
    .signal-label {
        display: inline-block;
        padding: 7px 12px;
        border-radius: 7px;
        font-size: .85rem;
        font-weight: 800;
        letter-spacing: .08em;
    }
    .signal-buy {
        color: #6cf2bf;
        background: rgba(34, 197, 144, .12);
        border: 1px solid rgba(78, 225, 175, .34);
    }
    .signal-sell {
        color: #ff8795;
        background: rgba(255, 88, 111, .11);
        border: 1px solid rgba(255, 111, 130, .34);
    }
    .signal-wait {
        color: #a9c0d3;
        background: rgba(130, 157, 182, .10);
        border: 1px solid rgba(150, 179, 202, .24);
    }
    .signal-copy {
        color: #a7bdce;
        font-size: .9rem;
        line-height: 1.55;
        margin-top: 10px;
    }
    .live-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #55e3b5;
        box-shadow: 0 0 10px rgba(85, 227, 181, .8);
        margin-right: 8px;
        vertical-align: middle;
    }
    .soft-note {
        color: #8ba2b5;
        font-size: .83rem;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(91, 185, 217, .15);
        border-radius: 12px;
        overflow: hidden;
    }
    
        /* Backtest readability */
        .backtest-panel {
            margin-top: 8px;
            padding: 18px 18px 12px 18px;
            border: 1px solid rgba(92, 211, 255, .18);
            border-radius: 16px;
            background: rgba(8, 27, 42, .72);
        }
        .backtest-panel h3 {
            color: #eaf7ff !important;
            margin: 0 0 8px 0;
        }
        .backtest-copy {
            color: #a9c0d3 !important;
            line-height: 1.55;
            margin-bottom: 8px;
        }
        .backtest-note {
            color: #91aabd !important;
            line-height: 1.5;
            margin-top: 10px;
        }
        div[data-testid="stSlider"] label,
        div[data-testid="stSlider"] p {
            color: #d8eaf5 !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(92, 211, 255, .16);
            border-radius: 12px;
            overflow: hidden;
        }
        div[data-testid="stExpander"] details {
            border-color: rgba(92, 211, 255, .16) !important;
            background: rgba(8, 27, 42, .58) !important;
        }
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            color: #d8eaf5 !important;
        }


        /* ===== Global JARVIS readability pass ===== */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            color: #dcecf6 !important;
        }

        [data-testid="stAppViewContainer"] p,
        [data-testid="stAppViewContainer"] li,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] span {
            color: #b8cddd;
        }

        [data-testid="stAppViewContainer"] h1,
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4 {
            color: #edf8ff !important;
        }

        [data-testid="stSidebar"] {
            background: rgba(5, 18, 29, .98) !important;
            border-right: 1px solid rgba(92, 211, 255, .14);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] li,
        [data-testid="stSidebar"] span {
            color: #bcd2e1 !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #edf8ff !important;
        }

        /* Select boxes */
        div[data-baseweb="select"] > div {
            background: #f7fbfe !important;
            border-color: rgba(92, 211, 255, .25) !important;
        }
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div {
            color: #122638 !important;
        }

        /* Sliders */
        div[data-testid="stSlider"] label,
        div[data-testid="stSlider"] p {
            color: #d8eaf5 !important;
        }

        /* Metrics */
        [data-testid="stMetric"] {
            background: rgba(12, 37, 55, .72);
            border: 1px solid rgba(92, 211, 255, .18);
            border-radius: 14px;
            padding: 12px 14px;
        }
        [data-testid="stMetricLabel"] p {
            color: #9fb9cb !important;
        }
        [data-testid="stMetricValue"] {
            color: #f1f9ff !important;
        }

        /* Captions / muted helper text */
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: #9fb8c9 !important;
        }

        /* Dataframes */
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(92, 211, 255, .18);
            border-radius: 12px;
            overflow: hidden;
        }

        /* Expanders */
        div[data-testid="stExpander"] details {
            background: rgba(9, 29, 44, .72) !important;
            border: 1px solid rgba(92, 211, 255, .16) !important;
            border-radius: 12px !important;
        }
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            color: #dcecf6 !important;
        }

        /* Alerts */
        [data-testid="stAlert"] p {
            color: #e3eff6 !important;
        }

        /* Dividers */
        hr {
            border-color: rgba(92, 211, 255, .14) !important;
        }

        /* Existing custom text classes */
        .soft-note, .signal-copy {
            color: #afc6d6 !important;
        }
        .eyebrow {
            color: #58ddff !important;
        }

        /* Plotly chart labels are rendered inside the chart; give chart container contrast */
        [data-testid="stPlotlyChart"] {
            border-radius: 14px;
            overflow: hidden;
        }

</style>
    """,
    unsafe_allow_html=True,
)


def kraken_get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Get public Kraken market data without an API key."""
    try:
        response = requests.get(
            f"{KRAKEN_API_HOST}/0/public/{endpoint}",
            params=params,
            headers={"User-Agent": "JariTradinAi/1.0"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise RuntimeError(
            "Kraken public market data is temporarily unavailable. "
            f"Please try again in a moment. Details: {str(error)[:180]}"
        ) from error

    errors = payload.get("error", [])
    if errors:
        raise RuntimeError("Kraken API error: " + "; ".join(errors))
    return payload.get("result", {})


def _kraken_result_rows(result: dict[str, Any]) -> list[list[Any]]:
    """Return the OHLC rows while ignoring Kraken's metadata fields."""
    for key, value in result.items():
        if key != "last" and isinstance(value, list):
            return value
    return []


def fetch_candles(symbol: str, interval: str, candle_count: int) -> list[list[Any]]:
    """Download one coin's recent OHLC candles from Kraken."""
    pair = KRAKEN_PAIRS[symbol]
    result = kraken_get(
        "OHLC",
        {"pair": pair, "interval": KRAKEN_INTERVALS[interval]},
    )
    rows = _kraken_result_rows(result)
    return rows[-candle_count:]


def fetch_ticker(symbol: str) -> dict[str, Any]:
    """Download one coin's latest ticker from Kraken."""
    pair = KRAKEN_PAIRS[symbol]
    result = kraken_get("Ticker", {"pair": pair})
    for value in result.values():
        if isinstance(value, dict):
            return value
    return {}


@st.cache_data(ttl=20, show_spinner=False)
def load_market_snapshot(
    interval: str, symbols: tuple[str, ...], candle_count: int
) -> tuple[dict[str, dict[str, Any]], dict[str, list[list[Any]]], str | None]:
    """Load Kraken tickers and candle history; tolerate unavailable individual coins."""
    tickers: dict[str, dict[str, Any]] = {}
    candles: dict[str, list[list[Any]]] = {}

    def load_one(symbol: str) -> tuple[str, dict[str, Any], list[list[Any]]]:
        ticker = fetch_ticker(symbol)
        history = fetch_candles(symbol, interval, candle_count)
        return symbol, ticker, history

    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(load_one, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                loaded_symbol, ticker, history = future.result()
                tickers[loaded_symbol] = ticker
                candles[loaded_symbol] = history
            except Exception as error:
                tickers[symbol] = {}
                candles[symbol] = []
                errors.append(f"{symbol}: {error}")

    if not tickers or all(not value for value in tickers.values()):
        detail = errors[0] if errors else "unknown connection error"
        return {}, {}, f"Kraken public market data is unavailable. Details: {detail[:180]}"

    return tickers, candles, None


def candles_to_frame(raw_candles: list[list[Any]]) -> pd.DataFrame:
    """Turn Kraken OHLC rows into named columns and calculate indicators."""
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "vwap",
        "volume",
        "trade_count",
    ]
    frame = pd.DataFrame(raw_candles, columns=columns)
    if frame.empty:
        return frame

    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["time"] = pd.to_datetime(frame["open_time"], unit="s", utc=True)
    change = frame["close"].diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    average_loss = losses.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    frame["rsi"] = 100 - (100 / (1 + relative_strength))
    frame.loc[(average_loss == 0) & (average_gain > 0), "rsi"] = 100
    frame.loc[(average_gain == 0) & (average_loss > 0), "rsi"] = 0
    frame.loc[(average_gain == 0) & (average_loss == 0), "rsi"] = 50
    frame["ema20"] = frame["close"].ewm(span=20, min_periods=20, adjust=False).mean()
    frame["ema50"] = frame["close"].ewm(span=50, min_periods=50, adjust=False).mean()
    frame["ema200"] = frame["close"].ewm(span=200, min_periods=200, adjust=False).mean()

    ema12 = frame["close"].ewm(span=12, adjust=False).mean()
    ema26 = frame["close"].ewm(span=26, adjust=False).mean()
    frame["macd"] = ema12 - ema26
    frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
    frame["macd_hist"] = frame["macd"] - frame["macd_signal"]

    # ATR (14): Wilder-style volatility measure.
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()
    frame["atr_percent"] = (frame["atr"] / frame["close"]) * 100

    # Volume analysis: compare the latest candle with the recent 20-candle average.
    frame["volume_avg20"] = frame["volume"].rolling(20).mean()
    frame["volume_ratio"] = frame["volume"] / frame["volume_avg20"]
    return frame



def get_setup_score(frame: pd.DataFrame) -> dict[str, Any]:
    """Score long and short conditions separately using transparent indicator rules."""
    if frame.empty:
        return {"direction": "WAIT", "score": 0, "long_score": 0, "short_score": 0, "reasons": []}

    latest = frame.iloc[-1]
    required = (
        "close", "ema20", "ema50", "ema200", "rsi",
        "macd", "macd_signal", "atr_percent", "volume_ratio",
    )
    if any(pd.isna(latest[column]) for column in required):
        return {"direction": "WAIT", "score": 0, "long_score": 0, "short_score": 0,
                "reasons": ["Indicators are still building."]}

    price = float(latest["close"])
    ema20 = float(latest["ema20"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    rsi = float(latest["rsi"])
    macd = float(latest["macd"])
    macd_signal = float(latest["macd_signal"])
    atr_pct = float(latest["atr_percent"])
    volume_ratio = float(latest["volume_ratio"])

    long_score = 0
    short_score = 0
    long_reasons: list[str] = []
    short_reasons: list[str] = []

    # Trend: max 30 points.
    if price > ema20 > ema50 > ema200:
        long_score += 30
        long_reasons.append("Strong bullish EMA structure")
    elif price > ema50 > ema200:
        long_score += 20
        long_reasons.append("Bullish medium/long trend")
    elif price > ema200:
        long_score += 10
        long_reasons.append("Price above EMA200")

    if price < ema20 < ema50 < ema200:
        short_score += 30
        short_reasons.append("Strong bearish EMA structure")
    elif price < ema50 < ema200:
        short_score += 20
        short_reasons.append("Bearish medium/long trend")
    elif price < ema200:
        short_score += 10
        short_reasons.append("Price below EMA200")

    # Momentum: max 30 points.
    if macd > macd_signal:
        long_score += 15
        long_reasons.append("MACD bullish")
    elif macd < macd_signal:
        short_score += 15
        short_reasons.append("MACD bearish")

    if 50 <= rsi <= 68:
        long_score += 15
        long_reasons.append("RSI supports bullish momentum")
    elif 32 <= rsi < 50:
        short_score += 15
        short_reasons.append("RSI supports bearish momentum")
    elif 68 < rsi < 75:
        long_score += 7
        long_reasons.append("Bullish RSI, but getting extended")
    elif 25 < rsi < 32:
        short_score += 7
        short_reasons.append("Bearish RSI, but getting extended")

    # Volume confirmation: max 20 points.
    if volume_ratio >= 1.5:
        if long_score >= short_score:
            long_score += 20
            long_reasons.append("High volume confirmation")
        else:
            short_score += 20
            short_reasons.append("High volume confirmation")
    elif volume_ratio >= 1.0:
        if long_score >= short_score:
            long_score += 12
            long_reasons.append("Above-average volume")
        else:
            short_score += 12
            short_reasons.append("Above-average volume")
    elif volume_ratio >= 0.7:
        if long_score >= short_score:
            long_score += 6
        else:
            short_score += 6

    # Volatility quality: max 20 points. Extremely quiet or very wild markets score less.
    if 0.35 <= atr_pct <= 2.5:
        volatility_points = 20
        volatility_reason = "Usable volatility"
    elif 0.20 <= atr_pct < 0.35 or 2.5 < atr_pct <= 4.0:
        volatility_points = 10
        volatility_reason = "Moderate setup volatility"
    else:
        volatility_points = 0
        volatility_reason = "Volatility outside preferred range"

    if long_score >= short_score:
        long_score += volatility_points
        if volatility_points:
            long_reasons.append(volatility_reason)
    else:
        short_score += volatility_points
        if volatility_points:
            short_reasons.append(volatility_reason)

    long_score = min(long_score, 100)
    short_score = min(short_score, 100)

    if long_score >= 65 and long_score >= short_score + 10:
        direction = "LONG SETUP"
        score = long_score
        reasons = long_reasons
    elif short_score >= 65 and short_score >= long_score + 10:
        direction = "SHORT SETUP"
        score = short_score
        reasons = short_reasons
    else:
        direction = "WAIT"
        score = max(long_score, short_score)
        reasons = long_reasons if long_score >= short_score else short_reasons

    return {
        "direction": direction,
        "score": int(score),
        "long_score": int(long_score),
        "short_score": int(short_score),
        "reasons": reasons[:4],
    }

def get_signal(frame: pd.DataFrame) -> str:
    """Apply a small, transparent rule set; this never places an order."""
    if frame.empty:
        return "Wait"

    latest = frame.iloc[-1]
    if pd.isna(latest["rsi"]) or pd.isna(latest["ema20"]) or pd.isna(latest["ema50"]):
        return "Wait"

    price = latest["close"]
    rsi = latest["rsi"]

    if price > latest["ema20"] > latest["ema50"] and 50 <= rsi <= 70:
        return "Buy watch"
    if rsi >= 75 or (
        price < latest["ema20"] and price < latest["ema50"] and rsi < 50
    ):
        return "Sell watch"
    return "Wait"


def get_trend(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Unavailable"
    latest = frame.iloc[-1]
    if pd.isna(latest["ema20"]) or pd.isna(latest["ema50"]):
        return "Building"
    if latest["close"] > latest["ema20"] > latest["ema50"]:
        return "Uptrend"
    if latest["close"] < latest["ema20"] < latest["ema50"]:
        return "Downtrend"
    return "Mixed"


def format_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.2f}"
    if value >= 1:
        return f"${value:,.3f}"
    return f"${value:.6f}".rstrip("0").rstrip(".")


def signal_explanation(signal: str, frame: pd.DataFrame) -> str:
    latest = frame.iloc[-1]
    if signal == "Buy watch":
        return (
            "Price is above EMA20 and EMA50, and RSI is between 50 and 70. "
            "This is a trend condition to review, not a trade instruction."
        )
    if signal == "Sell watch" and latest["rsi"] >= 75:
        return (
            "RSI is at or above 75, a high-momentum level in this simple rule set. "
            "This is a condition to review, not a trade instruction."
        )
    if signal == "Sell watch":
        return (
            "Price is below EMA20 and EMA50 while RSI is below 50. "
            "This is a downtrend condition to review, not a trade instruction."
        )
    return "The selected indicator conditions do not currently line up. Waiting is also a valid signal."



def run_backtest(frame: pd.DataFrame, min_score: int = 65) -> pd.DataFrame:
    """Evaluate historical setups using only information available at each candle."""
    rows: list[dict[str, Any]] = []
    horizons = (5, 10, 20)
    max_horizon = max(horizons)

    if len(frame) < 220:
        return pd.DataFrame()

    # EMA200 needs history. Stop early enough that future candles exist for evaluation.
    for index in range(199, len(frame) - max_horizon):
        history = frame.iloc[: index + 1]
        setup = get_setup_score(history)

        if setup["direction"] not in ("LONG SETUP", "SHORT SETUP"):
            continue
        if setup["score"] < min_score:
            continue

        entry = float(frame.iloc[index]["close"])
        direction_multiplier = 1 if setup["direction"] == "LONG SETUP" else -1

        row: dict[str, Any] = {
            "Time": frame.iloc[index]["time"],
            "Direction": setup["direction"].replace(" SETUP", ""),
            "Score": setup["score"],
            "Entry": entry,
        }

        for horizon in horizons:
            future_close = float(frame.iloc[index + horizon]["close"])
            raw_return = ((future_close / entry) - 1) * 100
            directional_return = raw_return * direction_multiplier
            row[f"{horizon} candle return %"] = directional_return
            row[f"{horizon} candle win"] = directional_return > 0

        rows.append(row)

    return pd.DataFrame(rows)


def backtest_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Create compact performance statistics for 5/10/20-candle horizons."""
    if results.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for horizon in (5, 10, 20):
        return_column = f"{horizon} candle return %"
        win_column = f"{horizon} candle win"
        rows.append(
            {
                "Horizon": f"{horizon} candles",
                "Setups": len(results),
                "Win rate": float(results[win_column].mean() * 100),
                "Average return": float(results[return_column].mean()),
                "Median return": float(results[return_column].median()),
            }
        )
    return pd.DataFrame(rows)


def compare_score_thresholds(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare score thresholds and LONG/SHORT results separately."""
    rows: list[dict[str, Any]] = []

    for threshold in (65, 70, 75, 80):
        results = run_backtest(frame, threshold)
        if results.empty:
            continue

        for direction in ("ALL", "LONG", "SHORT"):
            subset = results if direction == "ALL" else results[results["Direction"] == direction]
            if subset.empty:
                continue

            for horizon in (5, 10, 20):
                return_col = f"{horizon} candle return %"
                win_col = f"{horizon} candle win"
                rows.append(
                    {
                        "Min score": threshold,
                        "Direction": direction,
                        "Horizon": f"{horizon} candles",
                        "Setups": len(subset),
                        "Win rate": float(subset[win_col].mean() * 100),
                        "Average return": float(subset[return_col].mean()),
                        "Median return": float(subset[return_col].median()),
                    }
                )

    return pd.DataFrame(rows)


def beginner_explanations(latest: pd.Series) -> list[tuple[str, str, str]]:
    """Explain the main indicators in simple Finnish."""
    price = float(latest["close"])
    ema20 = float(latest["ema20"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    rsi = float(latest["rsi"])
    macd = float(latest["macd"])
    macd_signal = float(latest["macd_signal"])
    atr_pct = float(latest["atr_percent"])
    volume_ratio = float(latest["volume_ratio"])

    if price > ema20 > ema50 > ema200:
        ema_text = "🟢 Selkeä nousutrendi — hinta ja EMA-linjat ovat nousujärjestyksessä."
    elif price < ema20 < ema50 < ema200:
        ema_text = "🔴 Selkeä laskutrendi — hinta ja EMA-linjat ovat laskujärjestyksessä."
    else:
        ema_text = "🟡 Sekava trendi — EMA-linjat eivät tällä hetkellä osoita kaikki samaan suuntaan."

    if rsi >= 70:
        rsi_text = f"🟠 RSI {rsi:.1f} — nousu on ollut voimakasta ja hinta voi olla jo venynyt."
    elif rsi >= 50:
        rsi_text = f"🟢 RSI {rsi:.1f} — nousumomentum on tällä hetkellä laskumomentumia vahvempi."
    elif rsi >= 30:
        rsi_text = f"🔴 RSI {rsi:.1f} — laskumomentum on tällä hetkellä vahvempi."
    else:
        rsi_text = f"🟠 RSI {rsi:.1f} — lasku on ollut voimakasta ja hinta voi olla jo venynyt."

    if macd > macd_signal:
        macd_text = "🟢 MACD on signal-linjan yläpuolella — momentum tukee tällä hetkellä enemmän nousua."
    elif macd < macd_signal:
        macd_text = "🔴 MACD on signal-linjan alapuolella — momentum tukee tällä hetkellä enemmän laskua."
    else:
        macd_text = "🟡 MACD ja signal-linja ovat samassa kohdassa — selvää momentum-suuntaa ei ole."

    if atr_pct < 0.35:
        atr_text = f"🔵 ATR {atr_pct:.2f}% — hinta liikkuu tällä aikavälillä melko rauhallisesti."
    elif atr_pct <= 2.5:
        atr_text = f"🟢 ATR {atr_pct:.2f}% — markkinassa on kohtalaisesti liikettä."
    else:
        atr_text = f"🟠 ATR {atr_pct:.2f}% — markkina heiluu voimakkaasti, joten myös riski on suurempi."

    if volume_ratio >= 1.5:
        volume_text = f"🟢 Volume {volume_ratio:.2f}× — kaupankäyntiä on selvästi tavallista enemmän."
    elif volume_ratio >= 1.0:
        volume_text = f"🟢 Volume {volume_ratio:.2f}× — kaupankäyntiä on hieman keskimääräistä enemmän."
    elif volume_ratio >= 0.7:
        volume_text = f"🟡 Volume {volume_ratio:.2f}× — kaupankäyntiä on hieman tavallista vähemmän."
    else:
        volume_text = f"⚪ Volume {volume_ratio:.2f}× — kaupankäynti on tällä hetkellä hiljaista."

    return [
        ("EMA20 / EMA50 / EMA200", ema_text,
         "EMA:t näyttävät trendiä eri nopeuksilla: EMA20 reagoi nopeimmin ja EMA200 hitaimmin."),
        ("RSI (14)", rsi_text,
         "RSI mittaa viimeaikaisten nousujen ja laskujen voimaa asteikolla 0–100. Se ei ole nousun todennäköisyys."),
        ("MACD", macd_text,
         "MACD auttaa arvioimaan momentumin suuntaa. Yksinään se ei tarkoita, että pitäisi ostaa tai myydä."),
        ("ATR (14)", atr_text,
         "ATR kertoo hinnan heilunnan suuruudesta, ei liikkeen suunnasta."),
        ("Volume ratio", volume_text,
         "1.00× tarkoittaa 20 kynttilän keskimääräistä volyymia. Suuri volume kertoo aktiivisuudesta, ei yksin suunnasta."),
    ]

def build_price_chart(frame: pd.DataFrame, symbol: str) -> go.Figure:
    """Create a candlestick price chart with EMA overlays and an RSI panel."""
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.58, 0.21, 0.21],
        subplot_titles=(
            "Price with EMA20, EMA50 and EMA200",
            "RSI (14)",
            "MACD (12, 26, 9)",
        ),
    )

    figure.add_trace(
        go.Candlestick(
            x=frame["time"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name=symbol,
            increasing_line_color="#4de2b4",
            decreasing_line_color="#ff7187",
            increasing_fillcolor="rgba(77, 226, 180, .62)",
            decreasing_fillcolor="rgba(255, 113, 135, .58)",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["ema20"],
            name="EMA20",
            line={"color": "#53d8f5", "width": 1.6},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["ema50"],
            name="EMA50",
            line={"color": "#b697ff", "width": 1.6},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["ema200"],
            name="EMA200",
            line={"color": "#f2b84b", "width": 1.6},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["rsi"],
            name="RSI 14",
            line={"color": "#53d8f5", "width": 1.7},
            fill="tozeroy",
            fillcolor="rgba(83, 216, 245, .08)",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["macd"],
            name="MACD",
            line={"color": "#53d8f5", "width": 1.5},
        ),
        row=3,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["time"],
            y=frame["macd_signal"],
            name="MACD signal",
            line={"color": "#f2b84b", "width": 1.4},
        ),
        row=3,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=frame["time"],
            y=frame["macd_hist"],
            name="MACD histogram",
            marker_color="#6f8799",
            opacity=0.55,
        ),
        row=3,
        col=1,
    )
    figure.add_hline(
        y=0, line_dash="dot", line_color="rgba(169, 192, 211, .35)", row=3, col=1
    )

    figure.add_hline(
        y=70, line_dash="dot", line_color="rgba(255, 135, 149, .55)", row=2, col=1
    )
    figure.add_hline(
        y=30, line_dash="dot", line_color="rgba(77, 226, 180, .55)", row=2, col=1
    )
    figure.update_layout(
        height=760,
        margin={"l": 10, "r": 10, "t": 48, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6, 16, 27, .45)",
        font={"color": "#a9bfd0", "family": "Arial, sans-serif", "size": 11},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
    )
    figure.update_xaxes(showgrid=False, color="#8da6b9")
    figure.update_yaxes(
        gridcolor="rgba(124, 158, 184, .12)",
        zerolinecolor="rgba(124, 158, 184, .12)",
        color="#8da6b9",
    )
    figure.update_yaxes(range=[0, 100], row=2, col=1)
    for annotation in figure.layout.annotations:
        annotation.font = {"color": "#90aabe", "size": 11}
    return figure


DEXSCREENER_API_HOST = "https://api.dexscreener.com"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"


@st.cache_data(ttl=45, show_spinner=False)
def load_solana_early_radar() -> pd.DataFrame:
    """Discover recent Solana token profiles and enrich them with DEX market data."""
    try:
        response = requests.get(
            f"{DEXSCREENER_API_HOST}/token-profiles/latest/v1",
            headers={"User-Agent": "JariTradinAi/1.0"},
            timeout=12,
        )
        response.raise_for_status()
        profiles = response.json()
    except (requests.RequestException, ValueError):
        return pd.DataFrame()

    solana = [p for p in profiles if str(p.get("chainId", "")).lower() == "solana"][:24]
    rows = []
    now_ms = datetime.now().timestamp() * 1000

    def enrich(profile):
        address = profile.get("tokenAddress", "")
        if not address:
            return None
        try:
            r = requests.get(
                f"{DEXSCREENER_API_HOST}/token-pairs/v1/solana/{address}",
                headers={"User-Agent": "JariTradinAi/1.0"},
                timeout=10,
            )
            r.raise_for_status()
            pairs = r.json()
            if not isinstance(pairs, list) or not pairs:
                return None
            pair = max(pairs, key=lambda x: float((x.get("liquidity") or {}).get("usd") or 0))
            base = pair.get("baseToken") or {}
            created = pair.get("pairCreatedAt")
            age_hours = ((now_ms - float(created)) / 3_600_000) if created else None
            tx_h1 = (pair.get("txns") or {}).get("h1") or {}
            vol = pair.get("volume") or {}
            liquidity = pair.get("liquidity") or {}
            market_cap = pair.get("marketCap")
            fdv = pair.get("fdv")
            links = profile.get("links") or []
            social_items = []
            social_urls = []
            for link in links:
                kind = str(link.get("type") or link.get("label") or "link").strip()
                url = str(link.get("url") or "").strip()
                if url:
                    social_items.append(kind)
                    social_urls.append(url)
            socials = ", ".join(social_items) or "—"
            info = pair.get("info") or {}
            pair_socials = info.get("socials") or []
            for item in pair_socials:
                platform = str(item.get("platform") or "").strip()
                handle = str(item.get("handle") or "").strip()
                if platform and platform.lower() not in [x.lower() for x in social_items]:
                    social_items.append(platform)
                if platform and handle:
                    social_urls.append(f"{platform}: {handle}")
            boosts_active = int(((pair.get("boosts") or {}).get("active") or 0))
            return {
                "Token": base.get("name") or "Unknown",
                "Ticker": base.get("symbol") or "—",
                "Contract address": address,
                "Age (h)": age_hours,
                "Market cap": market_cap,
                "FDV": fdv,
                "Liquidity": liquidity.get("usd"),
                "Volume 1h": vol.get("h1"),
                "Buys 1h": tx_h1.get("buys"),
                "Sells 1h": tx_h1.get("sells"),
                "Social links": ", ".join(social_items) or socials,
                "Social refs": " | ".join(social_urls) or "—",
                "Profile description": str(profile.get("description") or ""),
                "DEX boosts": boosts_active,
                "DEX Screener": pair.get("url") or profile.get("url"),
            }
        except (requests.RequestException, ValueError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(enrich, profile) for profile in solana]
        for future in as_completed(futures):
            item = future.result()
            if item:
                rows.append(item)

    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    return result.sort_values(["Age (h)", "Liquidity"], ascending=[True, False], na_position="last")



def _rpc_call(method: str, params: list):
    try:
        response = requests.post(
            SOLANA_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            headers={"Content-Type": "application/json", "User-Agent": "JariTradinAi/2.0"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("result")
    except (requests.RequestException, ValueError, TypeError):
        return None


@st.cache_data(ttl=120, show_spinner=False)
def solana_safety_snapshot(mint: str) -> dict:
    """Read basic SPL mint authorities and holder concentration from Solana public RPC."""
    out = {
        "Mint authority": None,
        "Freeze authority": None,
        "Top 20 %": None,
        "On-chain checked": False,
    }
    account = _rpc_call("getAccountInfo", [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}])
    try:
        info = (((account or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})
        if info:
            out["Mint authority"] = info.get("mintAuthority")
            out["Freeze authority"] = info.get("freezeAuthority")
            out["On-chain checked"] = True
    except (AttributeError, TypeError):
        pass

    supply_result = _rpc_call("getTokenSupply", [mint, {"commitment": "confirmed"}])
    largest_result = _rpc_call("getTokenLargestAccounts", [mint, {"commitment": "confirmed"}])
    try:
        supply_raw = float(((supply_result or {}).get("value") or {}).get("amount") or 0)
        accounts = (largest_result or {}).get("value") or []
        largest_raw = sum(float(x.get("amount") or 0) for x in accounts[:20])
        if supply_raw > 0:
            out["Top 20 %"] = (largest_raw / supply_raw) * 100
    except (TypeError, ValueError, AttributeError):
        pass
    return out


def safety_assessment(row: pd.Series, chain: dict) -> tuple[int, str, list[str]]:
    """Transparent risk heuristic. Lower score means fewer observed warning flags, not 'safe'."""
    risk = 0
    reasons = []
    liquidity = float(row.get("Liquidity") or 0)
    market_cap = float(row.get("Market cap") or row.get("FDV") or 0)
    volume = float(row.get("Volume 1h") or 0)
    buys = float(row.get("Buys 1h") or 0)
    sells = float(row.get("Sells 1h") or 0)
    age = float(row.get("Age (h)") or 0)

    if liquidity < 10_000:
        risk += 30; reasons.append("very low liquidity")
    elif liquidity < 25_000:
        risk += 18; reasons.append("low liquidity")
    elif liquidity >= 100_000:
        reasons.append("stronger liquidity")

    if market_cap > 0:
        liq_ratio = liquidity / market_cap
        if liq_ratio < 0.03:
            risk += 22; reasons.append("liquidity is tiny vs valuation")
        elif liq_ratio < 0.08:
            risk += 10; reasons.append("thin liquidity vs valuation")
        elif liq_ratio >= 0.20:
            reasons.append("healthy liquidity/valuation ratio")

    if age < 1:
        risk += 8; reasons.append("less than 1 hour old")
    if volume < 2_000:
        risk += 8; reasons.append("little 1h trading activity")
    if buys + sells >= 10 and sells > buys * 2.5:
        risk += 10; reasons.append("sells heavily exceed buys")

    if chain.get("On-chain checked"):
        if chain.get("Mint authority"):
            risk += 18; reasons.append("mint authority still active")
        else:
            reasons.append("mint authority revoked")
        if chain.get("Freeze authority"):
            risk += 18; reasons.append("freeze authority still active")
        else:
            reasons.append("freeze authority revoked")
    else:
        reasons.append("mint authorities not verified")

    top20 = chain.get("Top 20 %")
    if top20 is not None:
        if top20 >= 80:
            risk += 22; reasons.append(f"top 20 token accounts hold {top20:.0f}%")
        elif top20 >= 60:
            risk += 12; reasons.append(f"top 20 token accounts hold {top20:.0f}%")
        else:
            reasons.append(f"top 20 token accounts hold {top20:.0f}%")

    risk = min(100, int(risk))
    label = "🔴 HIGH" if risk >= 55 else "🟡 MEDIUM" if risk >= 25 else "🟢 LOWER"
    return risk, label, reasons


CELEBRITY_CATALYST_WORDS = {
    "trump": "Trump",
    "elon": "Elon Musk",
    "musk": "Elon Musk",
    "mrbeast": "MrBeast",
    "kanye": "Kanye West",
    "ye ": "Kanye West",
    "ronaldo": "Cristiano Ronaldo",
    "messi": "Lionel Messi",
    "tate": "Andrew Tate",
}


def social_potential_assessment(row: pd.Series, risk_points: int) -> tuple[int, str, str, list[str]]:
    """Early-interest heuristic. This is not a return probability or verified celebrity endorsement."""
    score = 0
    reasons = []
    liquidity = float(row.get("Liquidity") or 0)
    market_cap = float(row.get("Market cap") or row.get("FDV") or 0)
    volume = float(row.get("Volume 1h") or 0)
    buys = float(row.get("Buys 1h") or 0)
    sells = float(row.get("Sells 1h") or 0)
    age = float(row.get("Age (h)") or 999)
    boosts = int(row.get("DEX boosts") or 0)
    social_text = str(row.get("Social links") or "").lower()
    searchable = " ".join([
        str(row.get("Token") or ""), str(row.get("Ticker") or ""),
        str(row.get("Profile description") or ""), str(row.get("Social refs") or "")
    ]).lower()

    # Market activity: 55 points max.
    if liquidity >= 100_000: score += 15; reasons.append("strong liquidity")
    elif liquidity >= 50_000: score += 11; reasons.append("solid liquidity")
    elif liquidity >= 25_000: score += 7
    if volume >= 250_000: score += 15; reasons.append("very high 1h volume")
    elif volume >= 100_000: score += 12; reasons.append("high 1h volume")
    elif volume >= 25_000: score += 7
    total_tx = buys + sells
    if total_tx >= 100 and buys > sells * 1.35: score += 15; reasons.append("buyers clearly lead")
    elif total_tx >= 40 and buys > sells: score += 9; reasons.append("buyers lead")
    elif total_tx >= 20: score += 4
    if age <= 6: score += 10; reasons.append("very early pair")
    elif age <= 24: score += 6

    # Public-profile attention proxies: 25 points max. DEX boosts are paid attention, not organic social proof.
    social_count = sum(k in social_text for k in ("twitter", "x", "telegram", "discord", "youtube", "tiktok"))
    if social_count >= 3: score += 10; reasons.append("multiple social channels")
    elif social_count >= 1: score += 5; reasons.append("social channel present")
    if boosts >= 50: score += 15; reasons.append("heavy DEX promotion")
    elif boosts >= 10: score += 10; reasons.append("DEX promotion active")
    elif boosts > 0: score += 5; reasons.append("some DEX promotion")

    # Valuation headroom proxy: 10 points max. This does not predict a target market cap.
    if 0 < market_cap <= 2_000_000: score += 10; reasons.append("small valuation / more theoretical headroom")
    elif market_cap <= 10_000_000 and market_cap > 0: score += 6
    elif market_cap <= 50_000_000 and market_cap > 0: score += 3

    # Keep safety separate, but cap hype when observed risk is severe.
    if risk_points >= 55:
        score = min(score, 49)
        reasons.append("potential capped because safety risk is HIGH")
    elif risk_points >= 25:
        score = max(0, score - 8)
        reasons.append("medium safety risk penalty")

    claims = sorted({label for word, label in CELEBRITY_CATALYST_WORDS.items() if word in searchable})
    catalyst = ", ".join(claims) if claims else "—"
    if claims:
        reasons.append("celebrity name detected — NOT verified as endorsement")

    score = max(0, min(100, int(score)))
    label = "🔥 HIGH INTEREST" if score >= 70 else "👀 WATCH" if score >= 50 else "⚪ EARLY/WEAK"
    return score, label, catalyst, reasons


def market_cap_scenarios(market_cap) -> str:
    try:
        mc = float(market_cap or 0)
    except (TypeError, ValueError):
        return "—"
    if mc <= 0:
        return "—"
    targets = []
    for multiple in (2, 3, 5, 10):
        target = mc * multiple
        if target < 1_000_000:
            text = f"${target/1_000:.0f}k"
        elif target < 1_000_000_000:
            text = f"${target/1_000_000:.1f}M"
        else:
            text = f"${target/1_000_000_000:.2f}B"
        targets.append(f"{multiple}×→{text}")
    return " · ".join(targets)


def send_telegram_message(message: str) -> tuple[bool, str]:
    """Send a message using credentials stored in Streamlit Secrets."""
    try:
        bot_token = str(st.secrets["TELEGRAM_BOT_TOKEN"]).strip()
        chat_id = str(st.secrets["TELEGRAM_CHAT_ID"]).strip()
    except Exception:
        return False, "Telegram Secrets are missing. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Streamlit Secrets."

    if not bot_token or not chat_id:
        return False, "Telegram bot token or chat ID is empty."

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=12,
        )
        payload = response.json()
        if response.ok and payload.get("ok"):
            return True, "Telegram message sent."
        description = payload.get("description", f"HTTP {response.status_code}")
        return False, f"Telegram rejected the message: {description}"
    except Exception as exc:
        return False, f"Telegram connection failed: {exc}"


def telegram_test_panel() -> None:
    st.markdown("### 📲 Telegram alerts")
    st.caption("Test the private JARVIS → Telegram connection before automatic radar alerts are enabled.")
    if st.button("📲 Send Telegram test", type="primary", use_container_width=False):
        ok, detail = send_telegram_message(
            "🤖 JARVIS ONLINE\n\nTelegram-yhteys toimii.\n🔥 Early Radar connected.\n\nAutomaattisia trading-alertteja ei ole vielä kytketty päälle."
        )
        if ok:
            st.success("Testiviesti lähetettiin Telegramiin. Tarkista puhelimesi. ✅")
        else:
            st.error(detail)


def show_early_radar() -> None:
    st.markdown('<div class="eyebrow"><span class="live-dot"></span>JARVIS EARLY RADAR · V4</div>', unsafe_allow_html=True)
    st.subheader("🔥 New Solana token radar")
    st.caption(
        "Discovery + safety + early-interest layer. Potential Score is a transparent attention/momentum heuristic — NOT a probability of profit. Identify tokens by exact contract address."
    )
    telegram_test_panel()
    st.divider()
    radar = load_solana_early_radar()
    if radar.empty:
        st.warning("Early Radar did not receive token data right now. Try refreshing in a moment.")
        return

    max_age = st.slider("Maximum pair age", 1, 168, 48, help="48 hours = pairs created during roughly the last two days.")
    min_liquidity = st.select_slider(
        "Minimum liquidity",
        options=[0, 5000, 10000, 25000, 50000, 100000, 250000],
        value=10000,
        format_func=lambda x: f"${x:,.0f}",
    )
    view = radar[(radar["Age (h)"].fillna(10**9) <= max_age) & (radar["Liquidity"].fillna(0) >= min_liquidity)].copy()
    if view.empty:
        st.info("No tokens currently match these filters. Try widening them.")
        return

    st.markdown("### 🛡️ Safety / Rug screen")
    st.caption("Checking public Solana on-chain data. This is a warning-flag screen, not a guarantee that a token is safe.")
    enriched = []
    with st.spinner("JARVIS is checking mint authorities and holder concentration…"):
        for _, row in view.head(12).iterrows():
            chain = solana_safety_snapshot(str(row["Contract address"]))
            score, label, reasons = safety_assessment(row, chain)
            item = row.to_dict()
            item["Risk"] = label
            item["Risk points"] = score
            item["Mint authority"] = "ACTIVE ⚠️" if chain.get("Mint authority") else ("Revoked ✓" if chain.get("On-chain checked") else "Unknown")
            item["Freeze authority"] = "ACTIVE ⚠️" if chain.get("Freeze authority") else ("Revoked ✓" if chain.get("On-chain checked") else "Unknown")
            item["Top 20 holders"] = chain.get("Top 20 %")
            potential, potential_label, celebrity_claim, potential_reasons = social_potential_assessment(row, score)
            item["Potential"] = potential
            item["Interest"] = potential_label
            item["Celebrity/catalyst"] = celebrity_claim
            item["Potential why"] = " · ".join(potential_reasons)
            item["MC scenarios"] = market_cap_scenarios(row.get("Market cap") or row.get("FDV"))
            item["Why"] = " · ".join(reasons)
            enriched.append(item)

    result = pd.DataFrame(enriched).sort_values(["Potential", "Risk points", "Liquidity"], ascending=[False, True, False])
    st.markdown("### 🔥 Social / Momentum radar")
    st.caption("Ranks early attention using DEX activity, social-link presence, promotion, age and valuation. Celebrity-name hits are UNVERIFIED until an official post and the exact contract address are matched.")
    st.dataframe(
        result[["Interest", "Potential", "Risk", "Token", "Ticker", "Contract address", "Celebrity/catalyst", "Age (h)", "Market cap", "MC scenarios", "Liquidity", "Volume 1h", "Buys 1h", "Sells 1h", "DEX boosts", "Social links", "Potential why", "Mint authority", "Freeze authority", "Top 20 holders", "Why", "DEX Screener"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Potential": st.column_config.NumberColumn("Potential", format="%d/100"),
            "Age (h)": st.column_config.NumberColumn("Age", format="%.1f h"),
            "Market cap": st.column_config.NumberColumn("Market cap", format="$%.0f"),
            "Liquidity": st.column_config.NumberColumn("Liquidity", format="$%.0f"),
            "Volume 1h": st.column_config.NumberColumn("Volume 1h", format="$%.0f"),
            "Top 20 holders": st.column_config.NumberColumn("Top 20", format="%.1f%%"),
            "DEX Screener": st.column_config.LinkColumn("Chart"),
        },
    )

    st.warning(
        "LOWER risk means only that JARVIS observed fewer of these specific warning flags. It does NOT mean safe, genuine, non-rug, or a good investment. "
        "Top-20 concentration is token-account concentration and can include pools/exchanges, so it is a screening signal rather than proof of insider ownership."
    )
    st.info(
        "V3 social score is a first-pass proxy, not full social listening yet. A celebrity name only creates an UNVERIFIED catalyst flag. "
        "The next upgrade is verified X/Reddit/Telegram trend velocity + Telegram alerts; those sources need their own API/bot credentials."
    )
    st.warning(
        "MC scenarios are arithmetic what-if levels, not price targets or sell recommendations. A 5× scenario means the current market cap multiplied by five; JARVIS is not claiming it will reach that level."
    )


st.markdown(
    """
    <div class="jari-header">
        <div class="jari-mark">◈</div>
        <div>
            <div class="jari-title">JARI TRADIN AI</div>
            <div class="jari-subtitle">Crypto market intelligence · Kraken public data</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "A read-only learning dashboard. It does not connect to a wallet or place trades."
)

with st.sidebar:
    st.markdown('<div class="eyebrow">Control room</div>', unsafe_allow_html=True)
    st.title("Dashboard settings")
    selected_symbol = st.selectbox(
        "Coin to chart",
        WATCH_SYMBOLS,
        index=WATCH_SYMBOLS.index("BTCUSDT"),
        format_func=lambda symbol: f"{symbol.removesuffix('USDT')} / USDT",
    )
    selected_timeframe_label = st.selectbox(
        "Candle size",
        list(TIMEFRAMES.keys()),
        index=1,
        help="A candle groups prices over this amount of time.",
    )
    candle_count = st.select_slider(
        "Chart history",
        options=[250, 300, 500],
        value=300,
        help="More candles show a longer history and take slightly longer to load.",
    )
    refresh_seconds = st.selectbox(
        "Auto-refresh",
        [15, 30, 60],
        index=1,
        format_func=lambda seconds: f"Every {seconds} seconds",
    )
    st.divider()
    st.markdown('<div class="eyebrow">Indicator guide</div>', unsafe_allow_html=True)
    st.markdown(
        """
        - **RSI (14):** momentum from 0 to 100.
        - **EMA20 / EMA50 / EMA200:** average price lines that react at different speeds.\n        - **MACD (12, 26, 9):** momentum/trend indicator comparing two EMAs.\n        - **ATR (14):** volatility measure showing the market’s typical price range.\n        - **Volume ratio:** current candle volume divided by the 20-candle average.\n        - **JARVIS Setup Score:** transparent 0–100 rule score, not a probability of profit.
        - **Watch signals:** simple rules to help review conditions, not advice.
        """
    )
    st.caption("All market data comes from Kraken's public API. No API key is used.")

selected_interval = TIMEFRAMES[selected_timeframe_label]

st.sidebar.divider()
app_page = st.sidebar.radio("JARVIS module", ["Market Dashboard", "🔥 Early Radar"], index=0)


@st.fragment(run_every=f"{refresh_seconds}s")
def show_market_dashboard() -> None:
    with st.spinner("Loading public Kraken market data…"):
        tickers, raw_candles, error = load_market_snapshot(
            selected_interval, WATCH_SYMBOLS, candle_count
        )

    if error:
        st.error(error)
        st.info("Check your internet connection, then wait for the next refresh.")
        return

    selected_raw = raw_candles.get(selected_symbol, [])
    selected_frame = candles_to_frame(selected_raw)
    if selected_frame.empty:
        st.error(
            f"Kraken did not return candle history for {selected_symbol}. "
            "Try another coin or candle size."
        )
        return

    latest = selected_frame.iloc[-1]
    ticker = tickers.get(selected_symbol, {})
    current_price = float(ticker.get("c", [latest["close"]])[0])
    open_24h = float(ticker.get("o", current_price))
    change_24h = ((current_price / open_24h) - 1) * 100 if open_24h else 0.0
    rsi = float(latest["rsi"]) if not pd.isna(latest["rsi"]) else None
    signal = get_signal(selected_frame)
    setup = get_setup_score(selected_frame)
    trend = get_trend(selected_frame)
    signal_class = {
        "Buy watch": "signal-buy",
        "Sell watch": "signal-sell",
        "Wait": "signal-wait",
    }[signal]
    signal_color = {
        "Buy watch": "#6cf2bf",
        "Sell watch": "#ff8795",
        "Wait": "#a9c0d3",
    }[signal]

    st.markdown(
        '<div class="eyebrow"><span class="live-dot"></span>Live market overview</div>',
        unsafe_allow_html=True,
    )
    metric_columns = st.columns(4)
    metric_columns[0].metric(
        f"{selected_symbol.removesuffix('USDT')} / USDT price",
        format_price(current_price),
    )
    metric_columns[1].metric("24h change", f"{change_24h:+.2f}%")
    metric_columns[2].metric("RSI (14)", f"{rsi:.1f}" if rsi is not None else "—")
    metric_columns[3].metric("EMA trend", trend)

    setup_direction = setup["direction"]
    setup_score = setup["score"]
    setup_reasons = " · ".join(setup["reasons"]) if setup["reasons"] else "No strong alignment yet."
    setup_class = (
        "signal-buy" if setup_direction == "LONG SETUP"
        else "signal-sell" if setup_direction == "SHORT SETUP"
        else "signal-wait"
    )
    st.markdown(
        f"""
        <div class="signal-box">
            <div class="eyebrow">JARVIS Setup Score · {selected_symbol.removesuffix('USDT')} / USDT</div>
            <div style="margin-top: 11px;">
                <span class="signal-label {setup_class}">{setup_direction} · {setup_score}/100</span>
            </div>
            <div class="signal-copy">{setup_reasons}</div>
            <div class="soft-note" style="margin-top:8px;">
                Long {setup["long_score"]}/100 · Short {setup["short_score"]}/100 · Rule score, not profit probability.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="signal-box">
            <div class="eyebrow">Rule-based signal · {selected_symbol.removesuffix('USDT')} / USDT</div>
            <div style="margin-top: 11px;">
                <span class="signal-label {signal_class}">{signal.upper()}</span>
            </div>
            <div class="signal-copy">{signal_explanation(signal, selected_frame)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_col, levels_col = st.columns([2.2, 1])
    with chart_col:
        st.subheader(f"{selected_symbol.removesuffix('USDT')} / USDT price chart")
        st.caption(
            f"{selected_timeframe_label} candles · EMA20/50/200 · RSI · MACD below"
        )
        st.plotly_chart(
            build_price_chart(selected_frame, selected_symbol.removesuffix("USDT")),
            width="stretch",
            config={"displayModeBar": False},
        )
    with levels_col:
        st.subheader("Mitä markkina kertoo?")
        st.caption("Paina indikaattoria avataksesi selityksen.")
        for indicator_name, interpretation, explanation in beginner_explanations(latest):
            with st.expander(indicator_name, expanded=False):
                st.write(interpretation)
                st.caption(explanation)

        st.subheader("Indicator readings")
        for label, column, color in (
            ("Current candle close", "close", "#eaf7ff"),
            ("EMA20", "ema20", "#53d8f5"),
            ("EMA50", "ema50", "#b697ff"),
            ("EMA200", "ema200", "#f2b84b"),
            ("MACD", "macd", "#53d8f5"),
            ("MACD signal", "macd_signal", "#f2b84b"),
            ("ATR (14)", "atr", "#eaf7ff"),
            ("Volume ratio", "volume_ratio", "#6cf2bf"),
        ):
            value = latest[column]
            if pd.isna(value):
                display_value = "Building…"
            elif column == "volume_ratio":
                display_value = f"{float(value):.2f}×"
            else:
                display_value = format_price(float(value))
            st.markdown(
                f"""
                <div style="padding: 13px 14px; margin: 0 0 10px;
                            background: rgba(13, 29, 44, .85);
                            border: 1px solid rgba(91, 185, 217, .15);
                            border-radius: 10px;">
                    <div style="color:#8da6b9;font-size:.79rem;">{label}</div>
                    <div style="color:{color};font-size:1.12rem;font-weight:650;margin-top:5px;">
                        {display_value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        atr_percent = latest["atr_percent"]
        if not pd.isna(atr_percent):
            st.caption(
                f"ATR is {float(atr_percent):.2f}% of the current price — "
                "a normalized view of current volatility."
            )

        volume_ratio = latest["volume_ratio"]
        if not pd.isna(volume_ratio):
            if volume_ratio >= 1.5:
                volume_text = "High activity"
            elif volume_ratio >= 1.0:
                volume_text = "Above average"
            elif volume_ratio >= 0.7:
                volume_text = "Below average"
            else:
                volume_text = "Low activity"
            st.caption(
                f"Volume: {float(volume_ratio):.2f}× the 20-candle average · {volume_text}."
            )

        st.markdown(
            f"""
            <div style="padding: 13px 14px; margin-top: 14px;
                        border-left: 2px solid {signal_color};
                        background: rgba(13, 29, 44, .7);">
                <div style="color:#8da6b9;font-size:.79rem;">Signal rule summary</div>
                <div style="color:#c4d6e4;font-size:.88rem;line-height:1.55;margin-top:6px;">
                    Buy watch: price above both EMAs and RSI 50–70.<br>
                    Sell watch: RSI at least 75, or price below both EMAs with RSI below 50.<br>
                    Otherwise: Wait.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown('<div class="eyebrow">Multi-coin scanner</div>', unsafe_allow_html=True)
    st.subheader("Watchlist analysis")
    st.caption(
        f"RSI and EMA signals use {selected_timeframe_label.lower()} candles for each coin."
    )

    watch_rows: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for symbol in WATCH_SYMBOLS:
        coin_ticker = tickers.get(symbol, {})
        coin_frame = (
            selected_frame if symbol == selected_symbol else candles_to_frame(raw_candles.get(symbol, []))
        )
        if coin_frame.empty or not coin_ticker:
            unavailable.append(symbol.removesuffix("USDT"))
            continue

        coin_latest = coin_frame.iloc[-1]
        coin_signal = get_signal(coin_frame)
        coin_setup = get_setup_score(coin_frame)
        close = float(coin_ticker.get("c", [coin_latest["close"]])[0])
        rsi_value = coin_latest["rsi"]
        watch_rows.append(
            {
                "Coin": symbol.removesuffix("USDT"),
                "Price (USDT)": close,
                "24h change": (
                    ((close / float(coin_ticker.get("o", close))) - 1) * 100
                    if float(coin_ticker.get("o", close))
                    else 0.0
                ),
                "RSI (14)": float(rsi_value) if not pd.isna(rsi_value) else None,
                "EMA trend": get_trend(coin_frame),
                "Setup": coin_setup["direction"],
                "Score": coin_setup["score"],
                "Signal": coin_signal,
            }
        )

    if watch_rows:
        watchlist = pd.DataFrame(watch_rows)
        st.dataframe(
            watchlist,
            hide_index=True,
            width="stretch",
            column_config={
                "Coin": st.column_config.TextColumn("Coin"),
                "Price (USDT)": st.column_config.NumberColumn(
                    "Price (USDT)", format="$%.5f"
                ),
                "24h change": st.column_config.NumberColumn(
                    "24h change", format="%.2f%%"
                ),
                "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.1f"),
                "EMA trend": st.column_config.TextColumn("EMA trend"),
                "Setup": st.column_config.TextColumn("JARVIS setup"),
                "Score": st.column_config.NumberColumn("Score", format="%d/100"),
                "Signal": st.column_config.TextColumn("Signal"),
            },
        )
    if unavailable:
        st.caption(
            "Some coins could not be loaded right now: "
            + ", ".join(unavailable)
            + ". Other results are still shown."
        )

    checked_at = datetime.now().astimezone().strftime("%H:%M:%S %Z")
    st.markdown(
        f'<p class="soft-note">Last checked: {checked_at} · Auto-refreshes every '
        f'{refresh_seconds} seconds · Source: Kraken public market data</p>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<div class="eyebrow">STRATEGY LABORATORY</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="backtest-panel">
            <h3>Backtest v1</h3>
            <div class="backtest-copy">
                Historical test of the current JARVIS Setup Score for the selected coin and timeframe.
                Each signal uses only information that was available at that candle.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    threshold = st.select_slider(
        "Minimum setup score for backtest",
        options=[65, 70, 75, 80],
        value=65,
        key="backtest_threshold",
    )

    backtest_results = run_backtest(selected_frame, threshold)
    summary = backtest_summary(backtest_results)

    if summary.empty:
        st.info(
            "Not enough qualifying historical setups in the loaded chart history. "
            "Try a lower score threshold or a different coin/timeframe."
        )
    else:
        st.dataframe(
            summary,
            hide_index=True,
            width="stretch",
            column_config={
                "Horizon": st.column_config.TextColumn("Horizon"),
                "Setups": st.column_config.NumberColumn("Setups", format="%d"),
                "Win rate": st.column_config.NumberColumn("Win rate", format="%.1f%%"),
                "Average return": st.column_config.NumberColumn(
                    "Avg directional return", format="%+.2f%%"
                ),
                "Median return": st.column_config.NumberColumn(
                    "Median directional return", format="%+.2f%%"
                ),
            },
        )
        st.markdown(
            """
            <div class="backtest-note">
                <b>How to read this:</b> a win means price was in the setup direction at that future candle.
                Returns exclude fees, spread and slippage, so these are research results—not live-trading performance.
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Show historical setups"):
            display_results = backtest_results[
                [
                    "Time", "Direction", "Score", "Entry",
                    "5 candle return %", "10 candle return %", "20 candle return %",
                ]
            ].copy()
            st.dataframe(
                display_results,
                hide_index=True,
                width="stretch",
                column_config={
                    "Score": st.column_config.NumberColumn("Score", format="%d/100"),
                    "Entry": st.column_config.NumberColumn("Entry", format="$%.5f"),
                    "5 candle return %": st.column_config.NumberColumn("5 candles", format="%+.2f%%"),
                    "10 candle return %": st.column_config.NumberColumn("10 candles", format="%+.2f%%"),
                    "20 candle return %": st.column_config.NumberColumn("20 candles", format="%+.2f%%"),
                },
            )

        st.markdown("### Score threshold comparison")
        st.markdown(
            """
            <div class="backtest-copy">
                Compare 65 / 70 / 75 / 80 without changing the live JARVIS score.
                LONG and SHORT setups are shown separately so weak sides of the strategy are easier to spot.
            </div>
            """,
            unsafe_allow_html=True,
        )

        comparison = compare_score_thresholds(selected_frame)
        if comparison.empty:
            st.info("Not enough historical setups for threshold comparison.")
        else:
            comparison_horizon = st.selectbox(
                "Comparison horizon",
                options=["5 candles", "10 candles", "20 candles"],
                index=1,
                key="comparison_horizon",
            )
            comparison_view = comparison[
                comparison["Horizon"] == comparison_horizon
            ].copy()

            st.dataframe(
                comparison_view[
                    [
                        "Min score",
                        "Direction",
                        "Setups",
                        "Win rate",
                        "Average return",
                        "Median return",
                    ]
                ],
                hide_index=True,
                width="stretch",
                column_config={
                    "Min score": st.column_config.NumberColumn("Min score", format="%d/100"),
                    "Direction": st.column_config.TextColumn("Direction"),
                    "Setups": st.column_config.NumberColumn("Setups", format="%d"),
                    "Win rate": st.column_config.NumberColumn("Win rate", format="%.1f%%"),
                    "Average return": st.column_config.NumberColumn(
                        "Avg directional return", format="%+.2f%%"
                    ),
                    "Median return": st.column_config.NumberColumn(
                        "Median directional return", format="%+.2f%%"
                    ),
                },
            )
            st.markdown(
                """
                <div class="backtest-note">
                    Treat rows with very few setups cautiously. A high win rate from only a handful
                    of historical signals is not strong evidence that the rule is reliable.
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.warning(
        "Learning tool only. Signals are simple indicator rules, not financial advice. "
        "No trades are placed."
    )


if app_page == "🔥 Early Radar":
    show_early_radar()
else:
    show_market_dashboard()