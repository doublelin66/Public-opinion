import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import random

# ================= 1. 基礎設定 =================
st.set_page_config(
    page_title="🇹🇼台灣熱門討論",
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

# ================= 3. 定義新聞來源 =================
def get_rss_url(category):
    base_search = "https://news.google.com/rss/search"
    suffix = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    def make_search_url(query):
        # 加入 when:2d 確保新聞新鮮度
        query_with_time = f"{query} when:2d"
        encoded_query = urllib.parse.quote(query_with_time)
        return f"{base_search}?q={encoded_query}&scoring=n&{suffix}"

    topics = {
        "首頁": [
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW",
            f"https://news.google.com/rss?{suffix}"
        ],
        "政治": [make_search_url("台灣政治 立法院 行政院")],
        "財經": [make_search_url("台灣股市 財經 台積電 營收")],
        "科技": [make_search_url("台灣科技 半導體 AI 輝達")],
        "娛樂": [make_search_url("台灣娛樂新聞 網紅 藝人 直播")],
        "運動": [make_search_url("中華職棒 NBA 台灣運動")],
        "國際": [make_search_url("國際新聞 美國 日本 中國")],
        "健康": [make_search_url("健康醫療 食安 流感 腸病毒")]
    }
    return topics.get(category, topics["首頁"])

# ================= 4. 核心功能：AI 分析 =================
# 快取設定：30分鐘內不重新抓取，避免被擋
@st.cache_data(ttl=1800) 
def run_analysis(category):
    debug_logs = []
    
    # A. 模型設定
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    generation_config = {"temperature": 1, "response_mime_type": "application/json"}
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings, generation_config=generation_config)
    except:
        model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)

    # B. 抓取資料
    urls = get_rss_url(category)
    all_raw_data = []
    
    # 偽裝 Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    cookies = {"CONSENT": "YES+"} 

    for url in urls:
        try:
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                limit = 30 if category == "首頁" else 20
                
                for entry in feed.entries[:limit]:
                    traffic = entry.ht_approx_traffic if hasattr(entry, 'ht_approx_traffic') else "N/A"
                    all_raw_data.append({
                        "title": entry.title,
                        "traffic": traffic,
                        "snippet": entry.summary if hasattr(entry, 'summary') else ""
                    })
            else:
                debug_logs.append(f"HTTP Error: {response.status_code} at {url}")
        except Exception as e:
            debug_logs.append(str(e))
            continue

    if not all_raw_data:
        return [], debug_logs

    # C. AI 分析 (修正語法錯誤風險)
    news_json = json.dumps(all_raw_data, ensure_ascii=False)
    
    if category == "首頁":
        task_desc = "請列出 **15-20 個** 台灣現在 **全網最熱門、最新** 的討論話題。"
    else:
        task_desc = f"請專注於 **{category}** 領域，列出 **10-15 個** 該領域 **這兩天內** 最受關注的議題。"

    # --- 這裡將 JSON 範例獨立出來，避免 f-string 語法錯誤 ---
    json_example = f"""
    [
      {{
        "id": 1,
        "keyword": "話題關鍵字",
        "category": "分類 (如: {category})",
        "score": 95,
        "volume_label": "討論量級 (如: 5萬+ 搜尋 / 熱議中)",
        "summary": "簡短說明",
        "hashtags": ["#tag1"]
      }}
    ]
    """

    prompt = f"""
    你是一個台灣社群趨勢觀察家。請分析以下資料，找出「現在進行式」的熱門話題。
    {task_desc}

    原始資料：
    {news_json}
    
    要求：
    1. **時效優先**：請忽略舊聞，只專注在最近發生的事件。
    2. 合併重複的事件。
    3. 有流量數據 (如 "50,000+") 分數給高。
    4. 繁體中文摘要。
    
    請回傳 JSON Array：
    {json_example}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        if not cleaned_text: return [], debug_logs
        return json.loads(cleaned_text), debug_logs
    except Exception as e:
        return [], [str(e)]

# ================= 5. 介面顯示 (UI) =================

st.sidebar.title("🔥 導覽選單")
st.sidebar.markdown("請選擇您感興趣的看版：")

options = ["首頁 (全網熱搜)", "⚖️ 政治", "💰 財經", "💻 科技", "🍿 娛樂", "⚾ 運動", "🌏 國際", "🏥 健康"]
selection = st.sidebar.radio("Go to", options, label_visibility="collapsed")

category_map = {
    "首頁 (全網熱搜)": "首頁", "⚖️ 政治": "政治", "💰 財經": "財經",
    "💻 科技": "科技", "🍿 娛樂": "娛樂", "⚾ 運動": "運動",
    "🌏 國際": "國際", "🏥 健康": "健康"
}
current_category = category_map[selection]

col1, col2 = st.columns([3, 1])
with col1:
    if current_category == "首頁":
        st.title("🇹🇼 台灣熱門討論")
    else:
        st.title(f"🇹🇼 {current_category}熱門討論")
    st.caption(f"即時 AI 輿情分析 | 資料範圍: 48小時內 | 更新: {datetime.now().strftime('%H:%M')}")

with col2:
    if st.button("🔄 重新整理"):
        st.rerun()

st.divider()

with st.spinner(f'🔍 正在掃描 {current_category} 版面「最新」新聞與趨勢...'):
    trends, logs = run_analysis(current_category)

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

    if current_category == "首頁":
        st.subheader("📊 話題熱度分佈")
        df = pd.DataFrame(trends)
        if not df.empty:
            st.bar_chart(df.set_index('keyword')['score'], color="#FF4B4B")

    st.subheader(f"🏆 {current_category}話題排行榜")
    
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
                            <span class="category-badge">{item.get('category', current_category)}</span>
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
    st.error("目前流量過大，資料暫時無法讀取。")
    st.info("💡 系統提示：這可能是因為 Google 新聞暫時限制了連線，請過 10-15 分鐘後再回來試試看，無需一直按重新整理。")
