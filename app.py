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

# ================= 2. 安全讀取金鑰 (核心保護區) =================
# 這段程式碼會去讀取 Streamlit Cloud 的 "Secrets" (保險箱)
# 如果程式碼被公開在 GitHub，別人也只會看到這行指令，看不到金鑰本人。
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception as e:
    # 如果在本地執行找不到 secrets.toml，或是在雲端忘記設定，會顯示這行警告
    st.error("⚠️ 找不到金鑰！請確認您已在 Streamlit Cloud 的 Advanced Settings -> Secrets 中設定了 'GOOGLE_API_KEY'。")
    st.stop() # 停止執行，避免報錯

# 設定 Google AI
genai.configure(api_key=API_KEY)

# ================= 3. 核心功能：爬蟲 + AI 分析 =================
# 使用 cache_data 避免每次重新整理都消耗 AI 額度 (設定快取 1 小時)
@st.cache_data(ttl=3600)
def run_analysis():
    # A. 選擇模型 (使用 Flash 版本，速度快且免費額度高)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # B. 抓取 Google News (台灣焦點)
    rss_url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    try:
        # 偽裝成瀏覽器，避免被擋
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        # 只取前 12 則最新新聞
        raw_data = [{"title": entry.title, "pubDate": entry.published} for entry in feed.entries[:12]]
    except Exception as e:
        st.error(f"新聞抓取失敗: {e}")
        return []

    if not raw_data:
        return []

    # C. 請 AI 進行分析
    prompt = f"""
    你是一個專業的輿情分析師。請閱讀以下台灣熱門新聞標題，並產出 JSON 格式的趨勢報告。
    
    原始新聞資料：
    {json.dumps(raw_data, ensure_ascii=False)}
    
    請嚴格遵守以下 JSON 輸出格式 (Array)：
    [
      {{
        "id": 1,
        "keyword": "新聞關鍵字 (例如：台積電)",
        "category": "分類 (英文，例如：Tech, Politics, Finance)",
        "score": 88 (熱度分數 60-100),
        "summary": "30字內繁體中文短評，犀利且直指重點。",
        "hashtags": ["#標籤1", "#標籤2"]
      }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        # 清洗資料，確保沒有 Markdown 符號
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.error(f"AI 分析失敗: {e}")
        return []

# ================= 4. 介面顯示 (UI) =================

# 標題區
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ Clarity 輿情儀表板")
    st.caption(f"即時追蹤台灣熱門話題 • Powered by Gemini AI • 更新時間: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 重新抓取分析 (Refresh)"):
        st.cache_data.clear() # 清除快取，強制重跑
        st.rerun()

st.divider()

# 執行分析
with st.spinner('🤖 AI 正在閱讀新聞並分析趨勢中... (首次執行約需 10 秒)'):
    trends = run_analysis()

# 顯示內容
if trends:
    # 自訂 CSS 樣式
    st.markdown("""
    <style>
        .stContainer {border-radius: 15px; padding: 10px;}
        .trend-card {background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #FF7F32;}
        .score-tag {background-color: #FFF3E0; color: #FF7F32; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em;}
    </style>
    """, unsafe_allow_html=True)

    # 版面配置：左 2 (重點) 右 1 (列表)
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("🔥 熱門焦點")
        for item in trends[:4]: # 顯示前 4 則
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
