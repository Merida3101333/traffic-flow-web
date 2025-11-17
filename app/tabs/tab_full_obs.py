# -*- coding: utf-8 -*-
# tab_full_obs.py 
# Tab3

import time

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from data_utils import load_csv, hourly_zone_values
from map_utils import make_map_with_values

def render(gj, center, global_zoom, show_labels, zone_centers, global_bounds=None):
    st.subheader("OBS – Full 252 days (Hourly / Range & Animation)")

    df_obs_hourly = load_csv("obs_hourly_canonical.csv")

    # 初始化 session_state
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

    # 控制列
    colh1, colh2, colh3 = st.columns([1, 2, 1])
    with colh1:
        d_full = st.number_input(
            "Day (1–252)",
            min_value=1,
            max_value=252,
            value=1,
            step=1,
        )
        agg_mode2 = st.selectbox(
            "Aggregate to zone",
            ["Origin sum (flow-out)", "Destination sum (flow-in)", "OD sum"],
            index=0,
        )
        stat2 = st.radio(
            "Hour agg", ["Sum", "Mean"],
            horizontal=True,
            index=0,
        )

    with colh2:
        h_start, h_end = st.slider(
            "Hour range (1–24)",
            min_value=1,
            max_value=24,
            value=(1, 6),
            step=1,
        )
        hours_range = list(range(h_start, h_end + 1))
        st.caption(f"區間小時：{hours_range}")

    # 如果 Day 或 Hour range 被改變，重設動畫起點
    if (d_full != st.session_state.prev_day) or (
        (h_start, h_end) != st.session_state.prev_range
    ):
        st.session_state.prev_day = d_full
        st.session_state.prev_range = (h_start, h_end)
        st.session_state.anim_hour = h_start
        st.session_state.anim_hour_widget = h_start

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

        st.slider(
            "Current hour",
            1,
            24,
            value=st.session_state.anim_hour_widget,
            step=1,
            key="anim_hour_widget",
            on_change=_sync_anim_from_widget,
        )

    # 左右兩張地圖
    left, right = st.columns(2)

    # 左：任意小時區間 Sum / Mean
    with left:
        v_range = hourly_zone_values(
            df_obs_hourly,
            d_full,
            hours_range,
            agg_mode2,
            stat2,
        )
        title_l = f"OBS – Day {d_full}, Hours {h_start}-{h_end} ({stat2})"
        label_digits_left = 0 if stat2 == "Sum" else 1

        mL = make_map_with_values(
            title_l,
            gj,
            v_range,
            center=center,
            zoom=global_zoom,
            zone_centers=zone_centers,
            show_labels=show_labels,
            label_digits=label_digits_left,
        )
        st_folium(
            mL,
            width=None,
            height=520,
            key=f"left_map_{d_full}_{h_start}_{h_end}_{agg_mode2}_{stat2}",
        )

    # 右：單一小時 + 動畫
    with right:
        cur_h = st.session_state.anim_hour
        df_sel = df_obs_hourly[
            (df_obs_hourly["day_abs"] == d_full)
            & (df_obs_hourly["hour_abs"] == cur_h)
        ]

        if agg_mode2 == "Origin sum (flow-out)":
            v_single = df_sel.groupby("origin_zone_id")["count"].sum()
        elif agg_mode2 == "Destination sum (flow-in)":
            v_single = df_sel.groupby("dest_zone_id")["count"].sum()
        else:  # OD sum
            g1 = df_sel.groupby("origin_zone_id")["count"].sum().rename("o")
            g2 = df_sel.groupby("dest_zone_id")["count"].sum().rename("d")
            v_single = (
                pd.concat([g1, g2], axis=1)
                  .fillna(0.0)
                  .sum(axis=1)
            )

        v_single.index.name = "zone_id"

        title_r = f"OBS – Day {d_full}, Hour {cur_h}"
        mR = make_map_with_values(
            title_r,
            gj,
            v_single,
            center=center,
            zoom=global_zoom,
            zone_centers=zone_centers,
            show_labels=show_labels,
            label_digits=0,  # 單一小時為整數
        )
        st_folium(
            mR,
            width=None,
            height=520,
            key=f"right_map_{d_full}_{cur_h}_{agg_mode2}",
        )
        st.markdown(f"**Frame hour:** {cur_h}")

    st.caption("左：任意小時區間（Sum/Mean）。右：單一小時，可播放動畫。")

    # 處理動畫：下一個 frame
    if animate and st.session_state.anim_running:
        time.sleep(speed)
        nxt = st.session_state.anim_hour + 1
        if nxt > h_end or nxt < h_start:
            nxt = h_start
        st.session_state.anim_hour = nxt
        st.rerun()



