# app/app.py — 整合與增強版
# =========================================
# Tabs:
#   1) 21-day Compare (OBS vs ARIMA vs TensorTS vs LSTM) — period level
#   2) Full 252-day (OBS Hourly)
#   3) OD Matrix Heatmap（OBS / Models / Errors）

import json
from pathlib import Path
import os
import pandas as pd
import numpy as np
import folium
import streamlit as st
from streamlit_folium import st_folium
from branca.colormap import linear
import plotly.express as px

# ---------- half-up 格式化（只影響「地圖標籤」顯示，不影響計算/著色） ----------
from decimal import Decimal, ROUND_HALF_UP
def format_label_half_up(val: float, digits: int) -> str:
    """
    half-up 四捨五入的字串格式化：
    - digits=0 → 整數
    - digits=1 → 一位小數
    - 皆含千分位
    """
    q = Decimal(str(val)).quantize(Decimal("1") if digits == 0 else Decimal(f"1.{'0'*digits}"),
                                   rounding=ROUND_HALF_UP)
    return f"{q:,.{digits}f}"

# ---------- 路徑 ----------
# 優先使用環境變數 APP_ROOT；未設定時，退回到 app/ 的上一層
ROOT = Path(os.getenv("APP_ROOT", Path(__file__).resolve().parents[1]))

GEO  = ROOT / "data" / "geo" / "midtown6.geojson"
DATA = ROOT / "data" / "processed"

st.set_page_config(page_title="Midtown Taxi Flow", layout="wide")
st.title("曼哈頓中城區計程車車流量預測模型比較")

# === Debug/Diagnostics 面板（本機與雲端環境快速比對） ===
with st.sidebar.expander("🔧 Diagnostics（環境自檢）", expanded=False):
    import sys, importlib, os
    st.write("**Python**", sys.version)
    for mod in ["streamlit", "streamlit_folium", "folium", "branca", "shapely", "numpy", "pandas", "plotly"]:
        try:
            m = importlib.import_module(mod)
            st.write(f"**{mod}**", getattr(m, "__version__", "unknown"))
        except Exception as e:
            st.write(f"**{mod}**", f"NOT INSTALLED ({e})")

    st.write("**ROOT**", str(ROOT))
    st.write("**Paths exist?**  GEO:", GEO.exists(), " | DATA dir:", DATA.exists())
    try:
        csvs = sorted([p.name for p in DATA.glob("*.csv")])
    except Exception:
        csvs = []
    st.write("**Data files in /data/processed/**", csvs[:20], ("…共 %d 個" % len(csvs)) if len(csvs) > 20 else "")

    # shapely 是否可用（影響 ZONE_CENTERS 與數字標籤）
    try:
        from shapely.geometry import shape  # noqa: F401
        st.write("**Shapely**", "OK")
    except Exception as e:
        st.write("**Shapely**", f"FAILED: {e}")

    # 顯示 ZONE_CENTERS 是否為空
    try:
        st.write("**ZONE_CENTERS empty?**", (len(ZONE_CENTERS) == 0))
    except Exception:
        st.write("**ZONE_CENTERS**", "not yet computed here")


# ---------- 載入 GeoJSON ----------
with open(GEO, "r", encoding="utf-8") as f:
    gj = json.load(f)

# ---------- 幾何輔助：中心、邊界、標籤座標 ----------
def guess_center(geojson):
    try:
        from shapely.geometry import shape
        feats = geojson.get("features", [])
        if feats:
            c = shape(feats[0]["geometry"]).centroid
            return float(c.y), float(c.x)
    except Exception:
        pass
    return 40.758, -73.985  # Times Square

def compute_bounds(geojson):
    try:
        from shapely.geometry import shape
        minx = miny =  1e9
        maxx = maxy = -1e9
        for ft in geojson["features"]:
            b = shape(ft["geometry"]).bounds  # (minx, miny, maxx, maxy)
            minx = min(minx, b[0]); miny = min(miny, b[1])
            maxx = max(maxx, b[2]); maxy = max(maxy, b[3])
        return (miny, minx, maxy, maxx)
    except Exception:
        return (40.74, -74.01, 40.78, -73.95)

def compute_centroids(geojson):
    """回傳 {zone_id: (lat, lng)}，使用 representative_point() 讓標籤落在多邊形內。"""
    centers = {}
    try:
        from shapely.geometry import shape
        for ft in geojson["features"]:
            props = ft.get("properties", {})
            zid = props.get("zone_id")
            if zid is None:
                continue
            geom = shape(ft["geometry"])
            p = geom.representative_point()
            centers[zid] = (float(p.y), float(p.x))
    except Exception:
        pass
    return centers

GLOBAL_CENTER = guess_center(gj)
GLOBAL_BOUNDS = compute_bounds(gj)
ZONE_CENTERS  = compute_centroids(gj)

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
def zid_label(zid: int) -> str:
    # 兩行顯示：ID + 簡名
    name = ZONE_NAME.get(zid, str(zid))
    return f"{zid}\n{(name if len(name)<=22 else name[:22]+'…')}"

# ---------- 共用地圖生成（Folium） ----------
def make_map_with_values(title, gj, values, vmin=None, vmax=None,
                         center=None, zoom=13, show_labels=True, label_digits=0):
    center = center or GLOBAL_CENTER
    m = folium.Map(location=list(center), zoom_start=zoom, tiles="CartoDB positron")

    # 色階範圍
    if values is not None and len(values) > 0:
        vmin = float(values.min()) if vmin is None else float(vmin)
        vmax = float(values.max()) if vmax is None else float(vmax)
        if vmax == vmin: vmax = vmin + 1.0
    else:
        vmin, vmax = 0.0, 1.0

    cmap = linear.Reds_09.scale(vmin, vmax)
    base_style = {"weight": 1.2, "color": "#333333", "fillOpacity": 0.85}
    highlight  = {"weight": 2, "color": "#B30000", "fillOpacity": 0.95}
    tooltip    = folium.features.GeoJsonTooltip(fields=["zone_name", "zone_id"],
                                                aliases=["Zone", "ID"], sticky=True)

    def style_fn(feat):
        zid = feat["properties"].get("zone_id")
        fill = "#cccccc"
        if values is not None and zid in values.index:
            fill = cmap(values.loc[zid])
        s = base_style.copy()
        s["fillColor"] = fill
        return s

    folium.GeoJson(gj, name=title, style_function=style_fn,
                   highlight_function=lambda x: highlight, tooltip=tooltip).add_to(m)

    # 中心值標籤（四捨五入）
    if show_labels and values is not None and len(values) > 0:
        for zid, val in values.items():
            if zid in ZONE_CENTERS:
                lat, lng = ZONE_CENTERS[zid]
                label = format_label_half_up(float(val), digits=label_digits)
                html = f"""
                <div style="
                    position: relative;
                    left: 50%; top: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 12px; font-weight: 700;
                    color: #000;
                    white-space: nowrap;
                    text-shadow:
                        -1px -1px 1px rgba(255,255,255,0.9),
                         1px -1px 1px rgba(255,255,255,0.9),
                        -1px  1px 1px rgba(255,255,255,0.9),
                         1px  1px 1px rgba(255,255,255,0.9),
                         0px  0px 2px rgba(0,0,0,0.35);
                ">{label}</div>
                """
                folium.map.Marker(
                    [lat, lng],
                    icon=folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0))
                ).add_to(m)

    cmap.caption = title
    cmap.add_to(m)
    return m

# ---------- 資料讀取 ----------
@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name)

def get_period_file(model: str, period: str) -> Path | None:
    """
    回傳各模型 period 等級的檔案路徑：
      - LSTM: lstm_<period>_canonical_period.csv（每小時平均）
      - ARIMA: arima_<period>_canonical.csv（時段合計）
      - TensorTS: tensor_<period>_canonical.csv（時段合計）
      - OBS:   obs_period_canonical.csv（時段合計）
    """
    if model.lower() == "lstm":
        return {
            "morning":   DATA / "lstm_morning_canonical_period.csv",
            "afternoon": DATA / "lstm_afternoon_canonical_period.csv",
            "night":     DATA / "lstm_night_canonical_period.csv",
        }.get(period)

    if model.lower() == "arima":
        return {
            "morning":   DATA / "arima_morning_canonical.csv",
            "afternoon": DATA / "arima_afternoon_canonical.csv",
            "night":     DATA / "arima_night_canonical.csv",
        }.get(period)

    if model.lower() in ["tensor", "tensors", "tensorts"]:
        return {
            "morning":   DATA / "tensor_morning_canonical.csv",
            "afternoon": DATA / "tensor_afternoon_canonical.csv",
            "night":     DATA / "tensor_night_canonical.csv",
        }.get(period)

    if model.lower() == "obs":
        return DATA / "obs_period_canonical.csv"

    return None

# period 小時數（Mean/Sum 換算用）
HOURS_PER_PERIOD = {"morning": 6, "afternoon": 6, "night": 5}

def period_zone_values(model: str, day_abs: int, period: str, agg_mode: str, stat: str = "Sum") -> pd.Series | None:
    """
    回傳 index=zone_id 的 Series（聚合到「每區」）。
    單位對齊：
    - LSTM 檔為每小時平均：Sum → 乘以時段小時；Mean → 原值
    - 其他模型為時段合計：Sum → 原值；Mean → 除以時段小時
    """
    path = get_period_file(model, period)
    if path is None or not path.exists():
        return None

    df = pd.read_csv(path)
    val_col = next((c for c in ["y_pred", "value", "y_sum"] if c in df.columns), None)
    if val_col is None:
        return None

    df = df[(df["day_abs"] == day_abs) & (df["period"] == period)]
    if df.empty:
        return None

    # 先彙總到「每區」
    if agg_mode == "Origin sum (flow-out)":
        g = df.groupby("origin_zone_id", dropna=False)[val_col].sum()
    elif agg_mode == "Destination sum (flow-in)":
        g = df.groupby("dest_zone_id", dropna=False)[val_col].sum()
    elif agg_mode == "OD sum":
        g1 = df.groupby("origin_zone_id")[val_col].sum().rename("o")
        g2 = df.groupby("dest_zone_id")[val_col].sum().rename("d")
        g = (pd.concat([g1, g2], axis=1).fillna(0.0).sum(axis=1))
    else:
        return None

    # 單位換算
    hrs = HOURS_PER_PERIOD.get(period, 0)
    m = model.lower()
    if m == "lstm":
        if stat == "Sum" and hrs > 0:
            g = g * float(hrs)
    else:
        if stat == "Mean" and hrs > 0:
            g = g / float(hrs)

    g.index.name = "zone_id"
    return g

# ---- 將 OBS 小時資料依「任意小時清單」彙整到每區 ----
def hourly_zone_values(df_obs_hourly: pd.DataFrame, day_abs: int, hours: list[int],
                       agg_mode: str, stat: str = "Sum") -> pd.Series | None:
    sub = df_obs_hourly[(df_obs_hourly["day_abs"] == day_abs) &
                        (df_obs_hourly["hour_abs"].isin(hours))]
    if sub.empty:
        return None
    val = sub.groupby(["origin_zone_id", "dest_zone_id"], dropna=False)["count"]
    od = (val.sum() if stat == "Sum" else val.mean()).reset_index(name="value")

    if agg_mode == "Origin sum (flow-out)":
        g = od.groupby("origin_zone_id", dropna=False)["value"].sum()
        g.index.name = "zone_id"
        return g
    elif agg_mode == "Destination sum (flow-in)":
        g = od.groupby("dest_zone_id", dropna=False)["value"].sum()
        g.index.name = "zone_id"
        return g
    elif agg_mode == "OD sum":
        g1 = od.groupby("origin_zone_id")["value"].sum().rename("o")
        g2 = od.groupby("dest_zone_id")["value"].sum().rename("d")
        g = pd.concat([g1, g2], axis=1).fillna(0.0)
        g["total"] = g["o"] + g["d"]
        g = g["total"]
        g.index.name = "zone_id"
        return g
    return None

# ---- for Tab3：讀取「period」等級的 OD 長表，並調整單位（Sum/Mean） ----
def load_period_od(model: str, day_abs: int, period: str, stat: str = "Sum") -> pd.DataFrame | None:
    """
    回傳欄位：origin_zone_id, dest_zone_id, value
    單位對齊邏輯與 period_zone_values 相同（LSTM=每小時平均；其餘=時段合計）
    若缺值，自動補 0 讓矩陣齊 6×6
    """
    path = get_period_file(model, period)
    if path is None or not path.exists():
        return None

    df = pd.read_csv(path)
    val_col = next((c for c in ["y_pred", "value", "y_sum"] if c in df.columns), None)
    if val_col is None:
        return None

    # 先切出指定日/時段
    df = df[(df["day_abs"] == day_abs) & (df["period"] == period)]
    if df.empty:
        return None

    # 先把「逐小時/逐 slot」的多列，彙總成「同日×同 period×同 OD 一列」
    # （OBS/ARIMA/TensorTS 若原本就一列，這步不影響；若有 5~6 列，就會 sum 起來變成「時段合計」）
    vals = (df.groupby(["origin_zone_id", "dest_zone_id"], dropna=False)[val_col]
              .sum()
              .reset_index()
              .rename(columns={val_col: "value"}))

    # 單位換算（確保 Sum/Mean 的意義一致）
    hrs = HOURS_PER_PERIOD.get(period, 0)
    m = model.lower()
    if m == "lstm":
        # LSTM 檔為「每小時平均」；Sum 需 × 小時數，Mean 保持原值
        if stat == "Sum" and hrs > 0:
            vals["value"] = vals["value"] * float(hrs)
    else:
        # 其他檔（OBS/ARIMA/TensorTS）此時是「時段合計」；Mean 需 ÷ 小時數
        if stat == "Mean" and hrs > 0:
            vals["value"] = vals["value"] / float(hrs)

    # 補齊 6×6 所有 OD（避免 pivot 時有 NaN），並確保索引唯一
    all_pairs = pd.MultiIndex.from_product([ZONE_ORDER, ZONE_ORDER],
                                           names=["origin_zone_id","dest_zone_id"])
    vals = (vals.set_index(["origin_zone_id","dest_zone_id"])
                 .reindex(all_pairs)
                 .fillna(0.0)
                 .reset_index())

    return vals


def od_heatmap_matrix(df_od: pd.DataFrame) -> pd.DataFrame:
    """把 OD 長表轉成 6×6 矩陣（依 ZONE_ORDER 排序）"""
    mat = df_od.pivot(index="origin_zone_id", columns="dest_zone_id", values="value")
    mat = mat.reindex(index=ZONE_ORDER, columns=ZONE_ORDER)
    return mat.fillna(0.0)

# ---- 檔名查找（保留備用） ----
def _find_csv_in_data_dirs(filename: str) -> Path | None:
    cand1 = DATA / filename
    if cand1.exists(): return cand1
    cand2 = ROOT / "data" / "raw" / filename
    if cand2.exists(): return cand2
    return None

# 0..5 → 真實 zone_id 對照（保留）
LSTM_ZONE_MAP = {0:186, 1:100, 2:230, 3:161, 4:162, 5:163}

# ---------- 側欄：全域視圖控制 ----------
st.sidebar.header("View Controls")
use_fit = st.sidebar.checkbox("Fit to Midtown bounds", value=False, key="sb_fit")
global_zoom = st.sidebar.slider("Zoom", min_value=10, max_value=16, value=13, step=1, key="sb_zoom")
show_labels = st.sidebar.checkbox("Show labels (values)", value=True, key="sb_labels")

if use_fit:
    center = ((GLOBAL_BOUNDS[0] + GLOBAL_BOUNDS[2]) / 2.0,
              (GLOBAL_BOUNDS[1] + GLOBAL_BOUNDS[3]) / 2.0)
else:
    center = GLOBAL_CENTER

# ---------- Tabs ----------

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

tab1, tab3, tab2 = st.tabs([
    "模型預測 21 天車流量與真實值比較 (OBS vs Models)",
    "OD 矩陣熱圖",
    "完整 252 天車流量"
])

# ===== Tab 1: 21 天比較 =====
with tab1:
    st.subheader("Compare last 21 days (Day 232–252) by Period")

    colc1, colc2, colc3, colc4 = st.columns([1,1,1,1])
    with colc1:
        day_21 = st.number_input("Day (232–252)", min_value=232, max_value=252, value=232, step=1, key="t1_day")
    with colc2:
        period = st.radio("Period", ["morning","afternoon","night"], index=0, horizontal=True, key="t1_period")
    with colc3:
        agg_mode = st.selectbox("Aggregate to zone", ["Origin sum (flow-out)","Destination sum (flow-in)","OD sum"], index=0, key="t1_agg")
    with colc4:
        stat1 = st.radio("Period agg", ["Sum", "Mean"], index=0, horizontal=True, key="t1_stat")

    v_obs    = period_zone_values("obs",    day_21, period, agg_mode, stat=stat1)
    v_arima  = period_zone_values("arima",  day_21, period, agg_mode, stat=stat1)
    v_tensor = period_zone_values("tensor", day_21, period, agg_mode, stat=stat1)
    v_lstm   = period_zone_values("lstm",   day_21, period, agg_mode, stat=stat1)

    vals_for_scale = [s for s in [v_obs, v_arima, v_tensor, v_lstm] if s is not None and len(s) > 0]
    if vals_for_scale:
        vmin = float(min(s.min() for s in vals_for_scale))
        vmax = float(max(s.max() for s in vals_for_scale))
    else:
        vmin, vmax = 0.0, 1.0

    label_digits_tab1 = 0 if stat1 == "Sum" else 1

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    with c1:
        st.markdown(f"**OBS (Ground Truth) – {stat1}**")
        m1 = make_map_with_values("OBS", gj, v_obs, vmin, vmax,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=label_digits_tab1)
        st_folium(m1, width=None, height=360)

    with c2:
        st.markdown(f"**ARIMA – {stat1}**")
        m2 = make_map_with_values("ARIMA", gj, v_arima, vmin, vmax,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=label_digits_tab1)
        st_folium(m2, width=None, height=360)

    with c3:
        st.markdown(f"**TensorTS – {stat1}**")
        m3 = make_map_with_values("TensorTS", gj, v_tensor, vmin, vmax,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=label_digits_tab1)
        st_folium(m3, width=None, height=360)

    with c4:
        st.markdown(f"**LSTM – {stat1}**")
        m4 = make_map_with_values("LSTM", gj, v_lstm, vmin, vmax,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=label_digits_tab1)
        st_folium(m4, width=None, height=360)

# ===== Tab 2: 252 天（OBS 小時）— 任意區間聚合 + 動畫 =====
with tab2:
    st.subheader("OBS – Full 252 days (Hourly / Range & Animation)")

    df_obs_hourly = load_csv("obs_hourly_canonical.csv")

    if "anim_running" not in st.session_state:
        st.session_state.anim_running = False
    if "anim_hour" not in st.session_state:
        st.session_state.anim_hour = 1
    if "anim_hour_widget" not in st.session_state:
        st.session_state.anim_hour_widget = 1
    if "prev_day" not in st.session_state:
        st.session_state.prev_day = 1
    if "prev_range" not in st.session_state:
        st.session_state.prev_range = (1, 6)

    def _sync_anim_from_widget():
        st.session_state.anim_hour = st.session_state.anim_hour_widget

    colh1, colh2, colh3 = st.columns([1, 2, 1])
    with colh1:
        d_full  = st.number_input("Day (1–252)", min_value=1, max_value=252, value=1, step=1)
        agg_mode2 = st.selectbox("Aggregate to zone",
                                 ["Origin sum (flow-out)", "Destination sum (flow-in)", "OD sum"],
                                 index=0)
        stat2 = st.radio("Hour agg", ["Sum", "Mean"], horizontal=True, index=0)
    with colh2:
        h_start, h_end = st.slider("Hour range (1–24)", min_value=1, max_value=24, value=(1, 6), step=1)
        hours_range = list(range(h_start, h_end + 1))
        st.caption(f"區間小時：{hours_range}")
    with colh3:
        animate = st.checkbox("Animate hours", value=False)
        speed = st.slider("Speed (sec/frame)", 0.05, 1.0, 0.25, 0.05)

        cplay1, cplay2 = st.columns(2)
        with cplay1:
            if st.button("▶ Play"):
                st.session_state.anim_running = True
        with cplay2:
            if st.button("⏸ Pause"):
                st.session_state.anim_running = False

        st.slider("Current hour", 1, 24,
                  value=st.session_state.anim_hour, step=1,
                  key="anim_hour_widget", on_change=_sync_anim_from_widget)

    if (d_full != st.session_state.prev_day) or ((h_start, h_end) != st.session_state.prev_range):
        st.session_state.prev_day = d_full
        st.session_state.prev_range = (h_start, h_end)
        st.session_state.anim_hour = h_start
        st.session_state.anim_hour_widget = h_start

    left, right = st.columns(2)
    with left:
        v_range = hourly_zone_values(df_obs_hourly, d_full, hours_range, agg_mode2, stat2)
        title_l = f"OBS – Day {d_full}, Hours {h_start}-{h_end} ({stat2})"
        label_digits_left = 0 if stat2 == "Sum" else 1
        mL = make_map_with_values(title_l, gj, v_range,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=label_digits_left)
        st_folium(mL, width=None, height=520,
                  key=f"left_map_{d_full}_{h_start}_{h_end}_{agg_mode2}_{stat2}")

    with right:
        cur_h = st.session_state.anim_hour
        df_sel = df_obs_hourly[(df_obs_hourly["day_abs"] == d_full) &
                               (df_obs_hourly["hour_abs"] == cur_h)]
        if agg_mode2 == "Origin sum (flow-out)":
            v_single = df_sel.groupby("origin_zone_id")["count"].sum()
        elif agg_mode2 == "Destination sum (flow-in)":
            v_single = df_sel.groupby("dest_zone_id")["count"].sum()
        else:  # OD sum
            g1 = df_sel.groupby("origin_zone_id")["count"].sum().rename("o")
            g2 = df_sel.groupby("dest_zone_id")["count"].sum().rename("d")
            v_single = (pd.concat([g1, g2], axis=1).fillna(0.0).sum(axis=1))
        v_single.index.name = "zone_id"

        title_r = f"OBS – Day {d_full}, Hour {cur_h}"
        mR = make_map_with_values(title_r, gj, v_single,
                                  center=center, zoom=global_zoom, show_labels=show_labels,
                                  label_digits=0)  # 單一小時為整數
        st_folium(mR, width=None, height=520,
                  key=f"right_map_{d_full}_{cur_h}_{agg_mode2}")
        st.markdown(f"**Frame hour:** {cur_h}")

    st.caption("左：任意小時區間（Sum/Mean）。右：單一小時，可播放動畫。")

    if animate and st.session_state.anim_running:
        import time
        time.sleep(speed)
        nxt = st.session_state.anim_hour + 1
        if nxt > h_end or nxt < h_start:
            nxt = h_start
        st.session_state.anim_hour = nxt
        st.rerun()





# ===== Tab 3: OD Matrix Heatmap（OBS / Models / Errors） =====
with tab3:
    st.subheader("OD Matrix Heatmap — Period level (Day 232–252)")

    # ── Tab3 說明面板：Value / Error 定義與用法 ─────────────────────────────
    with st.expander("ℹ️ 什麼是 Value / Error？（點此展開說明）", expanded=False):
        st.markdown("""
        **你可以用上方的 Day / Period / Unit (Sum / Mean) 搭配下拉選單切換要看的內容。**
        ...
        """)

    # --- 控制列：與 Tab1 同步的概念，但獨立 widgets ---
    colm1, colm2, colm3, colm4 = st.columns([1,1,1,1])
    with colm1:
        day_m = st.number_input("Day (232–252)", min_value=232, max_value=252, value=232, step=1, key="t3_day")
    with colm2:
        period_m = st.radio("Period", ["morning","afternoon","night"], index=0, horizontal=True, key="t3_period")
    with colm3:
        stat_m = st.radio("Agg unit", ["Sum","Mean"], index=0, horizontal=True, key="t3_stat")
    with colm4:
        view_mode = st.selectbox(
            "View",
            ["Value: OBS","Value: ARIMA","Value: TensorTS","Value: LSTM",
             "Error (signed): ARIMA − OBS","Error (signed): TensorTS − OBS","Error (signed): LSTM − OBS",
             "Error (abs): ARIMA − OBS","Error (abs): TensorTS − OBS","Error (abs): LSTM − OBS"],
            index=0, key="t3_view"
        )

    # --- 解析檢視模式 & 載入資料（保持你原本的函式呼叫邏輯） ---
    def parse_view(mode: str):
        if mode.startswith("Value"):
            return ("value", mode.split(":")[1].strip().lower())
        elif mode.startswith("Error (signed)"):
            model = mode.split(":")[1].strip().split(" ")[0].lower()
            return ("err_signed", model)
        else:
            model = mode.split(":")[1].strip().split(" ")[0].lower()
            return ("err_abs", model)

    mode_kind, model_sel = parse_view(view_mode)
    if model_sel == "tensorts":
        model_sel = "tensor"

    df_model = None
    df_obs_m = None

    if mode_kind == "value":
        src = "obs" if model_sel == "obs" else model_sel
        df_model = load_period_od(src, day_m, period_m, stat=stat_m)
        if df_model is None:
            st.warning(f"找不到檔案或當日資料：{src} / {period_m}")
    else:
        df_model = load_period_od(model_sel, day_m, period_m, stat=stat_m)
        df_obs_m = load_period_od("obs", day_m, period_m, stat=stat_m)
        if df_model is None or df_obs_m is None:
            st.warning(f"找不到檔案或當日資料：{model_sel} / obs / {period_m}")
        else:
            key = ["origin_zone_id","dest_zone_id"]
            df_join = pd.merge(df_model, df_obs_m, on=key, how="outer", suffixes=("_m","_o")).fillna(0.0)
            if mode_kind == "err_signed":
                df_model = df_join[key + ["value_m","value_o"]].assign(value=lambda x: x["value_m"] - x["value_o"])[key+["value"]]
            else:
                df_model = df_join[key + ["value_m","value_o"]].assign(value=lambda x: (x["value_m"] - x["value_o"]).abs())[key+["value"]]

    # --- 畫熱圖（保持原本的 px.imshow 設定） ---
    if df_model is not None and not df_model.empty:
        mat = od_heatmap_matrix(df_model)
        y_labels = [zid_label(z) for z in mat.index]
        x_labels = [zid_label(z) for z in mat.columns]
        text_arr = (np.vectorize(lambda v: f"{v:.1f}")(mat.values)
                    if stat_m == "Mean" else
                    np.vectorize(lambda v: f"{int(round(v))}")(mat.values))

        if mode_kind == "err_signed":
            vmax = float(np.nanmax(np.abs(mat.values))) or 1.0
            fig = px.imshow(
                mat.values,
                color_continuous_scale="RdBu",
                zmin=-vmax, zmax=vmax,
                labels=dict(x="Destination", y="Origin", color="Error")
            )
        else:
            vmin = float(np.nanmin(mat.values)) if np.isfinite(mat.values).all() else 0.0
            vmax = float(np.nanmax(mat.values)) or 1.0
            if vmax == vmin: vmax = vmin + 1.0
            fig = px.imshow(
                mat.values,
                color_continuous_scale="Reds",
                zmin=vmin, zmax=vmax,
                labels=dict(
                    x="Destination",
                    y="Origin",
                    color=("Value" if mode_kind == "value" else "Abs Error")
                )
            )

        fig.update_traces(
            text=text_arr,
            texttemplate="%{text}",
            textfont_size=11,
            hovertemplate="Origin=%{y}<br>Destination=%{x}<br>Value=%{z}<extra></extra>"
        )
        fig.update_xaxes(tickmode="array", tickvals=list(range(len(x_labels))), ticktext=x_labels, side="top")
        fig.update_yaxes(tickmode="array", tickvals=list(range(len(y_labels))), ticktext=y_labels, autorange="reversed")
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=640, coloraxis_colorbar=dict(len=0.75))

        title_map = {
            "value": "Value",
            "err_signed": "Signed Error (Model − OBS)",
            "err_abs": "Absolute Error |Model − OBS|"
        }
        model_title = view_mode.split(":")[1].strip() if ":" in view_mode else view_mode
        st.markdown(f"**{title_map[mode_kind]} — {model_title}**  ·  Day **{day_m}** · Period **{period_m}** · Unit **{stat_m}**")
        st.plotly_chart(fig, use_container_width=True)

