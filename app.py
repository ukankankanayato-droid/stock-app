import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed")

st.title("📈 株価分析アプリ")

# 主要銘柄リスト
STOCK_DICT = {
    "直接入力（コード指定）": "CUSTOM",
    "トヨタ自動車 (7203)": "7203.T",
    "ソニーグループ (6758)": "6758.T",
    "三菱UFJ FG (8306)": "8306.T",
    "ソフトバンクG (9984)": "9984.T",
    "キーエンス (6861)": "6861.T",
    "東京エレクトロン (8035)": "8035.T",
    "レーザーテック (6920)": "6920.T",
    "ファーストリテイリング (9983)": "9983.T",
    "NTT (9432)": "9432.T",
    "任天堂 (7974)": "7974.T",
    "日立製作所 (6501)": "6501.T",
    "三井住友FG (8316)": "8316.T",
    "三菱商事 (8058)": "8058.T",
}

selected_option = st.selectbox("銘柄を選択または直接入力", list(STOCK_DICT.keys()))

if STOCK_DICT[selected_option] == "CUSTOM":
    user_input = st.text_input("銘柄コードを入力（例: 7203）", "7203")
else:
    user_input = STOCK_DICT[selected_option]

# 入力処理（数字4桁なら自動で .T 付与）
raw_code = user_input.strip().upper()
ticker_symbol = f"{raw_code}.T" if raw_code.isdigit() and len(raw_code) == 4 else raw_code

if ticker_symbol:
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="6m")

        if df.empty:
            st.error("株価データが取得できませんでした。銘柄コードを確認してください。")
        else:
            # 移動平均線（5日・25日）の計算
            df['SMA5'] = df['Close'].rolling(window=5).mean()
            df['SMA25'] = df['Close'].rolling(window=25).mean()

            latest_price = df['Close'].iloc[-1]
            st.metric(label=f"対象銘柄: {ticker_symbol} (最新終値)", value=f"{latest_price:,.1f} 円")

            # ローソク足と出来高の2段チャート
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3]
            )

            # ローソク足
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name="株価"
            ), row=1, col=1)

            # 移動平均線
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], mode='lines', name='5日線', line=dict(color='orange', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], mode='lines', name='25日線', line=dict(color='#00BFFF', width=1)), row=1, col=1)

            # 出来高
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="出来高", marker_color='gray'), row=2, col=1)

            # ダークモード・レイアウト設定
            fig.update_layout(
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=10, b=10),
                height=500,
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"データ取得エラーが発生しました: {e}")
