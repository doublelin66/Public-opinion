import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime

# ================= 1. 基礎設定 =================
st.set_page_config(
    page_title="Clarity - 輿情分析儀表板",
    page_icon="⚡",
    layout="wide"
)

# ================= 2. 安全讀取金鑰 =================
# 這是最安全的寫法，金鑰藏在 Streamlit 的保險箱裡，GitHub 上看不到
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ 找不到金鑰！請確認 Streamlit Secrets 設定。")
    st.stop()

genai.configure(api_key=API_KEY)

# ================= 3. 核心功能：使用 Gemini 2.5 + 爬蟲 =================
@st.cache_data(ttl=3600)  # 設定快取 1 小時，避免浪費額度
def run_analysis():
    # --- 🚀 關鍵修正：使用您帳號檢測到的最新模型 ---
    # 根據您的診斷報告，我們鎖定使用 gemini-2.5-flash
    model_name = 'gemini-2.5-flash'
    
    try:
        model = genai.GenerativeModel(model_name)
    except:
        # 萬一 2.5 臨時有問題，自動切換回通用版
        model = genai.GenerativeModel('gemini-pro')
    # ----------------------------------------------
    
    # B. 抓取 Google News (台灣)
    rss_url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    try:
        # 偽裝成瀏覽器，避免被 Google News 擋下
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        # 只取前 12 則最新新聞來分析
        raw_data = [{"title": entry.title, "pubDate": entry.published} for entry in feed.entries[:12]]
    except Exception as e:
        st.error(f"新聞抓取失敗: {e}")
        return []

    if not raw_data:
        return []

    # C. AI 分析 (Prompt)
    prompt = f"""
    你是一個專業的輿情分析師。請閱讀以下台灣熱門新聞標題，並產出 JSON 格式的趨勢報告。
    
    原始新聞資料：
    {json.dumps(raw_data, ensure_ascii=False)}
    
    請嚴格遵守以下 JSON 輸出格式 (Array)，直接輸出 JSON 不要加 markdown 標記：
    [
      {{
        "id": 1,
        "keyword": "新聞關鍵字",
        "category": "分類(英文,如Tech/Politics/Life)",
        "score": 88,
        "summary": "30字內繁體中文短評，犀利且直指重點。",
        "hashtags": ["#tag1", "#tag2"]
      }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        # 清洗資料：移除可能出現的 ```json ... ``` 符號
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        # 如果出錯，會在畫面上顯示原因，方便除錯
        st.warning(f"AI 分析失敗 (使用模型 {model_name}): {e}")
        return []

# ================= 4. 介面顯示 (UI) =================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ Clarity 輿情儀表板")
    st.caption(f"Powered by Gemini 2.5 • 更新時間: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 重新抓取 (Refresh)"):
        st.cache_data.clear() # 清除快取，強制重跑
        st.rerun()

st.divider()

# 執行分析
with st.spinner('🤖 AI (Gemini 2.5) 正在閱讀新聞並分析中...'):
    trends = run_analysis()

# 如果有資料，開始繪製畫面
if trends:
    # 自訂 CSS 樣式 (卡片與標籤效果)
    st.markdown("""
    <style>
        .trend-card {background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #FF7F32;}
        .score-tag {background-color: #FFF3E0; color: #FF7F32; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em;}
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("🔥 熱門焦點")
        # 顯示前 4 則重點新聞
        for item in trends[:4]:
            with st.container():
                st.markdown(f"""
                <div class="trend-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <h3 style="margin:0; color:#333; font-size:1.4em;">{item['keyword']}</h3>
                        <span class="score-tag">🔥 {item['score']}</span>
                    </div>
                    <div style="color:#666; font-size:0.9em; margin-bottom:8px;">
                        <span style="background:#f0f2f6; padding:2px 8px; border-radius:4px;">{item['category']}</span>
                    </div>
                    <p style="color:#444; font-size:1.1em; line-height:1.5;">{item['summary']}</p>
                    <div style="margin-top:12px; font-size:0.9em; color:#888;">
                        {' '.join([f'#{tag}' for tag in item.get('hashtags', [])]).replace('##', '#')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.subheader("📈 關鍵字熱度")
        df = pd.DataFrame(trends)
        if not df.empty:
            st.bar_chart(df.set_index('keyword')['score'], color="#FF7F32")

    with right_col:
        st.subheader("🏆 話題排行榜")
        # 顯示簡易排行榜
        for i, item in enumerate(trends):
            st.markdown(f"""
            <div style="background:white; padding:15px; margin-bottom:10px; border-radius:10px; display:flex; align-items:center; border:1px solid #eee;">
                <div style="font-weight:bold; color:#FF7F32; width:30px; font-size:1.2em; text-align:center;">{i+1}</div>
                <div style="flex-grow:1; padding-left:10px;">
                    <div style="font-weight:bold; font-size:1em; color:#333;">{item['keyword']}</div>
                    <div style="font-size:0.8em; color:#999;">{item['category']}</div>
                </div>
                <div style="font-weight:bold; color:#FF7F32;">{item['score']}</div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.info("尚無資料，請確認 API Key 設定是否正確。")
