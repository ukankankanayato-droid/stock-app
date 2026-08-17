import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 画面設定
st.set_page_config(page_title="Stock Chart App", layout="wide")

# カスタムCSS（スマホでの横並び固定・文字サイズ調整）
st.markdown(
    """
    <style>
    .stApp { background-color: #0d0d0d; color: #ffffff; }
    div[data-baseweb="input"] { background-color: #1a1a1a; color: #ffffff; }

    /* スマホ画面でも6列のカラムを横並びに維持 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 2px !important;
    }
    
    [data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 0% !important;
    }

    /* チェックボックスの文字サイズ縮小・折り返し防止 */
    [data-testid="stCheckbox"] {
        padding: 0 !important;
    }
    [data-testid="stCheckbox"] label {
        padding-left: 1px !important;
        gap: 2px !important;
    }
    [data-testid="stCheckbox"] label span p {
        font-size: 10px !important;
        white-space: nowrap !important;
        letter-spacing: -0.5px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 銘柄コード・会社名からの自動検索関数
def resolve_symbol(query):
    query = query.strip()
    if not query:
        return "150A.T"

    # すでに .T 付き
    if query.endswith(".T"):
        return query

    # 数値のみ（例: 7203）または150A等の英数コード
    if query.isdigit() or (len(query) == 4 and query[0].isdigit()):
        return f"{query}.T"

    # 銘柄名・企業名での検索 (Yahoo Finance Search API)
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(query)}&quotesCount=5&newsCount=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            quotes = data.get("quotes", [])
            # 日本株 (.T) を優先的に検索
            for q in quotes:
                symbol = q.get("symbol", "")
                if symbol.endswith(".T"):
                    return symbol
            # なければ最初の検索結果
            if quotes:
                return quotes[0].get("symbol", f"{query}.T")
    except Exception:
        pass

    return f"{query}.T"


# RCI (Rank Correlation Index) 計算関数
def calculate_rci(close, period):
    def _rci(s):
        d = np.arange(len(s))[::-1]
        rank_price = pd.Series(s).rank(ascending=False, method="min").values
        rank_time = pd.Series(d).rank(ascending=False, method="min").values
        sum_d2 = np.sum((rank_price - rank_time) ** 2)
        n = len(s)
        return (1 - (6 * sum_d2) / (n * (n**2 - 1))) * 100

    return close.rolling(window=period).apply(_rci, raw=True)


# データ取得関数
@st.cache_data(ttl=300)
def fetch_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# --- UI構成 ---
col_input, col_btn = st.columns([3, 1])
with col_input:
    user_input = st.text_input(
        "銘柄コードまたは銘柄名",
        value="150A",
        placeholder="例: 7203, トヨタ, 150A",
        label_visibility="collapsed",
    ).strip()
with col_btn:
    st.button("検索", use_container_width=True)

# 銘柄検索・解析
ticker_symbol = resolve_symbol(user_input)

# 指標切り替えチェックボックス（横並び強制）
c1, c2, c3, c4, c5, c6 = st.columns(6)
show_nikkei = c1.checkbox("日経", value=True)
show_ma5 = c2.checkbox("MA5", value=True)
show_ma25 = c3.checkbox("MA25", value=True)
show_ma75 = c4.checkbox("MA75", value=True)
show_rci = c5.checkbox("RCI", value=True)
show_macd = c6.checkbox("MACD", value=False)

# データロード
df = fetch_data(ticker_symbol)

if df.empty:
    st.error(f"データを取得できませんでした: {user_input} ({ticker_symbol})")
else:
    # 銘柄ヘッダー情報表示
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    diff = latest["Close"] - prev["Close"]
    pct = (diff / prev["Close"]) * 100

    st.markdown(
        f"**銘柄:** {user_input} ({ticker_symbol}) &nbsp;&nbsp; **始値:** ¥{latest['Open']:.1f} &nbsp;&nbsp; **終値:** ¥{latest['Close']:.1f} (<span style='color:{'#00e676' if diff>=0 else '#ff5252'}'>{diff:+.1f} / {pct:+.2f}%</span>) &nbsp;&nbsp; **安値:** ¥{latest['Low']:.1f} &nbsp;&nbsp; **高値:** ¥{latest['High']:.1f}",
        unsafe_allow_html=True,
    )

    # 3段チャート作成 (メイン, 出来高, RCI)
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.6, 0.15, 0.25],
        specs=[
            [{"secondary_y": True}],
            [{"secondary_y": False}],
            [{"secondary_y": False}],
        ],
    )

    # 1. メインチャート：ローソク足
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="株価",
            increasing_line_color="#00e676",
            decreasing_line_color="#ff5252",
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

    # 移動平均線
    if show_ma5:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"].rolling(5).mean(),
                name="MA5",
                line=dict(color="#ff9800", width=1.5),
            ),
            row=1,
            col=1,
        )
    if show_ma25:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"].rolling(25).mean(),
                name="MA25",
                line=dict(color="#00bcd4", width=1.5),
            ),
            row=1,
            col=1,
        )
    if show_ma75:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"].rolling(75).mean(),
                name="MA75",
                line=dict(color="#4caf50", width=1.5),
            ),
            row=1,
            col=1,
        )

    # 日経平均（オーバーレイ）
    if show_nikkei:
        nk_df = fetch_data("^N225")
        if not nk_df.empty:
            nk_df = nk_df.reindex(df.index).ffill()
            fig.add_trace(
                go.Scatter(
                    x=nk_df.index,
                    y=nk_df["Close"],
                    name="日経225",
                    line=dict(color="#e91e63", width=1.5),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

    # 2. 出来高
    colors = [
        "#00e676" if c >= o else "#ff5252"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"], name="出来高", marker_color=colors, opacity=0.7
        ),
        row=2,
        col=1,
    )

    # 3. RCI
    if show_rci:
        rci9 = calculate_rci(df["Close"], 9)
        rci26 = calculate_rci(df["Close"], 26)
        rci52 = calculate_rci(df["Close"], 52)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rci9,
                name="RCI(9)",
                line=dict(color="#00bfa5", width=1.2),
            ),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rci26,
                name="RCI(26)",
                line=dict(color="#9c27b0", width=1.2),
            ),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rci52,
                name="RCI(52)",
                line=dict(color="#ffeb3b", width=1.2),
            ),
            row=3,
            col=1,
        )

        for line_y in [80, 0, -80]:
            fig.add_hline(
                y=line_y,
                line_dash="dash",
                line_color="#444444",
                line_width=1,
                row=3,
                col=1,
            )

    # チャート設定：指で触ってもドラッグ・拡大が動かないように固定
    fig.update_layout(
        template="plotly_dark",
        height=680,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        dragmode=False,  # ドラッグ移動を無効化
    )

    # 軸の移動・ズームを固定（スマホでの画面上下スクロールを妨げない）
    fig.update_xaxes(fixedrange=True, showgrid=True, gridcolor="#1f1f1f")
    fig.update_yaxes(fixedrange=True, showgrid=True, gridcolor="#1f1f1f")

    # タッチ操作の挙動制御
    plotly_config = {
        "scrollZoom": False,
        "displayModeBar": False,
        "doubleClick": False,
    }

    st.plotly_chart(fig, use_container_width=True, config=plotly_config)
