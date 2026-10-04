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
