# 曼哈頓中城計程車流量視覺化（Streamlit App）

這個專案是一個使用 **Python + Streamlit + Folium** 建立的互動式網頁，
用來展示 **紐約曼哈頓中城六個 Taxi Zones** 的計程車進出流量，
並比較不同預測模型（ARIMA / TensorTS / LSTM）在 21 天保留資料上的表現。

---

## 功能簡介

網站目前有三個主要分頁（tabs）：

1. **21-day Compare（OBS vs ARIMA vs TensorTS vs LSTM）**  
   - 針對保留的 21 天資料  
   - 比較觀測值 (OBS) 與三種模型的預測結果  
   - 可依「早 / 午 / 晚」時段切換

2. **Full OBS View（252-day OBS Hourly）**  
   - 顯示完整 252 天的逐小時觀測流量  
   - 讓使用者看到長期趨勢與季節性變化

3. **OD Matrix Heatmap（OBS / Models / Errors）**  
   - 顯示 6×6 起訖區間的 OD matrix  
   - 可切換 OBS / 各模型預測 / 誤差 (Error)  
   - 有助於看到「哪一些 OD pair 預測得好 / 哪些誤差大」

使用者可以在側邊欄選擇日期、時段，以及要顯示的模型或指標，
以自助方式探索自己關心的情境。

---

## 專案結構（簡要）

```text
project-root/
├─ app/                      # Streamlit 應用程式（Python）
│   ├─ app.py                # 入口程式（streamlit run app/app.py）
│   ├─ config.py
│   ├─ data_utils.py
│   ├─ geo_utils.py
│   ├─ map_utils.py
│   ├─ tabs/
│   │   ├─ tab_compare_21d.py
│   │   ├─ tab_full_obs.py
│   │   ├─ tab_od_heatmap.py
│   │   └─ __init__.py
│   └─ __init__.py
│
├─ data/
│   ├─ geo/                  # 地理資訊（midtown6.geojson, taxi_zones.shp, ...）
│   ├─ mapping/              # 各種對照表（day_map, period_hour_map, zone_map, ...）
│   ├─ processed/            # 整理好的 canonical 資料（App 直接讀取）
│   └─ raw/                  # 原始 RData / 模型輸出（可不放到 GitHub）
│
├─ R/
│   ├─ models/               # ARIMA / LSTM / TensorTS 等建模腳本
│   ├─ data_prep/            # 產生 mapping / canonical 資料的腳本
│   └─ analysis/             #（可選）額外分析、繪圖腳本
│
├─ scripts/                  # 單次 / 工具型 Python 腳本
│   └─ 01_make_midtown6_geojson.py
│
├─ output/                   # 報表或匯出結果（不一定放到 Git）
├─ README.md
├─ requirements.txt
└─ .gitignore
