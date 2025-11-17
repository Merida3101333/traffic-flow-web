# -*- coding: utf-8 -*-
# app.py                
# 入口，只做 layout + 呼叫各 tab

import streamlit as st

from config import GEO
from geo_utils import load_geojson, guess_center, compute_bounds, compute_centroids
from tabs import tab_compare_21d, tab_full_obs, tab_od_heatmap

st.set_page_config(page_title="Midtown Taxi Flow", layout="wide")
st.title("曼哈頓中城區計程車車流量預測模型比較")

# ---------- 載入 GeoJSON & 幾何資訊 ----------
gj = load_geojson(GEO)
GLOBAL_CENTER = guess_center(gj)
GLOBAL_BOUNDS = compute_bounds(gj)
ZONE_CENTERS  = compute_centroids(gj)

# ---------- 側欄：全域視圖控制 ----------
st.sidebar.header("View Controls")
use_fit = st.sidebar.checkbox("Fit to Midtown bounds", value=False, key="sb_fit")
global_zoom = st.sidebar.slider("Zoom", min_value=10, max_value=16,
                                value=13, step=1, key="sb_zoom")
show_labels = st.sidebar.checkbox("Show labels (values)", value=True, key="sb_labels")

if use_fit:
    center = (
        (GLOBAL_BOUNDS[0] + GLOBAL_BOUNDS[2]) / 2.0,
        (GLOBAL_BOUNDS[1] + GLOBAL_BOUNDS[3]) / 2.0
    )
else:
    center = GLOBAL_CENTER

# ---------- Tabs 樣式（保留你原本的 CSS） ----------
st.markdown("""
<style>
:root { --tab-label-size: 20px; }

.stTabs [role="tab"] {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}
.stTabs [role="tab"] p,
.stTabs [role="tab"] span,
.stTabs [role="tab"] div {
  font-size: var(--tab-label-size) !important;
  line-height: 1.3 !important;
}
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "模型預測 21 天車流量與真實值比較 (OBS vs Models)",
    "OD 矩陣熱圖",
    "完整 252 天車流量"
])

with tab1:
    tab_compare_21d.render(
        gj=gj,
        center=center,
        global_zoom=global_zoom,
        show_labels=show_labels,
        zone_centers=ZONE_CENTERS,
    )

with tab2:
    tab_od_heatmap.render()

with tab3:
    # 這支檔案裡面再去 load_csv / hourly_zone_values 等
    tab_full_obs.render(
        gj=gj,
        center=center,
        global_zoom=global_zoom,
        show_labels=show_labels,
        zone_centers=ZONE_CENTERS,
        global_bounds=GLOBAL_BOUNDS,
    )


