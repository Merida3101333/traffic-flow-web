# -*- coding: utf-8 -*-
# tab_compare_21d.py 
# Tab1

import streamlit as st
from streamlit_folium import st_folium

from data_utils import period_zone_values
from map_utils import make_map_with_values

def render(gj, center, global_zoom, show_labels, zone_centers):
    st.subheader("Compare last 21 days (Day 232–252) by Period")

    colc1, colc2, colc3, colc4 = st.columns([1,1,1,1])
    with colc1:
        day_21 = st.number_input("Day (232–252)", min_value=232, max_value=252,
                                 value=232, step=1, key="t1_day")
    with colc2:
        period = st.radio("Period", ["morning","afternoon","night"],
                          index=0, horizontal=True, key="t1_period")
    with colc3:
        agg_mode = st.selectbox("Aggregate to zone",
                                ["Origin sum (flow-out)","Destination sum (flow-in)","OD sum"],
                                index=0, key="t1_agg")
    with colc4:
        stat1 = st.radio("Period agg", ["Sum", "Mean"],
                         index=0, horizontal=True, key="t1_stat")

    v_obs    = period_zone_values("obs",    day_21, period, agg_mode, stat=stat1)
    v_arima  = period_zone_values("arima",  day_21, period, agg_mode, stat=stat1)
    v_tensor = period_zone_values("tensor", day_21, period, agg_mode, stat=stat1)
    v_lstm   = period_zone_values("lstm",   day_21, period, agg_mode, stat=stat1)

    vals_for_scale = [s for s in [v_obs, v_arima, v_tensor, v_lstm]
                      if s is not None and len(s) > 0]
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
        m1 = make_map_with_values("OBS", gj, v_obs, center, global_zoom,
                                  zone_centers, show_labels, label_digits_tab1,
                                  vmin=vmin, vmax=vmax)
        st_folium(m1, width=None, height=360)

    with c2:
        st.markdown(f"**ARIMA – {stat1}**")
        m2 = make_map_with_values("ARIMA", gj, v_arima, center, global_zoom,
                                  zone_centers, show_labels, label_digits_tab1,
                                  vmin=vmin, vmax=vmax)
        st_folium(m2, width=None, height=360)

    with c3:
        st.markdown(f"**TensorTS – {stat1}**")
        m3 = make_map_with_values("TensorTS", gj, v_tensor, center, global_zoom,
                                  zone_centers, show_labels, label_digits_tab1,
                                  vmin=vmin, vmax=vmax)
        st_folium(m3, width=None, height=360)

    with c4:
        st.markdown(f"**LSTM – {stat1}**")
        m4 = make_map_with_values("LSTM", gj, v_lstm, center, global_zoom,
                                  zone_centers, show_labels, label_digits_tab1,
                                  vmin=vmin, vmax=vmax)
        st_folium(m4, width=None, height=360)
