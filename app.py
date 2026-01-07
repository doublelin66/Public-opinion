import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import random # 用來隨機延遲

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
# 關鍵修改：TTL 設定為 1800 秒 (30分鐘)
# 這表示 30 分鐘內，不管誰來訪問，都直接給他看「舊的快取」，不要去煩 Google
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
    
    # 關鍵修改：更強的偽裝 Headers
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

    # C. AI 分析
    news_json = json.dumps(all_raw_data, ensure_ascii=False)
    
    if category == "首頁":
        task_desc = "請列出 **15-20 個** 台灣現在 **全網最熱門、最新** 的討論話題。"
    else:
        task_desc = f"請專注於 **{category}** 領域，列出 **10-15 個** 該領域 **這兩天內** 最受關注的議題。"

    prompt = f"""
    你是一個台灣社群趨勢觀察家。請分析以下資料，找出「現在進行式」的熱門話題。
    {task_desc}

    原始資料：
    {news_json}
    
    要求：
    1
