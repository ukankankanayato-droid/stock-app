import io
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed"
)

st.title("📈 株価分析アプリ")

# 主要銘柄リスト
STOCK_DICT = {
    "直接入力（コード指定）": "CUSTOM",
    "ソニーグループ (6758)": "6758",
    "トヨタ自動車 (7203)": "7203",
    "ソフトバンクG (9984)": "9984",
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

selected_option = st.selectbox("銘柄を選択または直接入力", list(STOCK_DICT.keys()))

if STOCK_DICT[selected_option] == "CUSTOM":
  user_input = st.text_input("銘柄コードを入力（例: 7203, 6758）", "6758")
  code = user_input.strip()
else:
  code = STOCK_DICT[selected_option]

if code and code.isdigit():
  url = f"https://stooq.com/q/d/l/?s={code}.jp&i=d"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  try:
    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code == 200:
      df = pd.read_csv(io.StringIO(response.text))

      if (
          df.empty
          or "Date" not in df.columns
          or "Close" not in df.columns
          or len(df) < 5
      ):
        st.error(
            "株価データが取得できませんでした。銘柄コードを確認してください。"
        )
      else:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        df = df.tail(120)

        # 移動平均線（5日・25日）
        df["SMA5"] = df["Close"].rolling(window=5).mean()
        df["SMA25"] = df["Close"].rolling(window=25).mean()

        latest_price = df["Close"].iloc[-1]
        st.metric(
            label=f"銘柄コード: {code} (最新終値)",
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
                x=df["Date"],
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
                x=df["Date"],
                y=df["SMA5"],
                mode="lines",
                name="5日線",
                line=dict(color="orange", width=1),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["SMA25"],
                mode="lines",
                name="25日線",
                line=dict(color="#00BFFF", width=1),
            ),
            row=1,
            col=1,
        )

        # 出来高
        fig.add_trace(
            go.Bar(
                x=df["Date"],
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

        st.plotly_chart(fig, use_container_width=True)
    else:
      st.error(f"データ取得エラー (ステータスコード: {response.status_code})")

  except Exception as e:
    st.error(f"通信エラーが発生しました: {e}")
