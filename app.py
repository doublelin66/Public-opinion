import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import random
import time

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
def get_rss_urls(category):
    base_search = "https://news.google.com/rss/search"
    base_topic = "https://news.google.com/rss/topics"
    suffix = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    def make_search_url(query):
        # 加入 when:2d 確保新聞新鮮度
        query_with_time = f"{query} when:2d"
        encoded_query = urllib.parse.quote(query_with_time)
        return f"{base_search}?q={encoded_query}&scoring=n&{suffix}"

    topic_ids = {
        "政治": "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0FBUWlHZ0pKVERNU0FBUW",
        "財經": "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0FBUWlHZ0pKVERNU0FBUW",
        "科技": "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGRqTVhZU0FBUWlHZ0pKVERNU0FBUW",
        "娛樂": "CAAqKggKIiRDQkFTRlFvSUwyMHZNREpxYW5RU0FBUWlHZ0pKVERNU0FBUW",
        "運動": "CAAqKggKIiRDQkFTRlFvSUwyMHZNRFp1ZEdvU0FBUWlHZ0pKVERNU0FBUW",
        "國際": "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0FBUWlHZ0pKVERNU0FBUW",
        "健康": "CAAqIaHZBAgESHgQAlIICgYI1p2w8wIw8MuzAzC4rYoD"
    }

    primary_url = ""
    if category == "首頁":
        return [
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW",
            f"https://news.google.com/rss?{suffix}"
        ]
    elif category == "政治": primary_url = make_search_url("台灣政治 立法院 行政院")
    elif category == "財經": primary_url = make_search_url("台灣股市 財經 台積電 營收")
    elif category == "科技": primary_url = make_search_url("台灣科技 半導體 AI 輝達")
    elif category == "娛樂": primary_url = make_search_url("台灣娛樂新聞 網紅 藝人 直播")
    elif category == "運動": primary_url = make_search_url("中華職棒 NBA 台灣運動")
    elif category == "國際": primary_url = make_search_url("國際新聞 美國 日本 中國")
    elif category == "健康": primary_url = make_search_url("健康醫療 食安 流感 腸病毒")

    backup_url = ""
    if category in topic_ids:
        backup_url = f"{base_topic}/{topic_ids[category]}?{suffix}"
    else:
        backup_url = f"https://news.google.com/rss?{suffix}"

    return [primary_url, backup_url]

# ================= 4. 核心功能：AI 分析 (全模型輪替) =================
@st.cache_data(ttl=1800) 
def run_analysis(category):
    debug_logs = []
    
    # 抓取資料
    target_urls = get_rss_urls(category)
    all_raw_data = []
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    cookies = {"CONSENT": "YES+"} 

    success_count = 0
    for url in target_urls:
        if success_count > 0 and category != "首頁": break 
        try:
            time.sleep(random.uniform(0.1, 0.5))
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if len(feed.entries) > 0:
                    limit = 25 if category == "首頁" else 15
                    for entry in feed.entries[:limit]:
                        traffic = entry.ht_approx_traffic if hasattr(entry, 'ht_approx_traffic') else "N/A"
                        all_raw_data.append({
                            "title": entry.title,
                            "traffic": traffic,
                            "snippet": entry.summary if hasattr(entry, 'summary') else ""
                        })
                    success_count += 1
        except Exception as e:
            debug_logs.append(f"連線錯誤: {str(e)}")
            continue

    if not all_raw_data:
        return [], debug_logs

    # --- AI 分析 ---
    news_json = json.dumps(all_raw_data, ensure_ascii=False)
    
    if category == "首頁":
        task_desc = "請列出 **15-20 個** 台灣現在 **全網最熱門、最新** 的討論話題。"
    else:
        task_desc = f"請專注於 **{category}** 領域，列出 **10-15 個** 該領域 **這兩天內** 最受關注的議題。"

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
    1. **時效優先**：請忽略舊聞。
    2. 合併重複的事件。
    3. 有流量數據分數給高。
    4. 繁體中文摘要。
    
    請回傳 JSON Array：
    {json_example}
    """

    # --- 關鍵修正：超級散彈槍模式 ---
    # 這裡列出了 Google 目前所有開放的免費模型名稱
    # 只要其中有一個能通，您的網站就會活著
    models_to_try = [
        'gemini-2.0-flash',       # 最強，但容易被擋
        'gemini-1.5-flash',       # 額度最高 (每天1500次)，最穩
        'gemini-1.5-flash-latest',# 1.5 的最新版變體
        'gemini-1.5-flash-001',   # 1.5 的舊版變體 (有時候 404 是因為沒加版號)
        'gemini-1.5-flash-002',   # 1.5 的更新版變體
        'gemini-1.5-flash-8b',    # 8B 版 (輕量級，額度通常獨立計算)
        'gemini-2.0-flash-exp',   # 2.0 實驗版
        'gemini-2.5-flash'        # 2.5 預覽版
    ]

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    generation_config = {"temperature": 1, "response_mime_type": "application/json"}

    for model_name in models_to_try:
        try:
            # 這裡不印 Log 了，以免嚇到使用者，默默嘗試就好
            model = genai.GenerativeModel(model_name, safety_settings=safety_settings, generation_config=generation_config)
            
            response = model.generate_content(prompt)
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            
            if cleaned_text:
                return json.loads(cleaned_text), debug_logs
                
        except Exception as e:
            # 失敗就換下一個，不要停
            debug_logs.append(f"❌ {model_name} 失敗，嘗試下一個...")
            time.sleep(0.5)
            continue
            
    return [], debug_logs

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

with st.spinner(f'🔍 正在掃描 {current_category} 版面，並嘗試連接最佳 AI 模型...'):
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
    with st.expander("🛠️ 系統診斷報告", expanded=True):
        st.write("嘗試連線紀錄：")
        for log in logs:
            st.write(log)
