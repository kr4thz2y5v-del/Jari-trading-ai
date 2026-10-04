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
    return frame


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
        - **EMA20 / EMA50 / EMA200:** average price lines that react at different speeds.\n        - **MACD (12, 26, 9):** momentum/trend indicator comparing two EMAs.\n        - **ATR (14):** volatility measure showing the market’s typical price range.
        - **Watch signals:** simple rules to help review conditions, not advice.
        """
    )
    st.caption("All market data comes from Kraken's public API. No API key is used.")

selected_interval = TIMEFRAMES[selected_timeframe_label]


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
        st.subheader("Indicator readings")
        for label, column, color in (
            ("Current candle close", "close", "#eaf7ff"),
            ("EMA20", "ema20", "#53d8f5"),
            ("EMA50", "ema50", "#b697ff"),
            ("EMA200", "ema200", "#f2b84b"),
            ("MACD", "macd", "#53d8f5"),
            ("MACD signal", "macd_signal", "#f2b84b"),
            ("ATR (14)", "atr", "#eaf7ff"),
        ):
            value = latest[column]
            display_value = format_price(float(value)) if not pd.isna(value) else "Building…"
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
    st.warning(
        "Learning tool only. Signals are simple indicator rules, not financial advice. "
        "No trades are placed."
    )


show_market_dashboard()
