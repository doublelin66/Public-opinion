import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime

# ================= 1. 基礎設定 =================
st.set_page_config(
    page_title="Clarity - 深度輿情儀表板",
    page_icon="⚡",
    layout="wide"
)

# ================= 2. 安全讀取金鑰 =================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ 找不到金鑰！請確認 Streamlit Secrets 設定。")
    st.stop()

genai.configure(api_key=API_KEY)

# ================= 3. 核心功能：多重來源爬蟲 + AI 分析 =================
@st.cache_data(ttl=3600)
def run_analysis():
    # --- A. 模型設定 (使用 Gemini 2.5) ---
    # 優先嘗試 2.5 Flash，如果失敗則退回 Pro
    model_name = 'gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-pro')

    # --- B. 定義多個新聞來源 (擴充資訊量) ---
    rss_sources = {
        "💰 財經": "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0FBUWlHZ0pKVERNU0FBUW?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
        "🤖 科技": "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGRqTVhZU0FBUWlHZ0pKVERNU0FBUW?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
        "🔥 焦點": "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    }
    
    all_raw_data = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 迴圈抓取每一個來源
    for category_name, url in rss_sources.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
            
            # 每個分類抓前 10 則
            for entry in feed.entries[:10]:
                all_raw_data.append({
                    "source": category_name,
                    "title": entry.title, 
                    "pubDate": entry.published
                })
        except Exception as e:
            continue

    if not all_raw_data:
        return []

    # --- C. AI 分析 ---
    # 先把 JSON 轉成字串，避免放在 f-string 裡容易出錯
    news_json = json.dumps(all_raw_data, ensure_ascii=False)

    # Prompt 指令
    prompt = f"""
    你是一個專業的股市輿情分析師。請閱讀以下 30 則台灣新聞標題。
    請進行深度分析，並產出 JSON 格式的報告。

    原始新聞資料：
    {news_json}
    
    任務要求：
    1. 去除重複新聞。
    2. 只保留對「投資市場、產業趨勢」有意義的新聞。
    3. 依照「重要性」排序。

    請嚴格遵守以下 JSON 輸出格式 (Array)，直接輸出 JSON 不要加 markdown：
    [
      {{
        "id": 1,
        "keyword": "核心關鍵字",
        "category": "分類 (例如: Tech, Finance)",
        "score": 90,
        "summary": "50字內繁體中文深度短評。",
        "hashtags": ["#tag1", "#tag2"]
      }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.warning(f"AI 分析失敗: {e}")
        return []

# ================= 4. 介面顯示 (UI) =================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ Clarity 深度輿情儀表板")
    st.caption(f"財經 • 科技 • 焦點 | Powered by Gemini 2.5 | 更新: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 全面更新"):
        st.cache_data.clear()
        st.rerun()

st.divider()

with st.spinner('🤖 AI 正在閱讀 30+ 則新聞並分析中... (需時約 15 秒)'):
    trends = run_analysis()

if trends:
    # CSS 美化
    st.markdown("""
    <style>
        .trend-card {background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #FF7F32;}
        .score-tag {background-color: #FFF3E0; color: #FF7F32; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em;}
        .category-tag {background-color: #f0f2f6; color: #555; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;}
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("🔥 市場熱點解析")
        for item in trends[:5]:
            with st.container():
                st.markdown(f"""
                <div class="trend-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <h3 style="margin:0; color:#333; font-size:1.4em;">{item['keyword']}</h3>
                        <span class="score-tag">🔥 {item['score']}</span>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span class="category-tag">{item['category']}</span>
                    </div>
                    <p style="color:#444; font-size:1.1em; line-height:1.5;">{item['summary']}</p>
                    <div style="margin-top:12px; font-size:0.9em; color:#888;">
                        {' '.join([f'#{tag}' for tag in item.get('hashtags', [])]).replace('##', '#')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.subheader("📈 趨勢權重")
        df = pd.DataFrame(trends)
        if not df.empty:
            st.bar_chart(df.set_index('keyword')['score'], color="#FF7F32")

    with right_col:
        st.subheader("🏆 重要性排行")
        for i, item in enumerate(trends):
            st.markdown(f"""
            <div style="background:white; padding:12px; margin-bottom:10px; border-radius:10px; display:flex; align-items:center; border:1px solid #eee;">
                <div style="font-weight:bold; color:#FF7F32; width:30px; font-size:1.2em; text-align:center;">{i+1}</div>
                <div style="flex-grow:1; padding-left:10px;">
                    <div style="font-weight:bold; font-size:0.95em; color:#333;">{item['keyword']}</div>
                    <div style="font-size:0.8em; color:#999;">{item['category']}</div>
                </div>
                <div style="font-weight:bold; color:#FF7F32;">{item['score']}</div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.info("尚無資料，請確認 API Key 設定是否正確。")
