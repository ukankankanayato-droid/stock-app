import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# ---------------------------------------------------------
# 1. ページ設定（黒基調・ダークモード）
# ---------------------------------------------------------
st.set_page_config(
    page_title="株価テクニカル解析ダッシュボード",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# カスタムCSS（ダークモードデザイン）
st.markdown("""
<style>
    .stApp {
        background-color: #131722;
        color: #d1d4dc;
    }
    .stTextInput > div > div > input {
        background-color: #1e222d;
        color: #ffffff;
        border: 1px solid #363c4e;
    }
    .ai-card {
        background-color: #1e222d;
        border-left: 4px solid #2962ff;
        padding: 16px;
        border-radius: 6px;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    .metric-box {
        background-color: #1e222d;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #2a2e39;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 株価テクニカル解析ダッシュボード")

# ---------------------------------------------------------
# 2. 検索バー（銘柄入力）
# ---------------------------------------------------------
col_search, _ = st.columns([1, 2])
with col_search:
    symbol = st.text_input(
        "銘柄コードを入力 (例: 日本株は 7203.T, 米国株は AAPL, NVDA)", 
        value="7203.T"
    ).strip().upper()

if symbol:
    st.subheader(f"🔍 解析対象: {symbol}")

    # 左右の2列レイアウト（左: チャート、右: テクニカル分析＆メモ）
    col_left, col_right = st.columns([1.2, 1])

    # ---------------------------------------------------------
    # 3. TradingView チャート埋め込み (左側)
    # ---------------------------------------------------------
    with col_left:
        st.markdown("### 📊 TradingView チャート")
        # TradingView用のシンボルフォーマット調整 (例: 7203.T -> TSE:7203)
        tv_symbol = f"TSE:{symbol.replace('.T', '')}" if symbol.endswith('.T') else symbol
        
        tv_html = f"""
        <div class="tradingview-widget-container" style="height:550px;width:100%">
          <div id="tradingview_chart" style="height:550px;width:100%"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "{tv_symbol}",
            "interval": "D",
            "timezone": "Asia/Tokyo",
            "theme": "dark",
            "style": "1",
            "locale": "ja",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "allow_symbol_change": true,
            "container_id": "tradingview_chart"
          }});
          </script>
        </div>
        """
        components.html(tv_html, height=560)

    # ---------------------------------------------------------
    # 4. テクニカル計算 & AIアドバイス & メモ (右側)
    # ---------------------------------------------------------
    with col_right:
        try:
            # yfinanceで株価取得 (APIキー不要・無料)
            df = yf.download(symbol, period="6m", interval="1d", progress=False)

            if not df.empty and len(df) > 30:
                # pandas MultiIndex対策
                close = df['Close'][symbol] if isinstance(df.columns, pd.MultiIndex) else df['Close']

                # --- RSI(14) 計算 ---
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                latest_rsi = float(rsi_series.iloc[-1])

                # --- MACD 計算 (12, 26, 9) ---
                exp12 = close.ewm(span=12, adjust=False).mean()
                exp26 = close.ewm(span=26, adjust=False).mean()
                macd_series = exp12 - exp26
                signal_series = macd_series.ewm(span=9, adjust=False).mean()
                
                latest_macd = float(macd_series.iloc[-1])
                latest_signal = float(signal_series.iloc[-1])
                macd_diff = latest_macd - latest_signal
                prev_macd_diff = float(macd_series.iloc[-2]) - float(signal_series.iloc[-2])

                # --- 判定ロジック ---
                if latest_rsi >= 70:
                    rsi_label = "買われすぎ (高値警戒)"
                elif latest_rsi <= 30:
                    rsi_label = "売られすぎ (底値警戒)"
                else:
                    rsi_label = "中立"

                if macd_diff > 0 and prev_macd_diff <= 0:
                    macd_label = "🚀 ゴールデンクロス発生"
                elif macd_diff < 0 and prev_macd_diff >= 0:
                    macd_label = "⚠️ デッドクロス発生"
                elif macd_diff > 0:
                    macd_label = "📈 上昇トレンド継続"
                else:
                    macd_label = "📉 下降トレンド継続"

                # 指標カード表示
                st.markdown("### ⚡ テクニカル指標カード")
                m1, m2 = st.columns(2)
                with m1:
                    st.metric(label="RSI (14)", value=f"{latest_rsi:.1f}", delta=rsi_label)
                with m2:
                    st.metric(label="MACD", value=f"{latest_macd:.2f}", delta=f"Signal: {latest_signal:.2f}")

                st.caption(f"MACD状態: **{macd_label}**")

                # --- 5. 総合AIアドバイスエリア ---
                st.markdown("### 🤖 総合AIアドバイス")
                
                advice = ""
                if latest_rsi >= 70 and macd_diff < 0:
                    advice = "過熱感が高く、短期的には下落転換の兆候が見られます。利益確定や押し目買い待ちを検討してください。"
                elif latest_rsi <= 30 and macd_diff > 0:
                    advice = "売られすぎ水準からの反発シグナルが出ています。打診買い（お試し購入）の好機となる可能性があります。"
                elif macd_diff > 0 and prev_macd_diff <= 0:
                    advice = "MACDがゴールデンクロスを形成しました。買いの勢いが強まっています。"
                elif macd_diff < 0 and prev_macd_diff >= 0:
                    advice = "MACDがデッドクロスを形成しました。下降リスクに注意し、損切りルールを確認してください。"
                elif latest_rsi > 50 and macd_diff > 0:
                    advice = "上昇トレンドが順調に継続しています。明確な売りサインが出るまでは保有継続が基本です。"
                else:
                    advice = "現在はトレンドが拮抗しています。次のブレイクアウトやクロスが発生するまで様子見を推奨します。"

                st.markdown(f"""
                <div class="ai-card">
                    <h4 style="margin:0 0 8px 0; color:#2962ff;">【自動解析レポート】</h4>
                    <p style="margin:0; font-size:14px; line-height:1.6;">{advice}</p>
                </div>
                """, unsafe_allow_html=True)

            else:
                st.warning("株価データが取得できませんでした。銘柄コードを確認してください。")

        except Exception as e:
            st.error(f"データ取得エラー: {e}")

        # --- 6. 自分用のメモ欄 ---
        st.markdown("### 📝 銘柄メモ")
        
        if "memos" not in st.session_state:
            st.session_state.memos = {}

        current_memo = st.session_state.memos.get(symbol, "")
        
        memo_text = st.text_area(
            label=f"{symbol} の分析メモ",
            value=current_memo,
            height=100,
            placeholder="例: RSI 30割れで100株購入。次回決算日は◯月◯日。"
        )

        if st.button("メモを保存"):
            st.session_state.memos[symbol] = memo_text
            st.success("メモを保存しました！")
