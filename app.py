/**
 * Google Drive 資料夾連線測試工具
 * 用途：測試指定的 Folder ID 是否正確，以及是否有權限存取。
 */
function debugDriveConnection() {
  // ==========================================
  // 【請在這裡填入您的資料夾 ID】
  // 請確保前後沒有空白鍵，也沒有包含 URL 其他部分
  var targetFolderId = "請將這裡替換成您的ID"; 
  // ==========================================

  Logger.log("=== 開始測試 ===");
  Logger.log("目標 ID: " + targetFolderId);

  try {
    // 1. 嘗試去除可能不小心複製到的空白鍵
    var cleanId = targetFolderId.trim(); 
    
    if (cleanId === "" || cleanId === "請將這裡替換成您的ID") {
      throw new Error("請先在程式碼中填入正確的 Folder ID！");
    }

    // 2. 嘗試抓取資料夾
    Logger.log("正在嘗試連線至 Google Drive...");
    var folder = DriveApp.getFolderById(cleanId);
    
    // 3. 如果成功，抓取資料夾名稱並顯示
    var folderName = folder.getName();
    Logger.log("✅ 成功！找到資料夾：[" + folderName + "]");
    Logger.log("資料夾 URL: " + folder.getUrl());

    // 4. (選用) 測試是否能讀取內部檔案
    var files = folder.getFiles();
    if (files.hasNext()) {
      Logger.log("📁 資料夾內至少有一個檔案：" + files.next().getName());
    } else {
      Logger.log("📁 資料夾是空的，但連線正常。");
    }

  } catch (e) {
    // ==========================================
    // 錯誤診斷區
    // ==========================================
    Logger.log("❌ 測試失敗！");
    Logger.log("錯誤訊息: " + e.toString());
    
    if (e.toString().includes("Unexpected error")) {
      Logger.log("👉 建議：這通常是 ID 格式錯誤。請確認 ID 不包含網址列的 'folders/' 部分。");
    } else if (e.toString().includes("Access denied") || e.toString().includes("permission")) {
      Logger.log("👉 建議：權限不足。請確認執行此腳本的帳號有權限讀取該資料夾。");
    }
  }
  
  Logger.log("=== 測試結束 ===");
}
