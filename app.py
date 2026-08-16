import datetime
import io
import time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

st.set_page_config(
    page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed"
)

st.title("📈 株価分析アプリ")


# 日本取引所グループ(JPX)公式から全上場銘柄データ（約4,000銘柄）を取得してキャッシュ
@st.cache_data(ttl=86400)
def get_all_jpx_stocks():
  url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  try:
    res = requests.get(url, headers=headers, timeout=10)
    df = pd.read_excel(io.BytesIO(res.content))

    # コードを4桁文字列に整形
    df["コード"] = df["コード"].astype(str).str.zfill(4)
    df = df[df["コード"].str.len() == 4]

    # ドロップダウン検索用フォーマット (例: "3407 | 旭化成 (プライム)")
    df["label"] = (
        df["コード"]
        + " | "
        + df["銘柄名"]
        + " ("
        + df["市場・商品区分"].astype(str)
        + ")"
    )
    options = df["label"].tolist()
    code_map = dict(zip(df["label"], df["コード"]))
    return options, code_map
  except Exception:
    # ネットワークエラー等のフォールバックリスト
    default_options = [
        "3407 | 旭化成 (プライム)",
        "7203 | トヨタ自動車 (プライム)",
        "9984 | ソフトバンクグループ (プライム)",
        "6758 | ソニーグループ (プライム)",
        "8306 | 三菱UFJフィナンシャル・グループ (プライム)",
        "6861 | キーエンス (プライム)",
        "8035 | 東京エレクトロン (プライム)",
        "6920 | レーザーテック (プライム)",
        "9983 | ファーストリテイリング (プライム)",
        "9432 | 日本電信電話 (プライム)",
        "7974 | 任天堂 (プライム)",
        "6501 | 日立製作所 (プライム)",
    ]
    default_map = {opt: opt.split(" | ")[0] for opt in default_options}
    return default_options, default_map


stock_options, code_map = get_all_jpx_stocks()

# 時間足マップ
TIMEFRAMES = {
    "1分足": ("1m", 1, 5, 25),
    "2分足": ("2m", 2, 5, 25),
    "5分足": ("5m", 5, 5, 25),
    "15分足": ("15m", 7, 5, 25),
    "30分足": ("30m", 14, 5, 25),
    "60分足": ("60m", 30, 5, 25),
    "日足": ("1d", 180, 5, 25),
    "週足": ("1wk", 730, 13, 26),
    "月足": ("1mo", 1825, 12, 24),
}

col1, col2 = st.columns([2, 1])

with col1:
  # 初期選択位置（デフォルト: 旭化成）
  default_idx = 0
  for i, opt in enumerate(stock_options):
    if "3407" in opt:
      default_idx = i
      break

  selected_stock = st.selectbox(
      "銘柄を検索・選択（コードや銘柄名の一部を入力すると候補が出ます）",
      options=stock_options,
      index=default_idx,
  )
  code = code_map.get(selected_stock, "3407")

with col2:
  selected_tf = st.selectbox(
      "足種（時間足）", list(TIMEFRAMES.keys()), index=6
  )  # デフォルト: 日足

interval, days, sma_short, sma_long = TIMEFRAMES[selected_tf]


def fetch_stock_data(symbol_code, interval, days):
  ticker = f"{symbol_code}.T" if symbol_code.isdigit() else symbol_code
  end_ts = int(time.time())
  start_ts = end_ts - (days * 86400)

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval={interval}"

  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code != 200:
      url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval={interval}"
      res = requests.get(url, headers=headers, timeout=10)
      if res.status_code != 200:
        return None

    data = res.json()
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    if not timestamps or not closes:
      return None

    records = []
    for ts, o, h, l, c, v in zip(
        timestamps, opens, highs, lows, closes, volumes
    ):
      if o is not None and h is not None and l is not None and c is not None:
        dt = datetime.datetime.fromtimestamp(ts)
        date_str = (
            dt.strftime("%m/%d %H:%M")
            if "m" in interval
            else dt.strftime("%Y-%m-%d")
        )
        records.append({
            "Date": dt,
            "DateStr": date_str,
            "Open": o,
            "High": h,
            "Low": l,
            "Close": c,
            "Volume": v if v is not None else 0,
        })

    df = pd.DataFrame(records)
    return df if not df.empty else None
  except Exception:
    return None


if code:
  df = fetch_stock_data(code, interval, days)

  if df is None or df.empty:
    st.error(
        f"銘柄コード「{code}」のデータを取得できませんでした。取引時間外またはデータ未更新の可能性があります。"
    )
  else:
    df["SMA_S"] = df["Close"].rolling(window=sma_short).mean()
    df["SMA_L"] = df["Close"].rolling(window=sma_long).mean()

    latest_price = df["Close"].iloc[-1]
    st.metric(
        label=f"銘柄: {selected_stock} [{selected_tf}] (最新終値)",
        value=f"{latest_price:,.1f} 円",
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )

    fig.add_trace(
        go.Candlestick(
            x=df["DateStr"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="株価",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["DateStr"],
            y=df["SMA_S"],
            mode="lines",
            name=f"{sma_short}本線",
            line=dict(color="orange", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["DateStr"],
            y=df["SMA_L"],
            mode="lines",
            name=f"{sma_long}本線",
            line=dict(color="#00BFFF", width=1.5),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=df["DateStr"], y=df["Volume"], name="出来高", marker_color="gray"
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=500,
        showlegend=False,
    )

    fig.update_xaxes(type="category")

    st.plotly_chart(fig, use_container_width=True)
