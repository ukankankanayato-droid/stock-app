import datetime
import io
import json
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

# セッション状態の初期化
if "holdings" not in st.session_state:
  st.session_state["holdings"] = {}


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
    code_to_name = dict(zip(df["コード"], df["銘柄名"]))
    return options, code_map, code_to_name
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
    default_names = {
        "3407": "旭化成",
        "7203": "トヨタ自動車",
        "9984": "ソフトバンクグループ",
        "6758": "ソニーグループ",
        "8306": "三菱UFJフィナンシャル・グループ",
        "6861": "キーエンス",
    }
    return default_options, default_map, default_names


stock_options, code_map, code_to_name = get_all_jpx_stocks()

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

# --- サイドバー設定 ---
st.sidebar.header("💼 設定・ナビゲーション")

app_mode = st.sidebar.radio(
    "表示モード", ["📈 個別銘柄チャート・分析", "📊 ポートフォリオ総合ダッシュボード"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 インジケーター・表示設定")
show_bollinger = st.sidebar.checkbox(
    "ボリンジャーバンド（20日 ±2σ）", value=False
)
show_rsi = st.sidebar.checkbox("RSI（14日）", value=False)
show_macd = st.sidebar.checkbox("MACD", value=False)

st.sidebar.markdown("---")
st.sidebar.subheader("🕹️ チャート操作")
enable_pan = st.sidebar.checkbox(
    "🖐️ チャートの左右移動（パン操作）を有効化",
    value=False,
    help="チェックを入れるとマウスや指でチャートを左右に移動・ズームできます。通常時の誤作動を防ぐ場合はオフにしてください。",
)

st.sidebar.markdown("---")
st.sidebar.subheader("📂 バックアップ / 復元")

json_str = json.dumps(
    st.session_state["holdings"], ensure_ascii=False, indent=2
)
st.sidebar.download_button(
    label="📥 ポートフォリオ設定を書き出す",
    data=json_str,
    file_name="my_portfolio.json",
    mime="application/json",
    use_container_width=True,
)

uploaded_file = st.sidebar.file_uploader(
    "📤 設定ファイルを読み込む", type=["json"]
)
if uploaded_file is not None:
  try:
    imported_data = json.load(uploaded_file)
    st.session_state["holdings"] = imported_data
    st.sidebar.success("設定を読み込みました！")
    st.rerun()
  except Exception as e:
    st.sidebar.error(f"読み込み失敗: {e}")


# --- データ取得関数 ---
def fetch_stock_data_and_meta(symbol_code, interval, days):
  ticker = (
      f"{symbol_code}.T"
      if (symbol_code.isdigit() or symbol_code.isalnum())
      else symbol_code
  )
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


def calculate_rsi(series, period=14):
  delta = series.diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
  rs = gain / loss
  return 100 - (100 / (1 + rs))


def calculate_macd(series, short=12, long=26, signal=9):
  ema_short = series.ewm(span=short, adjust=False).mean()
  ema_long = series.ewm(span=long, adjust=False).mean()
  macd = ema_short - ema_long
  macd_signal = macd.ewm(span=signal, adjust=False).mean()
  macd_hist = macd - macd_signal
  return macd, macd_signal, macd_hist


# === 画面切替 ===
if app_mode == "📊 ポートフォリオ総合ダッシュボード":
  st.subheader("📊 ポートフォリオ＆年間予想配当金ダッシュボード")

  holdings = st.session_state.get("holdings", {})
  if not holdings:
    st.info(
        "現在保有銘柄が登録されていません。個別銘柄画面から保有株の設定を行ってください。"
    )
  else:
    total_investment = 0.0
    total_current_value = 0.0
    total_annual_div = 0.0
    summary_data = []

    with st.spinner("保有銘柄の最新株価・配当情報を計算中..."):
      for h_code, h_info in holdings.items():
        qty = int(h_info.get("qty", 0))
        buy_p = float(h_info.get("buy_price", 0.0))
        annual_div = float(h_info.get("annual_div", 0.0))
        name = h_info.get("name", h_code)

        df_curr, _ = fetch_stock_data_and_meta(h_code, "1d", 5)
        if df_curr is not None and not df_curr.empty:
          curr_price = float(df_curr["Close"].iloc[-1])
        else:
          curr_price = buy_p

        invest = buy_p * qty
        curr_val = curr_price * qty
        diff = curr_val - invest
        diff_pct = (diff / invest * 100) if invest > 0 else 0.0

        item_annual_div = annual_div * qty
        total_annual_div += item_annual_div

        yoc = (annual_div / buy_p * 100) if buy_p > 0 else 0.0
        curr_yield = (annual_div / curr_price * 100) if curr_price > 0 else 0.0

        total_investment += invest
        total_current_value += curr_val

        summary_data.append({
            "コード": h_code,
            "銘柄名": name,
            "保有株数": f"{qty:,} 株",
            "取得単価": f"{buy_p:,.1f} 円",
            "現在値": f"{curr_price:,.1f} 円",
            "評価額": f"{curr_val:,.0f} 円",
            "評価損益": f"{diff:+,.0f} 円 ({diff_pct:+.2f}%)",
            "1株予想配当": f"{annual_div:,.1f} 円",
            "年間受取配当": f"{item_annual_div:,.0f} 円",
            "YOC (取得利回り)": f"{yoc:.2f} %",
        })

    total_diff = total_current_value - total_investment
    total_diff_pct = (
        (total_diff / total_investment * 100) if total_investment > 0 else 0.0
    )
    avg_yoc = (
        (total_annual_div / total_investment * 100)
        if total_investment > 0
        else 0.0
    )
    monthly_div = total_annual_div / 12.0

    st.markdown("### 💰 資産・配当金サマリー")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("総投資額", f"{total_investment:,.0f} 円")
    c2.metric("現在評価総額", f"{total_current_value:,.0f} 円")
    c3.metric(
        "トータル評価損益",
        f"{total_diff:+,.0f} 円",
        delta=f"{total_diff_pct:+.2f}%",
    )
    c4.metric(
        "年間予想受取配当額",
        f"{total_annual_div:,.0f} 円",
        delta=f"月平均: {monthly_div:,.0f} 円 / YOC: {avg_yoc:.2f}%",
    )

    # 増配シミュレーター
    with st.expander("🔮 将来の増配・受取配当シミュレーター", expanded=False):
      sim_col1, sim_col2 = st.columns(2)
      with sim_col1:
        growth_rate = st.slider(
            "想定年間増配率 (%)",
            min_value=0.0,
            max_value=15.0,
            value=3.0,
            step=0.5,
        )
      with sim_col2:
        sim_years = st.slider(
            "シミュレーション期間 (年)",
            min_value=1,
            max_value=20,
            value=5,
        )

      future_div = total_annual_div * ((1 + (growth_rate / 100)) ** sim_years)
      future_monthly = future_div / 12.0
      st.write(
          f"年 **{growth_rate}%** で増配が続いた場合、**{sim_years}年後** の年間配当予想は"
          f" **約 {future_div:,.0f} 円 / 年** （月平均 **約 {future_monthly:,.0f}"
          " 円**）になります。"
      )

    st.markdown("---")
    st.write("### 📋 保有銘柄・配当金一覧")
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

else:
  # 個別銘柄選択画面
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

  # 保有株設定サイドバー
  saved_item = st.session_state["holdings"].get(code, {})
  is_saved = code in st.session_state["holdings"]

  is_holding = st.sidebar.checkbox(
      "この銘柄を保有している",
      value=is_saved,
      key=f"chk_holding_{code}",
  )

  buy_price = 0.0
  holding_qty = 0
  annual_div = 0.0

  if is_holding:
    default_price = float(saved_item.get("buy_price", 1000.0))
    default_qty = int(saved_item.get("qty", 100))
    default_div = float(saved_item.get("annual_div", 0.0))

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
    annual_div = st.sidebar.number_input(
        "1株あたりの年間予想配当（円）",
        min_value=0.0,
        value=default_div,
        step=1.0,
        key=f"annual_div_{code}",
    )

    col_btn1, col_btn2 = st.sidebar.columns(2)
    with col_btn1:
      if st.sidebar.button("💾 設定を保存", key=f"btn_save_{code}"):
        stock_name = code_to_name.get(
            code,
            selected_stock.split(" | ")[1]
            if " | " in selected_stock
            else selected_stock,
        )
        st.session_state["holdings"][code] = {
            "name": stock_name,
            "buy_price": buy_price,
            "qty": holding_qty,
            "annual_div": annual_div,
        }
        st.sidebar.success("保存しました！")
        st.rerun()
    with col_btn2:
      if is_saved and st.sidebar.button("🗑️ 解除", key=f"btn_del_{code}"):
        del st.session_state["holdings"][code]
        st.sidebar.info("保存を解除しました。")
        st.rerun()

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

      # 保有株損益・配当パネル
      if is_holding and buy_price > 0:
        price_diff = latest_price - buy_price
        price_diff_pct = (price_diff / buy_price) * 100
        total_profit = price_diff * holding_qty

        # 自動計算配当初期設定の補助
        if annual_div == 0.0 and extra_info.get("配当利回り") != "---":
          try:
            div_pct = float(
                extra_info["配当利回り"].replace("%", "").strip()
            )
            est_div = latest_price * (div_pct / 100.0)
            annual_div = round(est_div, 1)
            st.session_state["holdings"][code]["annual_div"] = annual_div
          except Exception:
            pass

        item_annual_div = annual_div * holding_qty
        yoc = (annual_div / buy_price * 100) if buy_price > 0 else 0.0

        with st.expander("💰 保有株の損益・利回り・配当シミュレーション", expanded=True):
          p_col1, p_col2, p_col3, p_col4 = st.columns(4)
          p_col1.metric(
              label="保有株数 / 取得単価",
              value=f"{holding_qty:,} 株",
              delta=f"{buy_price:,.1f} 円",
              delta_color="off",
          )
          p_col2.metric(
              label="評価損益",
              value=f"{total_profit:+,.0f} 円",
              delta=f"{price_diff_pct:+.2f}%",
          )
          p_col3.metric(
              label="1株あたり予想配当 / YOC",
              value=f"{annual_div:,.1f} 円",
              delta=f"取得利回り: {yoc:.2f}%",
              delta_color="off",
          )
          p_col4.metric(
              label="この銘柄の年間受取配当額",
              value=f"{item_annual_div:,.0f} 円",
              delta=f"月平均: {item_annual_div / 12:,.0f} 円",
              delta_color="off",
          )

      # 一括登録・表形式編集パネル
      with st.expander(
          "📁 保有銘柄リスト（一括登録・表形式編集）", expanded=False
      ):
        tab1, tab2 = st.tabs(
            ["📝 表形式で一括編集", "📋 テキスト一括貼り付け"]
        )

        with tab1:
          st.write(
              "以下の表で直接銘柄の追加・各数値の編集・削除が行えます。「一括保存」を押して適用してください。"
          )

          editor_rows = []
          for h_code, h_info in st.session_state["holdings"].items():
            editor_rows.append({
                "銘柄コード": str(h_code).zfill(4),
                "銘柄名": h_info.get(
                    "name", code_to_name.get(h_code, "不明銘柄")
                ),
                "平均取得単価 (円)": float(h_info.get("buy_price", 0.0)),
                "保有株数 (株)": int(h_info.get("qty", 0)),
                "1株予想配当 (円)": float(h_info.get("annual_div", 0.0)),
            })

          if not editor_rows:
            editor_df = pd.DataFrame(
                columns=[
                    "銘柄コード",
                    "銘柄名",
                    "平均取得単価 (円)",
                    "保有株数 (株)",
                    "1株予想配当 (円)",
                ]
            )
          else:
            editor_df = pd.DataFrame(editor_rows)

          edited_df = st.data_editor(
              editor_df,
              num_rows="dynamic",
              column_config={
                  "銘柄コード": st.column_config.TextColumn(
                      "銘柄コード (4桁/英数字)", required=True
                  ),
                  "銘柄名": st.column_config.TextColumn(
                      "銘柄名", disabled=True
                  ),
                  "平均取得単価 (円)": st.column_config.NumberColumn(
                      "平均取得単価 (円)", min_value=0.0, step=10.0
                  ),
                  "保有株数 (株)": st.column_config.NumberColumn(
                      "保有株数 (株)", min_value=0, step=100
                  ),
                  "1株予想配当 (円)": st.column_config.NumberColumn(
                      "1株予想配当 (円)", min_value=0.0, step=1.0
                  ),
              },
              use_container_width=True,
              key="holdings_data_editor",
          )

          if st.button("💾 表の内容で一括保存", key="btn_save_bulk_table"):
            new_holdings = {}
            for _, row in edited_df.iterrows():
              c_str = str(row["銘柄コード"]).strip().upper().zfill(4)
              if c_str and len(c_str) == 4 and c_str.isalnum():
                b_price = float(row.get("平均取得単価 (円)", 0) or 0.0)
                h_q = int(row.get("保有株数 (株)", 0) or 0)
                a_div = float(row.get("1株予想配当 (円)", 0) or 0.0)
                s_name = code_to_name.get(
                    c_str, str(row.get("銘柄名") or c_str)
                )
                new_holdings[c_str] = {
                    "name": s_name,
                    "buy_price": b_price,
                    "qty": h_q,
                    "annual_div": a_div,
                }
            st.session_state["holdings"] = new_holdings
            st.success("保有銘柄リストを一括更新しました！")
            st.rerun()

        with tab2:
          st.write(
              "「銘柄コード, 平均取得単価, 保有株数, 1株予想配当」の順にテキストで貼り付けて一括登録できます。"
          )
          bulk_text = st.text_area(
              "貼り付けエリア",
              height=150,
              placeholder=(
                  "3407, 1050, 200, 36\n265A, 1009, 100, 15\n7203, 2800, 100, 90"
              ),
          )

          if st.button("📥 テキストから一括取り込み", key="btn_import_text"):
            if bulk_text.strip():
              count = 0
              lines = bulk_text.strip().split("\n")
              for line in lines:
                parts = re.split(r"[,,\s\t]+", line.strip())
                if len(parts) >= 1:
                  c_code = parts[0].strip().upper().zfill(4)
                  if len(c_code) == 4 and c_code.isalnum():
                    c_price = (
                        float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
                    )
                    c_qty = int(parts[2]) if len(parts) > 2 and parts[2] else 0
                    c_div = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                    s_name = code_to_name.get(c_code, c_code)

                    st.session_state["holdings"][c_code] = {
                        "name": s_name,
                        "buy_price": c_price,
                        "qty": c_qty,
                        "annual_div": c_div,
                    }
                    count += 1
              st.success(f"{count} 件の銘柄を一括追加・更新しました！")
              st.rerun()

      # 市況情報表示
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

      # テクニカル指標の計算
      df["SMA_S"] = df["Close"].rolling(window=sma_short).mean()
      df["SMA_L"] = df["Close"].rolling(window=sma_long).mean()

      if show_bollinger:
        df["BB_Middle"] = df["Close"].rolling(window=20).mean()
        df["BB_Std"] = df["Close"].rolling(window=20).std()
        df["BB_Upper2"] = df["BB_Middle"] + (df["BB_Std"] * 2)
        df["BB_Lower2"] = df["BB_Middle"] - (df["BB_Std"] * 2)

      rows = 2
      row_heights = [0.7, 0.3]
      if show_rsi and show_macd:
        rows = 4
        row_heights = [0.4, 0.2, 0.2, 0.2]
      elif show_rsi or show_macd:
        rows = 3
        row_heights = [0.5, 0.25, 0.25]

      fig = make_subplots(
          rows=rows,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.03,
          row_heights=row_heights,
      )

      # ボリンジャーバンド描画（ロウソク足の背面）
      if show_bollinger:
        fig.add_trace(
            go.Scatter(
                x=df["DateStr"],
                y=df["BB_Upper2"],
                mode="lines",
                name="+2σ",
                line=dict(color="rgba(100, 200, 255, 0.4)", width=1),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["DateStr"],
                y=df["BB_Lower2"],
                mode="lines",
                name="-2σ",
                line=dict(color="rgba(100, 200, 255, 0.4)", width=1),
                fill="tonexty",
                fillcolor="rgba(100, 200, 255, 0.05)",
            ),
            row=1,
            col=1,
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

      curr_row = 3
      if show_rsi:
        df["RSI"] = calculate_rsi(df["Close"])
        fig.add_trace(
            go.Scatter(
                x=df["DateStr"],
                y=df["RSI"],
                mode="lines",
                name="RSI",
                line=dict(color="#E040FB", width=1.5),
            ),
            row=curr_row,
            col=1,
        )
        fig.add_hline(
            y=70, line_dash="dash", line_color="red", row=curr_row, col=1
        )
        fig.add_hline(
            y=30, line_dash="dash", line_color="green", row=curr_row, col=1
        )
        curr_row += 1

      if show_macd:
        macd, signal, hist = calculate_macd(df["Close"])
        fig.add_trace(
            go.Scatter(
                x=df["DateStr"],
                y=macd,
                mode="lines",
                name="MACD",
                line=dict(color="#00E676", width=1.5),
            ),
            row=curr_row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["DateStr"],
                y=signal,
                mode="lines",
                name="Signal",
                line=dict(color="#FF9100", width=1.5),
            ),
            row=curr_row,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=df["DateStr"],
                y=hist,
                name="Hist",
                marker_color="gray",
            ),
            row=curr_row,
            col=1,
        )

      total_len = len(df)
      display_count = min(60, total_len)
      start_idx = total_len - display_count
      end_idx = total_len - 1

      # チャートパン（移動）動作の設定切替
      drag_mode = "pan" if enable_pan else False

      fig.update_layout(
          template="plotly_dark",
          xaxis_rangeslider_visible=False,
          margin=dict(l=10, r=10, t=10, b=10),
          height=650 if (show_rsi or show_macd) else 500,
          showlegend=False,
          dragmode=drag_mode,
      )
      fig.update_xaxes(type="category", range=[start_idx, end_idx])

      plotly_config = {
          "scrollZoom": enable_pan,
          "displayModeBar": True,
      }
      st.plotly_chart(
          fig, use_container_width=True, config=plotly_config
      )
