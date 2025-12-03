# EmoGo 後端與資料串接說明

本專案延伸自先前的 **EmoGo 情緒與影片紀錄 App**。  
這次保留原本前端 App 的操作流程，新增：

- 後端 API（FastAPI）
- 雲端資料庫（MongoDB Atlas）
- 可調整的提醒時間機制
- 錄影後自動上傳紀錄到雲端

---

## 📱 前端 App（React Native / Expo）

目前使用的 App 版本（APK）：  
👉 <https://expo.dev/accounts/kylelai/projects/emogo-frontend/builds/563cde7e-95cb-4a15-b9d3-a8d8a470bd9c>

### App 主要流程

1. 使用者先在主畫面選擇 **心情指數（1–5 分）**。
2. 選好心情後才能進入錄影畫面。
3. 錄影結束後，App 會自動記錄並上傳：
   - 心情文字與數值
   - 目前經緯度
   - 錄製完成的影片（Base64 編碼）
   - 記錄時間與上傳時間

### 提醒功能（新功能）

- 預設每天三個提醒時間：**09:00、15:00、21:00**。
- 使用者可以在「設定」頁：
  - 修改每一個提醒時間
  - 新增更多提醒
  - 刪除多餘提醒（至少保留 3 個）

---

## ☁️ 後端服務（FastAPI + MongoDB Atlas）

後端部署於 Render：  
👉 <https://emogo-backend-kylelaiii.onrender.com>

主要工作：

- 接收 App 上傳的紀錄，寫入 MongoDB Atlas
- 透過網頁 `/export` 顯示所有紀錄
- 提供 CSV 匯出與影片下載功能

---

## 🔌 API 端點總覽

Base URL：`https://emogo-backend-kylelaiii.onrender.com`

- `POST /records`  
  接收前端送來的一筆紀錄（心情、經緯度、時間、影片 Base64…）並寫入 MongoDB。

- `GET /export`  
  以 HTML 表格顯示所有紀錄，欄位包含：
  - ID、心情、心情值、緯度、經度  
  - 記錄時間（台北時間）、上傳時間（台北時間）  
  - 影片路徑、影片下載連結（若有影片）

- `GET /export/csv`  
  將所有紀錄（不含影片檔本身）匯出為 `emogo_records.csv`，內容欄位與 `/export` 的表格對應。

- `GET /records/{record_id}/video`  
  依照紀錄的 `id` 回傳該筆的影片檔（`video/mp4`），供下載或後續分析使用。

---

## 📊 使用方式簡述

1. 在手機安裝 EmoGo APK，正常操作 App（選心情 → 錄影）。
2. 每次錄影完成後，紀錄會自動上傳到 MongoDB Atlas。
3. 開啟後端網址 `/export` 可以查看所有紀錄、下載單筆影片。
4. 需要進一步分析時，可透過 `/export/csv` 下載 CSV，在 Excel / R / Python 中使用。