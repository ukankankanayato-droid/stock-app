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
  user_input = st.text_input(
      "銘柄コードまたは銘柄名を入力（例: 3407, 旭化成, トヨタ, 9984）",
      value="旭化成",
      placeholder="例: 3407 または 旭化成",
  )

with col2:
  selected_tf = st.selectbox(
      "足種（時間足）", list(TIMEFRAMES.keys()), index=6
  )  # デフォルト: 日足

interval, days, sma_short, sma_long = TIMEFRAMES[selected_tf]


# 銘柄名・コードからTickerシンボルを自動判定する関数
def resolve_ticker(query):
  query = query.strip()
  if not query:
    return None, None

  # 数字のみ（4桁など）の場合は直接指定
  if query.isdigit():
    return f"{query}.T", query

  # 主要銘柄の高速検索辞書
  COMMON_STOCKS = {
      "旭化成": ("3407.T", "3407 旭化成"),
      "ソフトバンク": ("9984.T", "9984 ソフトバンクG"),
      "ソフトバンクg": ("9984.T", "9984 ソフトバンクG"),
      "ソフトバンクグループ": ("9984.T", "9984 ソフトバンクG"),
      "トヨタ": ("7203.T", "7203 トヨタ自動車"),
      "トヨタ自動車": ("7203.T", "7203 トヨタ自動車"),
      "ソニー": ("6758.T", "6758 ソニーグループ"),
      "ソニーグループ": ("6758.T", "6758 ソニーグループ"),
      "三菱ufj": ("8306.T", "8306 三菱UFJ FG"),
      "キーエンス": ("6861.T", "6861 キーエンス"),
      "東京エレクトロン": ("8035.T", "8035 東京エレクトロン"),
      "レーザーテック": ("6920.T", "6920 レーザーテック"),
      "ファーストリテイリング": (
          "9983.T",
          "9983 ファーストリテイリング",
      ),
      "ユニクロ": ("9983.T", "9983 ファーストリテイリング"),
      "ntt": ("9432.T", "9432 NTT"),
      "任天堂": ("7974.T", "7974 任天堂"),
      "日立": ("6501.T", "6501 日立製作所"),
      "日立製作所": ("6501.T", "6501 日立製作所"),
      "三井住友": ("8316.T", "8316 三井住友FG"),
      "三菱商事": ("8058.T", "8058 三菱商事"),
  }

  q_lower = query.lower()
  if q_lower in COMMON_STOCKS:
    return COMMON_STOCKS[q_lower]

  # 辞書にない銘柄名はYahoo Financeの検索APIで自動補完
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }
  search_url = f"https://query2.finance.yahoo.com/1/finance/search?q={query}&quotesCount=5&newsCount=0"

  try:
    res = requests.get(search_url, headers=headers, timeout=5)
    if res.status_code == 200:
      quotes = res.json().get("quotes", [])
      for q in quotes:
        symbol = q.get("symbol", "")
        if symbol.endswith(".T"):
          short_name = q.get("shortname") or q.get("longname") or query
          code_num = symbol.replace(".T", "")
          return symbol, f"{code_num} {short_name}"
      if quotes:
        sym = quotes[0].get("symbol")
        name = (
            quotes[0].get("shortname") or quotes[0].get("longname") or query
        )
        return sym, f"{sym} {name}"
  except Exception:
    pass

  return f"{query}.T", query


def fetch_stock_data(symbol, interval, days):
  end_ts = int(time.time())
  start_ts = end_ts - (days * 86400)

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval={interval}"

  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code != 200:
      url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval={interval}"
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


if user_input:
  symbol, display_label = resolve_ticker(user_input)

  if symbol:
    df = fetch_stock_data(symbol, interval, days)

    if df is None or df.empty:
      st.error(
          f"「{user_input}」の株価データを取得できませんでした。銘柄コード（4桁数字）または正確な銘柄名でお試しください。"
      )
    else:
      df["SMA_S"] = df["Close"].rolling(window=sma_short).mean()
      df["SMA_L"] = df["Close"].rolling(window=sma_long).mean()

      latest_price = df["Close"].iloc[-1]
      st.metric(
          label=f"銘柄: {display_label} [{selected_tf}] (最新終値)",
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
              x=df["DateStr"],
              y=df["Volume"],
              name="出来高",
              marker_color="gray",
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
