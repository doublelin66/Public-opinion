import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime
import urllib.parse

# ================= 1. 基礎設定 =================
st.set_page_config(
    page_title="🇹🇼臺灣熱門討論",
    page_icon="🔥",
    layout="wide"
)

# ================= 2. 安全讀取金鑰 =================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ 找不到金鑰！請確認 Streamlit Secrets 設定。")
    st.stop()

genai.configure(api_key=API_KEY)

# ================= 3. 核心功能：強固型 AI 分析 =================
@st.cache_data(ttl=1800)
def run_analysis():
    # --- A. 模型與安全設定 (關鍵修正) ---
    # 1. 解除安全限制，避免新聞因為政治/社會議題被過濾
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    # 2. 強制輸出 JSON 格式 (這是 1.5/2.5 模型的新功能，大幅降低格式錯誤)
    generation_config = {
        "temperature": 1,
        "response_mime_type": "application/json"
    }

    model_name = 'gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(model_name, safety_settings=safety_settings, generation_config=generation_config)
    except:
        # 如果 2.5 連線失敗，回退到 Pro (不使用 JSON Mode 以免舊版不支援)
        model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)

    # --- B. 定義來源 ---
    rss_sources = {
        "🔥 搜尋熱榜": "https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW",
        "🍿 娛樂": "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNREpxYW5RU0FBUWlHZ0pKVERNU0FBUW?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
        "📰 綜合": "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    }
    
    all_raw_data = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for category_name, url in rss_sources.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
            
            limit = 20 if "搜尋" in category_name else 10
            
            for entry in feed.entries[:limit]:
                traffic = "N/A"
                if hasattr(entry, 'ht_approx_traffic'):
                    traffic = entry.ht_approx_traffic
                
                all_raw_data.append({
                    "source": category_name,
                    "title": entry.title,
                    "traffic": traffic,
                    "snippet": entry.summary if hasattr(entry, 'summary') else ""
                })
        except Exception as e:
            continue

    if not all_raw_data:
        return []

    # --- C. AI 分析 ---
    news_json = json.dumps(all_raw_data, ensure_ascii=False)

    prompt = f"""
    你是一個台灣社群趨勢觀察家。請分析以下資料並整理出 **15-20 個** 台灣現在最熱門的討論話題。

    原始資料：
    {news_json}
    
    要求：
    1. 主題要多元 (政治/娛樂/運動/生活)。
    2. 有流量數據 (如 "50,000+") 分數給高。
    3. 繁體中文摘要。
    
    請直接回傳 JSON Array：
    [
      {{
        "id": 1,
        "keyword": "話題關鍵字",
        "category": "分類 (Entertainment, Sports, Politics, Tech, Life)",
        "score": 95,
        "volume_label": "討論量級 (如: 5萬+ 搜尋)",
        "summary": "簡短說明。",
        "hashtags": ["#tag1"]
      }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        
        # 即使有 JSON Mode，還是做一下字串清理比較保險
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        
        # 檢查是否為空 (AI 拒絕回答時會發生)
        if not cleaned_text:
            st.warning("AI 回傳空白內容，可能是觸發安全機制，請稍後重試。")
            return []
            
        return json.loads(cleaned_text)
    except Exception as e:
        # 印出錯誤與原始文字，方便除錯
        st.error(f"AI 分析失敗: {e}")
        # 如果想看 AI 到底回了什麼鬼東西，可以把下面這行取消註解
        # st.text(response.text if 'response' in locals() else "No Response")
        return []

# ================= 4. 介面顯示 (UI) =================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🇹🇼臺灣熱門討論")
    st.caption(f"點擊卡片可查看相關新聞 | 更新: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 刷新熱榜"):
        st.cache_data.clear()
        st.rerun()

st.divider()

with st.spinner('🔍 正在挖掘全台熱搜與社群話題...'):
    trends = run_analysis()

if trends:
    st.markdown("""
    <style>
        a.trend-link { text-decoration: none !important; color: inherit !important; display: block; }
        .trend-row { background-color: white; padding: 15px; border-radius: 10px; margin-bottom: 12px; border: 1px solid #eee; transition: all 0.2s ease; cursor: pointer; }
        .trend-row:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); border-color: #FF4B4B; }
        .rank-num { font-size: 1.5em; font-weight: bold; color: #ccc; width: 40px; text-align: center; }
        .rank-1 { color: #FF4B4B; }
        .rank-2 { color: #FF8F00; }
        .rank-3 { color: #FFC107; }
        .volume-badge { background-color: #ffebee; color: #c62828; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
        .category-badge { background-color: #f1f3f4; color: #555; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("📊 話題熱度分佈")
    df = pd.DataFrame(trends)
    if not df.empty:
        st.bar_chart(df.set_index('keyword')['score'], color="#FF4B4B")

    st.subheader("🏆 全台話題排行榜 (點擊可看新聞)")
    
    for i, item in enumerate(trends):
        rank_class = f"rank-{i+1}" if i < 3 else ""
        search_query = urllib.parse.quote(item['keyword'])
        google_url = f"https://www.google.com/search?q={search_query}"
        
        st.markdown(f"""
        <a href="{google_url}" target="_blank" class="trend-link">
            <div class="trend-row">
                <div style="display:flex; align-items:center;">
                    <div class="rank-num {rank_class}">{i+1}</div>
                    <div style="flex-grow:1; padding-left:15px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h3 style="margin:0; font-size:1.2em; color:#333;">{item['keyword']} 🔗</h3>
                            <span class="volume-badge">🔥 {item.get('volume_label', '熱議中')}</span>
                        </div>
                        <div style="margin-top:5px; font-size:0.9em; color:#666;">
                            <span class="category-badge">{item['category']}</span>
                            <span style="margin-left:8px;">{item['summary']}</span>
                        </div>
                        <div style="margin-top:8px; font-size:0.85em; color:#888;">
                            {' '.join([f'#{tag}' for tag in item.get('hashtags', [])]).replace('##', '#')}
                        </div>
                    </div>
                </div>
            </div>
        </a>
        """, unsafe_allow_html=True)

else:
    st.info("目前無法取得資料，請稍後再試。")
