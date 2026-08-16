import datetime
import io
import re
import time
from bs4 import BeautifulSoup
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


# チャートデータとmeta情報を取得
def fetch_stock_data_and_meta(symbol_code, interval, days):
  ticker = f"{symbol_code}.T" if symbol_code.isdigit() else symbol_code
  end_ts = int(time.time())
  start_ts = end_ts - (days * 86400)

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  urls = [
      f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval={interval}",
      f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval={interval}",
  ]

  data = None
  for url in urls:
    try:
      res = requests.get(url, headers=headers, timeout=10)
      if res.status_code == 200:
        data = res.json()
        break
    except Exception:
      continue

  if not data or "chart" not in data or not data["chart"]["result"]:
    return None, {}

  result = data["chart"]["result"][0]
  meta = result.get("meta", {})
  timestamps = result.get("timestamp", [])
  quote = (
      result["indicators"]["quote"][0]
      if result.get("indicators", {}).get("quote")
      else {}
  )

  opens = quote.get("open", [])
  highs = quote.get("high", [])
  lows = quote.get("low", [])
  closes = quote.get("close", [])
  volumes = quote.get("volume", [])

  if not timestamps or not closes:
    return None, meta

  records = []
  for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes):
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
  return df, meta


# PER / PBR / 時価総額 / 配当利回りを取得する精密抽出関数
@st.cache_data(ttl=300)
def fetch_extra_quote_info(symbol_code):
  info = {"PER": "---", "PBR": "---", "時価総額": "---", "配当利回り": "---"}
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  try:
    url_k = f"https://kabutan.jp/stock/?code={symbol_code}"
    res_k = requests.get(url_k, headers=headers, timeout=5)
    if res_k.status_code == 200:
      soup_k = BeautifulSoup(res_k.text, "html.parser")
      fin_info = soup_k.find("div", id="stock_fin_info")
      if fin_info:
        for tr in fin_info.find_all("tr"):
          ths = tr.find_all("th")
          tds = tr.find_all("td")
          for th, td in zip(ths, tds):
            th_text = th.get_text(strip=True)
            td_text = td.get_text(strip=True)

            # (08/14) などの日付を除去して数値のみにする
            val_clean = re.sub(r"\(\d{2}/\d{2}\)", "", td_text).strip()

            if "PER" in th_text and info["PER"] == "---":
              if val_clean:
                info["PER"] = (
                    val_clean if "倍" in val_clean else f"{val_clean} 倍"
                )
            elif "PBR" in th_text and info["PBR"] == "---":
              if val_clean:
                info["PBR"] = (
                    val_clean if "倍" in val_clean else f"{val_clean} 倍"
                )
            elif "利回り" in th_text and info["配当利回り"] == "---":
              if val_clean:
                info["配当利回り"] = (
                    val_clean if "%" in val_clean else f"{val_clean} %"
                )
            elif "時価総額" in th_text and info["時価総額"] == "---":
              if val_clean:
                info["時価総額"] = val_clean
  except Exception:
    pass

  return info


if code:
  df, meta = fetch_stock_data_and_meta(code, interval, days)
  extra_info = fetch_extra_quote_info(code)

  if df is None or df.empty:
    st.error(f"銘柄コード「{code}」のデータを取得できませんでした。")
  else:
    latest_price = df["Close"].iloc[-1]
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    if not prev_close and len(df) > 1:
      prev_close = df["Close"].iloc[-2]

    diff = latest_price - prev_close if prev_close else 0
    diff_pct = (diff / prev_close * 100) if prev_close else 0

    st.metric(
        label=f"銘柄: {selected_stock} [{selected_tf}]",
        value=f"{latest_price:,.1f} 円",
        delta=f"{diff:+.1f} 円 ({diff_pct:+.2f}%)",
    )

    day_high = meta.get("regularMarketDayHigh") or df["High"].max()
    day_low = meta.get("regularMarketDayLow") or df["Low"].min()
    day_vol = meta.get("regularMarketVolume") or df["Volume"].iloc[-1]
    high_52 = meta.get("fiftyTwoWeekHigh")
    low_52 = meta.get("fiftyTwoWeekLow")

    # 市況情報パネル
    with st.expander(
        "📋 市況情報（PER / PBR / 時価総額 / 年初来高安 など）", expanded=True
    ):
      m1, m2, m3, m4, m5 = st.columns(5)
      with m1:
        st.write(
            "**前日終値:**",
            f"{prev_close:,.1f} 円" if prev_close else "---",
        )
        st.write(
            "**始値:**",
            f"{df['Open'].iloc[-1]:,.1f} 円" if not df.empty else "---",
        )
      with m2:
        st.write("**高値:**", f"{day_high:,.1f} 円" if day_high else "---")
        st.write("**安値:**", f"{day_low:,.1f} 円" if day_low else "---")
      with m3:
        st.write(
            "**出来高:**", f"{int(day_vol):,} 株" if day_vol else "---"
        )
        st.write("**時価総額:**", extra_info.get("時価総額", "---"))
      with m4:
        st.write("**PER:**", extra_info.get("PER", "---"))
        st.write("**PBR:**", extra_info.get("PBR", "---"))
      with m5:
        st.write("**配当利回り:**", extra_info.get("配当利回り", "---"))
        st.write(
            "**年初来高値/安値:**",
            f"{high_52:,.1f} 円 / {low_52:,.1f} 円"
            if high_52 and low_52
            else "---",
        )

    # 2段チャート（ローソク足 ＋ 出来高）
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
