import datetime
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

# 主要銘柄リスト
STOCK_DICT = {
    "直接入力（コード指定）": "CUSTOM",
    "旭化成 (3407)": "3407",
    "ソフトバンクG (9984)": "9984",
    "トヨタ自動車 (7203)": "7203",
    "ソニーグループ (6758)": "6758",
    "三菱UFJ FG (8306)": "8306",
    "キーエンス (6861)": "6861",
    "東京エレクトロン (8035)": "8035",
    "レーザーテック (6920)": "6920",
    "ファーストリテイリング (9983)": "9983",
    "NTT (9432)": "9432",
    "任天堂 (7974)": "7974",
    "日立製作所 (6501)": "6501",
    "三井住友FG (8316)": "8316",
    "三菱商事 (8058)": "8058",
}

# 時間足の定義マップ (表示名: (interval, 取得日数, 短期移動平均, 長期移動平均))
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
  selected_option = st.selectbox(
      "銘柄を選択または直接入力", list(STOCK_DICT.keys())
  )

with col2:
  selected_tf = st.selectbox(
      "足種（時間足）", list(TIMEFRAMES.keys()), index=6
  )  # デフォルト: 日足

if STOCK_DICT[selected_option] == "CUSTOM":
  user_input = st.text_input("銘柄コードを入力（例: 3407, 7203）", "3407")
  code = user_input.strip()
else:
  code = STOCK_DICT[selected_option]

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
        # 分足は時刻まで表示、日足以上は日付のみ表示
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
        "株価データが取得できませんでした。取引時間外または銘柄コードをご確認ください。"
    )
  else:
    # 足種に応じた移動平均線
    df["SMA_S"] = df["Close"].rolling(window=sma_short).mean()
    df["SMA_L"] = df["Close"].rolling(window=sma_long).mean()

    latest_price = df["Close"].iloc[-1]
    st.metric(
        label=f"銘柄コード: {code} [{selected_tf}] (最新終値)",
        value=f"{latest_price:,.1f} 円",
    )

    # 2段チャート（ローソク足 ＋ 出来高）
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )

    # ローソク足
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

    # 移動平均線
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

    # 出来高
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
