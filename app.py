import streamlit as st
import google.generativeai as genai
import sys

# 1. 基礎設定
st.set_page_config(page_title="系統診斷", page_icon="🛠️")
st.title("🛠️ Clarity 系統診斷模式")

# 2. 顯示環境資訊
st.subheader("1. 環境版本檢查")
st.write(f"Python Version: `{sys.version}`")
st.write(f"Google GenAI SDK Version: `{genai.__version__}`")
# 關鍵：如果這裡顯示的版本低於 0.8.0，代表 Streamlit 根本沒更新

# 3. 測試金鑰與模型清單
st.subheader("2. 模型連線測試")

try:
    # 嘗試讀取金鑰
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    st.success("✅ 金鑰讀取成功 (Secrets 設定正確)")
    
    genai.configure(api_key=API_KEY)
    
    # 列出所有可用模型
    st.write("正在向 Google 查詢您的帳號可用模型...")
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    if available_models:
        st.success(f"✅ 連線成功！共找到 {len(available_models)} 個可用模型：")
        st.code("\n".join(available_models))
        
        # 幫您自動判斷
        if 'models/gemini-1.5-flash' in available_models:
            st.info("🎉 太棒了！您的帳號支援 `models/gemini-1.5-flash`。")
        else:
            st.error("⚠️ 您的帳號似乎沒有 1.5 Flash 的權限，請參考上方清單修改程式碼。")
    else:
        st.warning("⚠️ 連線成功但找不到任何模型，可能是 API Key 權限問題。")

except Exception as e:
    st.error(f"❌ 連線失敗: {e}")
    st.error("請檢查 Streamlit Secrets 中的 GOOGLE_API_KEY 是否正確。")
