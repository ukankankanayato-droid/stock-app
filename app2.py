import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 画面設定
st.set_page_config(page_title="Stock Chart App", layout="wide")

# カスタムCSS（スマホでの「6列完全横一列固定」＆「溢れ・縦積み防止」）
st.markdown(
    """
    <style>
    .stApp { background-color: #0d0d0d; color: #ffffff; }
    div[data-baseweb="input"], div[data-baseweb="select"] { 
        background-color: #1a1a1a !important; 
        color: #ffffff !important; 
    }

    /* スマホ画面で st.columns が縦積みになるのを強制的に横一列へ固定 */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: space-between !important;
        align-items: center !important;
        gap: 0px !important;
        width: 100% !important;
    }
    
    div[data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        padding: 0 1px !important;
    }

    /* チェックボックス全体の文字・余白をスマホ画面（360px〜）用に最小化 */
    [data-testid="stCheckbox"] {
        padding: 0 !important;
        margin: 0 !important;
    }
    [data-testid="stCheckbox"] label {
        padding-left: 0px !important;
        gap: 2px !important;
    }
    [data-testid="stCheckbox"] label span p {
        font-size: 10px !important;
        white-space: nowrap !important;
        color: #ffffff !important;
        letter-spacing: -0.8px !important;
    }
    /* チェックボックスのアイコンをわずかに縮小して横幅を確保 */
    [data-testid="stCheckbox"] label span div {
        transform: scale(0.8);
        margin: 0 -2px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# 候補銘柄辞書
STOCK_CANDIDATES = {
    "150A | JSH": "150A.T",
    "6986 | フタバ産業": "6986.T",
    "7203 | トヨタ自動車": "7203.T",
    "6758 | ソニーグループ": "6758.T",
    "9984 | ソフトバンクグループ": "9984.T",
    "8306 | 三菱UFJフィナンシャルG": "8306.T",
    "6857 | アドバンテスト": "6857.T",
    "8035 | 東京エレクトロン": "8035.T",
    "7201 | 日産自動車": "7201.T",
    "7267 | ホンダ": "7267.T",
    "9104 | 商船三井": "9104.T",
    "6146 | ディスコ": "6146.T",
    "6501 | 日立製作所": "6501.T",
    "🔍 リストにない銘柄を自由入力": "CUSTOM",
}


# 銘柄自動検索関数
def resolve_symbol(query):
    query = query.strip()
    if not query:
        return "150A.T"
    if query.endswith(".T"):
        return query
    if query.isdigit() or (len(query) == 4 and query[0].isdigit()):
        return f"{query}.T"

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(query)}&quotesCount=5&newsCount=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            quotes = res.json().get("quotes", [])
            for q in quotes:
                symbol = q.get("symbol", "")
                if symbol.endswith(".T"):
                    return symbol
            if quotes:
                return quotes[0].get("symbol", f"{query}.T")
    except Exception:
        pass
    return f"{query}.T"


# RCI計算関数
def calculate_rci(close, period):
    def _rci(s):
        d = np.arange(len(s))[::-1]
        rank_price = pd.Series(s).rank(ascending=False, method="min").values
        rank_time = pd.Series(d).rank(ascending=False, method="min").values
        sum_d2 = np.sum((rank_price - rank_time) ** 2)
        n = len(s)
        return (1 - (6 * sum_d2) / (n * (n**2 - 1))) * 100

    return close.rolling(window=period).apply(_rci, raw=True)


# データ取得関数（NaN行の自動除外処理を追加）
@st.cache_data(ttl=300)
def fetch_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # 株価データがないNaN行（市場準備時間など）を除外
    df = df.dropna(subset=["Close", "Open", "High", "Low"])
    return df


# --- UI構成 ---
selected_option = st.selectbox(
    "銘柄選択",
    options=list(STOCK_CANDIDATES.keys()),
    index=0,
    label_visibility="collapsed",
)

if selected_option == "🔍 リストにない銘柄を自由入力":
    custom_input = st.text_input(
        "銘柄コードまたは銘柄名を入力",
        value="",
        placeholder="例: 7241, フタバ",
    ).strip()
    ticker_symbol = resolve_symbol(custom_input) if custom_input else "150A.T"
    display_title = custom_input if custom_input else "150A"
else:
    ticker_symbol = STOCK_CANDIDATES[selected_option]
    display_title = selected_option

# チェックボックス（スマホ画面幅に合わせて1行6並びを固定）
c1, c2, c3, c4, c5, c6 = st.columns(6)
show_nikkei = c1.checkbox("日経", value=True)
show_ma5 = c2.checkbox("MA5", value=True)
show_ma25 = c3.checkbox("MA25", value=True)
show_ma75 = c4.checkbox("MA75", value=True)
show_rci = c5.checkbox("RCI", value=True)
show_macd = c6.checkbox("MACD", value=False)

# データ取得
df = fetch_data(ticker_symbol)

if df.empty:
    st.error(f"データを取得できませんでした: {display_title}")
else:
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    diff = latest["Close"] - prev["Close"]
    pct = (diff / prev["Close"]) * 100

    st.markdown(
        f"**{display_title}** ({ticker_symbol})<br>"
        f"**始値:** ¥{latest['Open']:.1f} &nbsp; **終値:** ¥{latest['Close']:.1f} "
        f"(<span style='color:{'#00e676' if diff>=0 else '#ff5252'}'>{diff:+.1f} / {pct:+.2f}%</span>)<br>"
        f"**安値:** ¥{latest['Low']:.1f} &nbsp; **高値:** ¥{latest['High']:.1f}",
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

    # ローソク足
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

    # 日経平均
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

    # 出来高
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

    # RCI
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

    # レイアウト設定
    fig.update_layout(
        template="plotly_dark",
        height=660,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True, showgrid=True, gridcolor="#1f1f1f")
    fig.update_yaxes(fixedrange=True, showgrid=True, gridcolor="#1f1f1f")

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": False, "displayModeBar": False},
    )
