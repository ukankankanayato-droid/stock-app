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


# 日本取引所グループ(JPX)公式から全上場銘柄データを取得
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

    df["コード"] = df["コード"].astype(str).str.zfill(4)
    df = df[df["コード"].str.len() == 4]

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
  )

interval, days, sma_short, sma_long = TIMEFRAMES[selected_tf]


# 市況詳細情報（PER、PBR、時価総額、配当、年初来高安など）を取得する関数
@st.cache_data(ttl=300)
def fetch_market_info(symbol_code):
  ticker = f"{symbol_code}.T" if symbol_code.isdigit() else symbol_code
  url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=summaryDetail,price,defaultKeyStatistics"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  info = {}
  try:
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      data = res.json()["quoteSummary"]["result"][0]
      summary = data.get("summaryDetail", {})
      price = data.get("price", {})
      stats = data.get("defaultKeyStatistics", {})

      info["前日終値"] = price.get("regularMarketPreviousClose", {}).get(
          "raw"
      )
      info["始値"] = price.get("regularMarketOpen", {}).get("raw")
      info["高値"] = price.get("regularMarketDayHigh", {}).get("raw")
      info["安値"] = price.get("regularMarketDayLow", {}).get("raw")
      info["出来高"] = price.get("regularMarketVolume", {}).get("raw")

      mcap = price.get("marketCap", {}).get("raw")
      info["時価総額"] = (
          f"{mcap / 100000000:,.1f} 億円" if mcap else "---"
      )

      pe = summary.get("trailingPE", {}).get("raw")
      info["PER"] = f"{pe:.2f} 倍" if pe else "---"

      pbr = stats.get("priceToBook", {}).get("raw")
      info["PBR"] = f"{pbr:.2f} 倍" if pbr else "---"

      div_yield = summary.get("dividendYield", {}).get("raw")
      div_rate = summary.get("dividendRate", {}).get("raw")
      if div_yield:
        info["配当利回り"] = f"{div_yield * 100:.2f} %"
      elif div_rate:
        info["配当利回り"] = f"{div_rate} 円"
      else:
        info["配当利回り"] = "---"

      high_52 = summary.get("fiftyTwoWeekHigh", {}).get("raw")
      low_52 = summary.get("fiftyTwoWeekLow", {}).get("raw")
      info["年初来高値"] = f"{high_52:,.1f} 円" if high_52 else "---"
      info["年初来安値"] = f"{low_52:,.1f} 円" if low_52 else "---"
      info["単元株式"] = "100 株"
  except Exception:
    pass
  return info


# 株価チャートデータ取得関数
def fetch_stock_data(symbol_code, interval, days):
  ticker = f"{symbol_code}.T" if symbol_code.isdigit() else symbol_code
  end_ts = int(time.time())
  start_ts = end_ts - (days * 86400)

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
  market_info = fetch_market_info(code)

  if df is None or df.empty:
    st.error(f"銘柄コード「{code}」のデータを取得できませんでした。")
  else:
    latest_price = df["Close"].iloc[-1]
    prev_price = (
        market_info.get("前日終値")
        if market_info.get("前日終値")
        else df["Close"].iloc[-2]
    )
    diff = latest_price - prev_price if prev_price else 0
    diff_pct = (diff / prev_price * 100) if prev_price else 0

    # 上部ヘッダー（株価・前日比）
    st.metric(
        label=f"銘柄: {selected_stock} [{selected_tf}]",
        value=f"{latest_price:,.1f} 円",
        delta=f"{diff:+.1f} 円 ({diff_pct:+.2f}%)",
    )

    # 市況情報パネルを表示
    with st.expander("📋 市況情報（PER / PBR / 時価総額 / 年初来高安 など）", expanded=True):
      m1, m2, m3, m4, m5 = st.columns(5)
      with m1:
        st.write(
            "**前日終値:**",
            (
                f"{market_info.get('前日終値'):,.1f} 円"
                if market_info.get("前日終値")
                else "---"
            ),
        )
        st.write(
            "**始値:**",
            (
                f"{market_info.get('始値'):,.1f} 円"
                if market_info.get("始値")
                else "---"
            ),
        )
      with m2:
        st.write(
            "**高値:**",
            (
                f"{market_info.get('高値'):,.1f} 円"
                if market_info.get("高値")
                else "---"
            ),
        )
        st.write(
            "**安値:**",
            (
                f"{market_info.get('安値'):,.1f} 円"
                if market_info.get("安値")
                else "---"
            ),
        )
      with m3:
        st.write(
            "**出来高:**",
            (
                f"{market_info.get('出来高'):,} 株"
                if market_info.get("出来高")
                else "---"
            ),
        )
        st.write("**時価総額:**", market_info.get("時価総額", "---"))
      with m4:
        st.write("**PER:**", market_info.get("PER", "---"))
        st.write("**PBR:**", market_info.get("PBR", "---"))
      with m5:
        st.write("**配当利回り:**", market_info.get("配当利回り", "---"))
        st.write(
            "**年初来高値/安値:**",
            f"{market_info.get('年初来高値', '---')} /"
            f" {market_info.get('年初来安値', '---')}",
        )

    # 2段チャート（ローソク足 ＋ 移動平均線 ＋ 出来高）
    df["SMA_S"] = df["Close"].rolling(window=sma_short).mean()
    df["SMA_L"] = df["Close"].rolling(window=sma_long).mean()

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
