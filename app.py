import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime

# ================= 1. 基礎設定 =================
st.set_page_config(
    page_title="台灣熱門討論",
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
@st.cache_data(ttl=3600)  # 快取 1 小時
def run_analysis():
    # --- A. 模型設定 (使用您帳號支援的 2.5 Flash) ---
    model_name = 'gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-pro')

    # --- B. 定義多個新聞來源 (擴充資訊量) ---
    # 這裡包含了 Google 新聞的三大分類：財經、科技、綜合焦點
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
            
            # 每個分類抓前 10 則，總共約 30 則
            for entry in feed.entries[:10]:
                all_raw_data.append({
                    "source_channel": category_name, # 標記是哪一類的新聞
                    "title": entry.title, 
                    "pubDate": entry.published
                })
        except Exception as e:
            print(f"Error fetching {category_name}: {e}")
            continue

    if not all_raw_data:
        return []

    # --- C. AI 分析 (升級版 Prompt) ---
    # 讓 AI 處理大量資訊：去重、分類、排序
    prompt = f"""
    你是一個專業的股市輿情分析師。請閱讀以下來自不同頻道(財經/科技/焦點)的 30 則台灣新聞標題。
    請進行深度分析，並產出 JSON 格式的報告。

    原始新聞資料：
    {json.dumps(all_raw_data, ensure_ascii=False)}
    
    任務
