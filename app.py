import streamlit as st
import google.generativeai as genai
import feedparser
import requests
import json
import pandas as pd
from datetime import datetime
import urllib.parse # 新增這個庫，用來處理網址編碼

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

# ================= 3. 核心功能：搜尋趨勢 + 新聞爬蟲 =================
@st.cache_data(ttl=1800) # 30 分鐘更新一次
def run_analysis():
    # --- A. 模型設定 ---
    model_name = 'gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-pro')

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
    你是一個台灣社群趨勢觀察家。請分析以下來自「Google 搜尋熱榜」與「新聞」的資料。
    使用者想知道 **「🇹🇼 台灣現在最熱門的討論是什麼？」**。

    原始資料：
    {news_json}
    
    🔥 任務指令：
    1. **主題要多**：請列出 **15 到 20 個** 不同的獨立話題。
    2. **話題多元**：涵蓋 政治、娛樂、運動、生活、財經。
    3. **討論熱度估算**：依照流量數據或新聞重要性給分 (0-100)。
    4. **繁體中文**：請用台灣人習慣的用語撰寫 summary。

    請嚴格遵守以下 JSON 輸出格式 (Array)，直接輸出 JSON：
    [
      {{
        "id": 1,
        "keyword": "話題關鍵字",
        "category": "分類 (Entertainment, Sports, Politics, Tech, Life)",
        "score": 95,
        "volume_label": "討論量級",
        "summary": "簡短說明為什麼大家在討論這個。",
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
        /* 讓超連結去除底線，並保持顏色 */
        a.trend-link {
            text-decoration: none !important;
            color: inherit !important;
            display: block;
        }
        
        .trend-row {
            background-color: white; 
            padding: 15px; 
            border-radius: 10px; 
            margin-bottom: 12px; 
            border: 1px solid #eee;
            transition: all 0.2s ease;
            cursor: pointer; /* 讓滑鼠變成手指形狀 */
        }
        
        .trend-row:hover {
            transform: translateY(-2px); /* 輕微浮起 */
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            border-color: #FF4B4B; /* 邊框變色 */
        }

        .rank-num {
            font-size: 1.5em; 
            font-weight: bold; 
            color: #ccc; 
            width: 40px; 
            text-align: center;
        }
        .rank-1 { color: #FF4B4B; }
        .rank-2 { color: #FF8F00; }
        .rank-3 { color: #FFC107; }
        
        .volume-badge {
            background-color: #ffebee; 
            color: #c62828; 
            padding: 3px 8px; 
            border-radius: 12px; 
            font-size: 0.8em; 
            font-weight: bold;
        }
        .category-badge {
            background-color: #f1f3f4;
            color: #555;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.8em;
        }
    </style>
    """, unsafe_allow_html=True)

    # 上方圖表 (保留)
    st.subheader("📊 話題熱度分佈")
    df = pd.DataFrame(trends)
    if not df.empty:
        st.bar_chart(df.set_index('keyword')['score'], color="#FF4B4B")

    # 排行榜
    st.subheader("🏆 全台話題排行榜 (點擊可看新聞)")
    
    for i, item in enumerate(trends):
        rank_class = f"rank-{i+1}" if i < 3 else ""
        
        # 製作 Google 搜尋連結
        # 使用 urllib.parse.quote 把中文轉成網址編碼 (例如 "台積電" -> "%E5%8F%B0...")
        search_query = urllib.parse.quote(item['keyword'])
        google_url = f"https://www.google.com/search?q={search_query}"
        
        # 使用 HTML <a> 標籤包住整個卡片，target="_blank" 代表開新視窗
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
    st.info("尚無資料，請稍後再試。")
