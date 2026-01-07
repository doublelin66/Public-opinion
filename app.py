# ================= 3. 核心功能：多重來源爬蟲 + AI 分析 =================
@st.cache_data(ttl=3600)
def run_analysis():
    # 使用您的 2.5 Flash 模型
    model_name = 'gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-pro')

    # --- 🚀 升級：定義多個新聞來源 (財經、科技、焦點) ---
    rss_sources = {
        "💰 財經": "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0FBUWlHZ0pKVERNU0FBUW?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
        "🤖 科技": "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGRqTVhZU0FBUWlHZ0pKVERNU0FBUW?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
        "🔥 焦點": "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    }
    
    all_raw_data = []
    
    # 偽裝成瀏覽器
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 迴圈抓取每一個來源
    for category_name, url in rss_sources.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
            # 每個分類抓前 10 則，總共就有 30 則
            for entry in feed.entries[:10]:
                all_raw_data.append({
                    "source": category_name, # 標記來源
                    "title": entry.title, 
                    "pubDate": entry.published
                })
        except Exception as e:
            print(f"Error fetching {category_name}: {e}")
            continue

    if not all_raw_data:
        return []

    # C. AI 分析 (Prompt 也升級，請 AI 分類更細)
    prompt = f"""
    你是一個專業的股市輿情分析師。請閱讀以下來自不同頻道的台灣新聞標題，並產出 JSON 格式的深度趨勢報告。
    
    原始新聞資料：
    {json.dumps(all_raw_data, ensure_ascii=False)}
    
    請嚴格遵守以下 JSON 輸出格式 (Array)，直接輸出 JSON：
    [
      {{
        "id": 1,
        "keyword": "新聞關鍵字 (例如：台積電)",
        "category": "分類 (Tech, Finance, Politics)",
        "score": 88 (熱度分數 60-100),
        "summary": "50字內的繁體中文深度短評，若有關鍵個股請特別點出。",
        "hashtags": ["#tag1", "#tag2"]
      }}
    ]
    請過濾掉重複的新聞，並依照「對投資市場影響力」由高到低排序。
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.warning(f"AI 分析失敗: {e}")
        return []
