import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed")

st.title("📈 株価分析アプリ")

# 主要銘柄リスト
STOCK_DICT = {
    "トヨタ自動車 (7203)": "TSE:7203",
    "ソニーグループ (6758)": "TSE:6758",
    "三菱UFJ FG (8306)": "TSE:8306",
    "ソフトバンクG (9984)": "TSE:9984",
    "キーエンス (6861)": "TSE:6861",
    "東京エレクトロン (8035)": "TSE:8035",
    "レーザーテック (6920)": "TSE:6920",
    "ファーストリテイリング (9983)": "TSE:9983",
    "NTT (9432)": "TSE:9432",
    "任天堂 (7974)": "TSE:7974",
    "日立製作所 (6501)": "TSE:6501",
    "三井住友FG (8316)": "TSE:8316",
    "三菱商事 (8058)": "TSE:8058",
}

# 銘柄選択
selected_option = st.selectbox("銘柄を選択", list(STOCK_DICT.keys()))
symbol = STOCK_DICT[selected_option]

# TradingView チャート埋め込み
tv_html = f"""
<div class="tradingview-widget-container" style="height:100%;width:100%">
  <div id="tradingview_chart" style="height:500px;width:100%"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "{symbol}",
    "interval": "D",
    "timezone": "Asia/Tokyo",
    "theme": "dark",
    "style": "1",
    "locale": "ja",
    "enable_publishing": false,
    "allow_symbol_change": true,
    "container_id": "tradingview_chart"
  }});
  </script>
</div>
"""

components.html(tv_html, height=520)
