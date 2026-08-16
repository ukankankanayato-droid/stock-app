import datetime
import io
import json
import os
import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

st.set_page_config(
    page_title="株価分析アプリ", layout="wide", initial_sidebar_state="expanded"
)

# タイトル
st.markdown(
    "<h2 style='font-size: 22px; font-weight: bold; margin-bottom: 12px;'>📈"
    " 株価分析アプリ</h2>",
    unsafe_allow_html=True,
)

# --- 保有データのローカル保存機能 ---
HOLDINGS_FILE = "holdings.json"


def load_holdings():
  if os.path.exists(HOLDINGS_FILE):
    try:
      with open(HOLDINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def save_holdings(data):
  try:
    with open(HOLDINGS_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
  except Exception as e:
    st.error(f"保存処理中にエラーが発生しました: {e}")


if "holdings" not in st.session_state:
  st.session_state["holdings"] = load_holdings()


# JPX全銘柄取得
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
    df["市場"] = (
        df["市場・商品区分"].astype(str).str.replace(r"（.*）", "", regex=True)
    )
    df["label"] = df["コード"] + " | " + df["銘柄名"] + " (" + df["市場"] + ")"
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

# 銘柄選択
col1, col2 = st.columns([2, 1])
with col1:
  default_idx = 0
  for i, opt in enumerate(stock_options):
    if "3407" in opt:
      default_idx = i
      break
  selected_stock = st.selectbox(
      "銘柄検索（コード・名称）", options=stock_options, index=default_idx
  )
  code = code_map.get(selected_stock, "3407")

with col2:
  selected_tf = st.selectbox(
      "足種（時間足）", list(TIMEFRAMES.keys()), index=6
  )

interval, days, sma_short, sma_long = TIMEFRAMES[selected_tf]

# --- サイドバー：保有データ設定と保存管理 ---
st.sidebar.header("💼 保有株の設定")

saved_item = st.session_state["holdings"].get(code, {})
is_saved = code in st.session_state["holdings"]

is_holding = st.sidebar.checkbox(
    "この銘柄を保有している",
    value=is_saved,
    key=f"is_holding_{code}",
)

buy_price = 0.0
holding_qty = 0

if is_holding:
  default_price = float(saved_item.get("buy_price", 1000.0))
  default_qty = int(saved_item.get("qty", 100))

  buy_price = st.sidebar.number_input(
      "平均取得単価（購入株価 / 円）",
      min_value=0.0,
      value=default_price,
      step=10.0,
      key=f"buy_price_{code}",
  )
  holding_qty = st.sidebar.number_input(
      "保有株数（株）",
      min_value=0,
      value=default_qty,
      step=100,
      key=f"holding_qty_{code}",
  )

  col_btn1, col_btn2 = st.sidebar.columns(2)
  with col_btn1:
    if st.sidebar.button("💾 設定を保存", key=f"btn_save_{code}"):
      stock_name = (
          selected_stock.split(" | ")[1]
          if " | " in selected_stock
          else selected_stock
      )
      st.session_state["holdings"][code] = {
          "name": stock_name,
          "buy_price": buy_price,
          "qty": holding_qty,
      }
      save_holdings(st.session_state["holdings"])
      st.sidebar.success("保存しました！")
  with col_btn2:
    if is_saved and st.sidebar.button("🗑️ 解除", key=f"btn_del_{code}"):
      del st.session_state["holdings"][code]
      save_holdings(st.session_state["holdings"])
      st.sidebar.info("保存を解除しました。")
      st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📂 バックアップ / 復元")

# バックアップダウンロード機能
json_str = json.dumps(
    st.session_state["holdings"], ensure_ascii=False, indent=2
)
st.sidebar.download_button(
    label="📥 ポートフォリオ設定を保存",
    data=json_str,
    file_name="my_portfolio.json",
    mime="application/json",
    use_container_width=True,
)

# 復元アップロード機能
uploaded_file = st.sidebar.file_uploader(
    "📤 設定ファイルを読み込む", type=["json"]
)
if uploaded_file is not None:
  try:
    imported_data = json.load(uploaded_file)
    st.session_state["holdings"] = imported_data
    save_holdings(imported_data)
    st.sidebar.success("設定を復元しました！")
  except Exception as e:
    st.sidebar.error(f"読み込み失敗: {e}")


# --- 株価データ取得関数 ---
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

  opens, highs, lows, closes, volumes = (
      quote.get("open", []),
      quote.get("high", []),
      quote.get("low", []),
      quote.get("close", []),
      quote.get("volume", []),
  )
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
  return pd.DataFrame(records), meta


def get_from_kabutan(code):
  url = f"https://kabutan.jp/stock/?code={code}"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  res = requests.get(url, headers=headers, timeout=5)
  if res.status_code != 200:
    return None
  soup = BeautifulSoup(res.text, "html.parser")
  text = soup.get_text()
  info = {}
  m_per = re.search(r"PER[^\d]*([\d\.]+)\s*倍", text)
  if m_per:
    info["PER"] = f"{m_per.group(1)} 倍"
  m_pbr = re.search(r"PBR[^\d]*([\d\.]+)\s*倍", text)
  if m_pbr:
    info["PBR"] = f"{m_pbr.group(1)} 倍"
  m_div = re.search(r"利回り[^\d]*([\d\.]+)\s*%", text)
  if m_div:
    info["配当利回り"] = f"{m_div.group(1)} %"
  m_cap = re.search(r"時価総額[^\d]*([\d,]+)\s*(億円|百万円)", text)
  if m_cap:
    info["時価総額"] = f"{m_cap.group(1)} {m_cap.group(2)}"
  return info


def get_from_minkabu(code):
  url = f"https://minkabu.jp/stock/{code}"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  res = requests.get(url, headers=headers, timeout=5)
  if res.status_code != 200:
    return None
  soup = BeautifulSoup(res.text, "html.parser")
  text = soup.get_text()
  info = {}
  m_per = re.search(r"PER[^\d]*([\d\.]+)\s*倍", text)
  if m_per:
    info["PER"] = f"{m_per.group(1)} 倍"
  m_pbr = re.search(r"PBR[^\d]*([\d\.]+)\s*倍", text)
  if m_pbr:
    info["PBR"] = f"{m_pbr.group(1)} 倍"
  m_div = re.search(r"(?:予想)?配当利回り[^\d]*([\d\.]+)\s*%", text)
  if m_div:
    info["配当利回り"] = f"{m_div.group(1)} %"
  m_cap = re.search(r"時価総額[^\d]*([\d,]+)\s*(百万円|億円|兆円)", text)
  if m_cap:
    info["時価総額"] = f"{m_cap.group(1)} {m_cap.group(2)}"
  return info


def get_from_yahoo_jp(code):
  url = f"https://finance.yahoo.co.jp/quote/{code}.T"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  res = requests.get(url, headers=headers, timeout=5)
  if res.status_code != 200:
    return None
  soup = BeautifulSoup(res.text, "html.parser")
  text = soup.get_text()
  info = {}
  m_per = re.search(r"PER[^\d]*([\d\.]+)\s*倍", text)
  if m_per:
    info["PER"] = f"{m_per.group(1)} 倍"
  m_pbr = re.search(r"PBR[^\d]*([\d\.]+)\s*倍", text)
  if m_pbr:
    info["PBR"] = f"{m_pbr.group(1)} 倍"
  m_div = re.search(r"配当利回り[^\d]*([\d\.]+)\s*%", text)
  if m_div:
    info["配当利回り"] = f"{m_div.group(1)} %"
  m_cap = re.search(r"時価総額[^\d]*([\d,]+)\s*(百万円|億円|兆円)", text)
  if m_cap:
    info["時価総額"] = f"{m_cap.group(1)} {m_cap.group(2)}"
  return info


@st.cache_data(ttl=300)
def fetch_extra_quote_info(symbol_code):
  info = {"PER": "---", "PBR": "---", "時価総額": "---", "配当利回り": "---"}
  for fetch_func in [get_from_kabutan, get_from_minkabu, get_from_yahoo_jp]:
    try:
      data = fetch_func(symbol_code)
      if data:
        for k, v in data.items():
          if info[k] == "---" and v:
            info[k] = v
    except Exception:
      pass
    if not any(v == "---" for v in info.values()):
      break
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

    # 保有株計算処理
    if is_holding and buy_price > 0:
      price_diff = latest_price - buy_price
      price_diff_pct = (price_diff / buy_price) * 100
      total_profit = price_diff * holding_qty

      raw_div_str = extra_info.get("配当利回り", "---").replace("%", "").strip()
      try:
        current_div_yield = float(raw_div_str)
        yoc = current_div_yield * (latest_price / buy_price)
        yoc_str = f"{yoc:.2f} %"
      except ValueError:
        yoc_str = "---"

      st.subheader("💰 保有株の損益・利回り状況")
      p_col1, p_col2, p_col3 = st.columns(3)
      p_col1.metric(
          label="1株あたりの株価差",
          value=f"{price_diff:+.1f} 円",
          delta=f"{price_diff_pct:+.2f}%",
      )
      p_col2.metric(
          label="総額の評価損益",
          value=f"{total_profit:+,.0f} 円",
          delta=f"{holding_qty:,} 株保有",
      )
      p_col3.metric(
          label="取得株価の利回り（YOC）",
          value=yoc_str,
          help=(
              "現在の配当利回りと平均取得単価から算出した、購入価格に対する年間配当利回りです"
          ),
      )

    # 保存済みの保有銘柄一覧
    if st.session_state["holdings"]:
      with st.expander("📁 保存中の保有銘柄リスト一覧", expanded=False):
        list_data = []
        for h_code, h_info in st.session_state["holdings"].items():
          list_data.append({
              "銘柄コード": h_code,
              "銘柄名": h_info.get("name", "---"),
              "平均取得単価 (円)": f"{h_info.get('buy_price', 0):,.1f}",
              "保有株数 (株)": f"{h_info.get('qty', 0):,}",
              "投資原本 (円)": (
                  f"{h_info.get('buy_price', 0) * h_info.get('qty', 0):,.0f}"
              ),
          })
        st.dataframe(pd.DataFrame(list_data), use_container_width=True)

    day_high = meta.get("regularMarketDayHigh") or df["High"].max()
    day_low = meta.get("regularMarketDayLow") or df["Low"].min()
    day_vol = meta.get("regularMarketVolume") or df["Volume"].iloc[-1]
    high_52 = meta.get("fiftyTwoWeekHigh")
    low_52 = meta.get("fiftyTwoWeekLow")

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

    # チャート表示
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

    # --- チャート上の水平線（現在値 & 平均取得単価）の追加 ---
    # 現在値（緑色の破線）
    fig.add_hline(
        y=latest_price,
        line_dash="dash",
        line_color="#00FF7F",
        line_width=1.5,
        annotation_text=f"現在値: {latest_price:,.1f}円",
        annotation_position="bottom right",
        annotation_font_color="#00FF7F",
        row=1,
        col=1,
    )

    # 平均取得単価（保有設定されている場合のみ表示）
    if is_holding and buy_price > 0:
      fig.add_hline(
          y=buy_price,
          line_dash="dot",
          line_color="#FF4500",
          line_width=1.5,
          annotation_text=f"平均取得単価: {buy_price:,.1f}円",
          annotation_position="top right",
          annotation_font_color="#FF4500",
          row=1,
          col=1,
      )

    # 初期表示範囲を直近60本に設定（左右スクロール・移動を可能に）
    total_len = len(df)
    display_count = min(60, total_len)
    start_idx = total_len - display_count
    end_idx = total_len - 1

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=500,
        showlegend=False,
        dragmode="pan",  # マウスドラッグでの移動（パン操作）をデフォルトに設定
    )
    fig.update_xaxes(type="category", range=[start_idx, end_idx])
    st.plotly_chart(fig, use_container_width=True)
