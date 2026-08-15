import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed")

st.title("📈 株価分析アプリ")

# 主要銘柄リスト（銘柄名から選択可能）
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
    "信越化学工業 (4063)": "4063.T",
    "三井住友FG (8316)": "8316.T",
    "伊藤忠商事 (8001)": "8001.T",
    "三菱商事 (8058)": "8058.T",
}

# 銘柄選択（プルダウン）
selected_option = st.selectbox("銘柄を選択または直接入力", list(STOCK_DICT.keys()))

if STOCK_DICT[selected_option] == "CUSTOM":
    user_input = st.text_input("銘柄コードを入力（例: 7203）", "7203")
else:
    user_input = STOCK_DICT[selected_option]

# 入力値の整形（数字4桁の場合は自動で末尾に .T を付与）
raw_code = user_input.strip().upper()
if raw_code.isdigit() and len(raw_code) == 4:
    ticker_symbol = f"{raw_code}.T"
else:
    ticker_symbol = raw_code

# データ取得処理
if ticker_symbol:
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="6m")
        
        if df.empty:
            st.error("株価データが取得できませんでした。銘柄コードを確認してください。")
        else:
            latest_price = df['Close'].iloc[-1]
            st.metric(label=f"対象銘柄: {ticker_symbol} (最新終値)", value=f"{latest_price:,.1f} 円")
            st.line_chart(df['Close'])
    except Exception as e:
        st.error(f"データ取得エラーが発生しました: {e}")
