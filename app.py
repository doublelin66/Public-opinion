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
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception as e:
    st.error("⚠️ 找不到金鑰！請確認您已在 Streamlit Cloud 的 Advanced Settings -> Secrets 中設定了 'GOOGLE_API_KEY'。")
    st.stop()

genai.configure(api_key=API_KEY)

# ================= 3. 核心功能：爬蟲 + AI 分析 =================
@st.cache_data(ttl=3600)
def run_analysis():
    # --- 🛡️ 模型保險機制 (關鍵修正) ---
    # 嘗試使用最新的 Flash，如果失敗則自動切換回 Pro
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # 測試一下模型是否活著
        model.generate_content("test")
        print("✅ 使用模型: Gemini 1.5 Flash")
    except:
        print("⚠️ Flash 模型載入失敗，切換至 gemini-pro")
        model = genai.GenerativeModel('gemini-pro')
    # ----------------------------------
    
    # B. 抓取 Google News
    rss_url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        raw_data = [{"title": entry.title, "pubDate": entry.published} for entry in feed.entries[:12]]
    except Exception as e:
        st.error(f"新聞抓取失敗: {e}")
        return []

    if not raw_data:
        return []

    # C. AI 分析
    prompt = f"""
    你是一個專業的輿情分析師。請閱讀以下台灣熱門新聞標題，並產出 JSON 格式的趨勢報告。
    原始新聞資料：
    {json.dumps(raw_data, ensure_ascii=False)}
    
    請嚴格遵守以下 JSON 輸出格式 (Array)，不要加 markdown：
    [
      {{
        "id": 1,
        "keyword": "新聞關鍵字",
        "category": "分類(英文)",
        "score": 88,
        "summary": "30字內繁體中文短評",
        "hashtags": ["#tag1", "#tag2"]
      }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        # 有時候 AI 會因為內容敏感拒絕回答，這裡做個保護
        if not cleaned_text: 
            return []
        return json.loads(cleaned_text)
    except Exception as e:
        st.warning(f"AI 分析暫時無法使用 (可能因額度或模型問題): {e}")
        return []

# ================= 4. 介面顯示 =================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ Clarity 輿情儀表板")
    st.caption(f"即時追蹤台灣熱門話題 • Powered by Gemini AI • 更新時間: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 重新抓取 (Refresh)"):
        st.cache_data.clear()
        st.rerun()

st.divider()

with st.spinner('🤖 AI 正在閱讀新聞並分析趨勢中... (首次執行約需 10-15 秒)'):
    trends = run_analysis()

if trends:
    st.markdown("""
    <style>
        .trend-card {background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #FF7F32;}
        .score-tag {background-color: #FFF3E0; color: #FF7F32; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em;}
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("🔥 熱門焦點")
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
    st.info("尚無資料，請稍後再試。")
