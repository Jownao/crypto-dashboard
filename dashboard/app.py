import os
import psycopg2
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Dashboard",
    page_icon="₿",
    layout="wide",
)

# ── Styling ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3, .metric-label  { font-family: 'Space Mono', monospace; }

.block-container { padding-top: 2rem; }

div[data-testid="metric-container"] {
    background: #0f0f0f;
    border: 1px solid #1e1e1e;
    border-radius: 12px;
    padding: 1rem 1.2rem;
}
div[data-testid="metric-container"] label {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    color: #555 !important;
    text-transform: uppercase;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Space Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
}

.pct-positive { color: #00d26a; font-weight: 600; }
.pct-negative { color: #ff4c4c; font-weight: 600; }
.pct-neutral  { color: #888;    font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Data source detection ──────────────────────────────────────────────────────
# Looks for sample_data.csv at the repo root (one level above dashboard/)
CSV_PATH = Path(__file__).parent.parent / "sample_data.csv"
USE_RDS  = bool(os.getenv("DB_HOST"))
MODE     = "RDS" if USE_RDS else "CSV (local preview)"

def get_connection():
    """Always creates a fresh connection — avoids stale/closed connection errors."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
    )

@st.cache_data(ttl=300)
def load_csv() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH, parse_dates=["collected_at"])

# ── Data loaders ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_latest_snapshot() -> pd.DataFrame:
    if USE_RDS:
        query = """
            SELECT DISTINCT ON (symbol)
                symbol, name, cmc_rank, price, volume_24h, market_cap,
                pct_1h, pct_24h, pct_7d, pct_30d, collected_at
            FROM crypto_quotes
            ORDER BY symbol, collected_at DESC;
        """
        conn = get_connection()
        df = pd.read_sql(query, conn)
        conn.close()
    else:
        df = load_csv()
        df = (df.sort_values("collected_at", ascending=False)
                .drop_duplicates("symbol"))
    return df.sort_values("cmc_rank")

@st.cache_data(ttl=60)
def load_price_history(symbol: str, hours: int = 24) -> pd.DataFrame:
    if USE_RDS:
        if hours == 0:
            query = """
                SELECT collected_at, price, volume_24h
                FROM crypto_quotes
                WHERE symbol = %s
                ORDER BY collected_at ASC;
            """
        else:
            query = f"""
                SELECT collected_at, price, volume_24h
                FROM crypto_quotes
                WHERE symbol = %s
                  AND collected_at >= NOW() - ({hours} * INTERVAL '1 hour')
                ORDER BY collected_at ASC;
            """
        conn = get_connection()
        df = pd.read_sql(query, conn, params=(symbol,))
        conn.close()
        return df
    else:
        df = load_csv()
        if hours > 0:
            cutoff = df["collected_at"].max() - timedelta(hours=hours)
            df = df[(df["symbol"] == symbol) & (df["collected_at"] >= cutoff)]
        else:
            df = df[df["symbol"] == symbol]
        return df[["collected_at", "price", "volume_24h"]].sort_values("collected_at")

# ── Helpers ─────────────────────────────────────────────────────────────────────
DEFAULT_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC"]

def fmt_price(v):
    if v is None: return "—"
    return f"${v:,.2f}" if v >= 1 else f"${v:.6f}"

def fmt_large(v):
    if v is None: return "—"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def pct_badge(v):
    if v is None:
        return '<span class="pct-neutral">—</span>'
    arrow = "▲" if v > 0 else "▼" if v < 0 else "●"
    cls   = "pct-positive" if v > 0 else "pct-negative" if v < 0 else "pct-neutral"
    return f'<span class="{cls}">{arrow} {abs(v):.2f}%</span>'

# ── App ──────────────────────────────────────────────────────────────────────────
st.title("₿  Crypto Dashboard")
st.caption(
    f"Top 100 · refreshes every 60 s · "
    f"last update: {datetime.now().strftime('%H:%M:%S')} UTC · "
    f"source: **{MODE}**"
)

if not USE_RDS:
    st.info(
        "🖥️ **Local preview mode** — reading from `sample_data.csv`. "
        "Price history chart will be flat (single snapshot). "
        "Deploy to EC2 with RDS for live data.",
        icon="ℹ️",
    )

snapshot = load_latest_snapshot()

if snapshot.empty:
    st.warning("No data found. Make sure sample_data.csv exists at the repo root.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Coin selector")
    all_symbols       = snapshot["symbol"].tolist()
    default_selection = [s for s in DEFAULT_COINS if s in all_symbols]
    selected = st.multiselect("Choose coins", options=all_symbols, default=default_selection)
    st.markdown("---")
    period_map   = {"1 hour": 1, "6 hours": 6, "24 hours": 24, "7 days": 168, "30 days": 720, "All time": 0}
    period_label = st.selectbox("Chart period", list(period_map.keys()), index=2)
    chart_hours  = period_map[period_label]
    st.markdown("---")
    st.markdown("### 📊 Chart coin")
    chart_coin = st.selectbox("Price chart for", options=selected if selected else all_symbols, index=0)

if not selected:
    selected = default_selection

# ── KPI row ──────────────────────────────────────────────────────────────────────
btc        = snapshot[snapshot["symbol"] == "BTC"].iloc[0] if "BTC" in snapshot["symbol"].values else None
eth        = snapshot[snapshot["symbol"] == "ETH"].iloc[0] if "ETH" in snapshot["symbol"].values else None
total_mcap = snapshot["market_cap"].sum()
total_vol  = snapshot["volume_24h"].sum()

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("BTC Price",  fmt_price(btc["price"]) if btc is not None else "—",
              f'{btc["pct_24h"]:+.2f}% (24h)'       if btc is not None else "")
with k2:
    st.metric("ETH Price",  fmt_price(eth["price"]) if eth is not None else "—",
              f'{eth["pct_24h"]:+.2f}% (24h)'       if eth is not None else "")
with k3:
    st.metric("Total Mkt Cap (top 100)", fmt_large(total_mcap))
with k4:
    st.metric("Total Volume 24h", fmt_large(total_vol))

st.markdown("---")

# ── Price chart + % changes ───────────────────────────────────────────────────────
col_chart, col_pct = st.columns([2, 1])

with col_chart:
    st.markdown(f"#### {chart_coin} — price history ({period_label})")
    history = load_price_history(chart_coin, chart_hours)

    if history.empty:
        st.info(f"Not enough history yet for {chart_coin}.")
    else:
        fig = go.Figure()
        y_min = history["price"].min()
        y_max = history["price"].max()
        y_pad = (y_max - y_min) * 0.1 or y_min * 0.01

        fig.add_trace(go.Scatter(
            x=history["collected_at"],
            y=history["price"],
            mode="lines",
            line=dict(color="#f7931a", width=2),
            fill="toself",
            fillcolor="rgba(247,147,26,0.07)",
            name="Price",
            hovertemplate="<b>%{y:,.4f}</b> USD<br>%{x}<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(
                showgrid=True,
                gridcolor="#1e1e1e",
                range=[y_min - y_pad, y_max + y_pad],
            ),
            height=320,
            showlegend=False,
        )
        st.plotly_chart(fig, config={"responsive": True})

with col_pct:
    st.markdown(f"#### {chart_coin} — % changes")
    row = snapshot[snapshot["symbol"] == chart_coin]
    if not row.empty:
        r       = row.iloc[0]
        periods = ["1h", "24h", "7d", "30d"]
        values  = [r["pct_1h"], r["pct_24h"], r["pct_7d"], r["pct_30d"]]
        colors  = ["#00d26a" if (v or 0) >= 0 else "#ff4c4c" for v in values]

        fig2 = go.Figure(go.Bar(
            x=periods, y=values,
            marker_color=colors,
            text=[f"{v:+.2f}%" if v is not None else "—" for v in values],
            textposition="outside",
        ))
        fig2.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(showgrid=True, gridcolor="#1e1e1e", zeroline=True, zerolinecolor="#333"),
            height=320,
            showlegend=False,
        )
        st.plotly_chart(fig2, config={"responsive": True})

st.markdown("---")

# ── Top 100 live table ───────────────────────────────────────────────────────────
st.markdown("#### 📋 Top 100 — live snapshot")

table_df = snapshot[["cmc_rank", "symbol", "name", "price", "market_cap",
                      "volume_24h", "pct_1h", "pct_24h", "pct_7d", "pct_30d"]].copy()

table_df["price"]      = table_df["price"].apply(fmt_price)
table_df["market_cap"] = table_df["market_cap"].apply(fmt_large)
table_df["volume_24h"] = table_df["volume_24h"].apply(fmt_large)

for col in ["pct_1h", "pct_24h", "pct_7d", "pct_30d"]:
    table_df[col] = table_df[col].apply(pct_badge)

table_df.columns = ["#", "Symbol", "Name", "Price", "Mkt Cap", "Vol 24h", "1h %", "24h %", "7d %", "30d %"]
st.write(table_df.to_html(escape=False, index=False), unsafe_allow_html=True)

st.markdown("---")
st.caption("Data via CoinMarketCap · Stored on AWS RDS · Built with Streamlit")