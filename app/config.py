# -*- coding: utf-8 -*-
# config.py             
# 路徑、常數、ZONE 名稱等

from pathlib import Path
import os

# ---------- 路徑 ----------
ROOT = Path(os.getenv("APP_ROOT", Path(__file__).resolve().parents[1]))
GEO  = ROOT / "data" / "geo" / "midtown6.geojson"
DATA = ROOT / "data" / "processed"

# ---------- 區名對照（軸標籤用） ----------
ZONE_ORDER = [186, 100, 230, 161, 162, 163]
ZONE_NAME = {
    186: "Penn Station/Madison Sq West",
    100: "Garment District",
    230: "Times Sq/Theatre District",
    161: "Midtown Center",
    162: "Midtown East",
    163: "Midtown North",
}

# period 小時數（Mean/Sum 換算用）
HOURS_PER_PERIOD = {"morning": 6, "afternoon": 6, "night": 5}

# 0..5 → 真實 zone_id 對照（保留）
LSTM_ZONE_MAP = {0:186, 1:100, 2:230, 3:161, 4:162, 5:163}
