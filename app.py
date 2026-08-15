import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="株価分析アプリ", layout="wide", initial_sidebar_state="collapsed")

st.title("📈 株価分析アプリ")

# 主要銘柄リスト
STOCK_DICT = {
    "直接入力（コード指定）": "CUSTOM",
    "トヨタ自動車 (7203)": "TSE:7203",
    "ソニーグループ (6758)": "TSE:6758",
    "ソフトバンクG (9984)": "TSE:9984",
    "三菱UFJ FG (8306)": "TSE:8306",
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

# 銘柄選択（プルダウン）
selected_option = st.selectbox("銘柄を選択または直接入力", list(STOCK_DICT.keys()))

if STOCK_DICT[selected_option] == "CUSTOM":
    user_input = st.text_input("銘柄コードを入力（例: 7203, 9984）", "7203")
    raw_code = user_input.strip().upper()
    if raw_code.isdigit():
        symbol = f"TSE:{raw_code}"
    elif raw_code.startswith("TSE:"):
        symbol = raw_code
    else:
        symbol = f"TSE:{raw_code}"
else:
    symbol = STOCK_DICT[selected_option]

clean_symbol = symbol.replace(":", "_")

# TradingView チャート埋め込み（ポップアップ抑止設定済み）
tv_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; background-color: #0e1117; }}
        .tradingview-widget-container {{ width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <div class="tradingview-widget-container">
      <div id="tv_chart_{clean_symbol}" style="width:100%;height:500px;"></div>
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
        "allow_symbol_change": false,
        "hide_side_toolbar": false,
        "container_id": "tv_chart_{clean_symbol}"
      }});
      </script>
    </div>
</body>
</html>
"""

components.html(tv_html, height=510)
