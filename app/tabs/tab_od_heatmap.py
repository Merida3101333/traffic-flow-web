# -*- coding: utf-8 -*-
# tab_od_heatmap.py    
# Tab2

import numpy as np
import streamlit as st
import plotly.express as px

from data_utils import load_period_od, od_heatmap_matrix
from map_utils import zid_label


def render():
    st.subheader("OD Matrix Heatmap — Period level (Day 232–252)")

    # ── 說明面板：Value / Error 定義與用法 ─────────────────────────────
    with st.expander("ℹ️ 什麼是 Value / Error？（點此展開說明）", expanded=False):
        st.markdown("""
        **你可以用上方的 Day / Period / Unit (Sum / Mean) 搭配下拉選單切換要看的內容。**
        - Value: 顯示各 OD pair 的預測值 / 真實值
        - Error (signed): Model − OBS（帶正負號，紅=低估、藍=高估）
        - Error (abs): |Model − OBS|（誤差大小，不看方向）

        這個熱圖可以幫你：
        1. 看某個模型在特定時段，哪幾個 OD pair 反覆預測得不好
        2. 比較不同模型在相同 Day / Period 下，誤差空間分布的差異
        """)

    # --- 控制列：與 Tab1 同步的概念，但獨立 widgets ---
    colm1, colm2, colm3, colm4 = st.columns([1, 1, 1, 1])
    with colm1:
        day_m = st.number_input(
            "Day (232–252)",
            min_value=232,
            max_value=252,
            value=232,
            step=1,
            key="t3_day"
        )
    with colm2:
        period_m = st.radio(
            "Period",
            ["morning", "afternoon", "night"],
            index=0,
            horizontal=True,
            key="t3_period"
        )
    with colm3:
        stat_m = st.radio(
            "Agg unit",
            ["Sum", "Mean"],
            index=0,
            horizontal=True,
            key="t3_stat"
        )
    with colm4:
        view_mode = st.selectbox(
            "View",
            [
                "Value: OBS", "Value: ARIMA", "Value: TensorTS", "Value: LSTM",
                "Error (signed): ARIMA − OBS", "Error (signed): TensorTS − OBS", "Error (signed): LSTM − OBS",
                "Error (abs): ARIMA − OBS", "Error (abs): TensorTS − OBS", "Error (abs): LSTM − OBS"
            ],
            index=0,
            key="t3_view"
        )

    # --- 解析檢視模式 ---
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

    # --- 根據 view_mode 載入資料 ---
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
            key = ["origin_zone_id", "dest_zone_id"]
            df_join = (
                df_model.merge(df_obs_m, on=key, how="outer", suffixes=("_m", "_o"))
                       .fillna(0.0)
            )
            if mode_kind == "err_signed":
                df_model = df_join[key + ["value_m", "value_o"]].assign(
                    value=lambda x: x["value_m"] - x["value_o"]
                )[key + ["value"]]
            else:
                df_model = df_join[key + ["value_m", "value_o"]].assign(
                    value=lambda x: (x["value_m"] - x["value_o"]).abs()
                )[key + ["value"]]

    # --- 畫熱圖 ---
    if df_model is not None and not df_model.empty:
        mat = od_heatmap_matrix(df_model)
        y_labels = [zid_label(z) for z in mat.index]
        x_labels = [zid_label(z) for z in mat.columns]

        # 文字標籤：Sum → 整數；Mean → 一位小數
        text_arr = (
            np.vectorize(lambda v: f"{v:.1f}")(mat.values)
            if stat_m == "Mean"
            else np.vectorize(lambda v: f"{int(round(v))}")(mat.values)
        )

        if mode_kind == "err_signed":
            vmax = float(np.nanmax(np.abs(mat.values))) or 1.0
            fig = px.imshow(
                mat.values,
                color_continuous_scale="RdBu",
                zmin=-vmax,
                zmax=vmax,
                labels=dict(x="Destination", y="Origin", color="Error")
            )
        else:
            vmin = float(np.nanmin(mat.values)) if np.isfinite(mat.values).all() else 0.0
            vmax = float(np.nanmax(mat.values)) or 1.0
            if vmax == vmin:
                vmax = vmin + 1.0
            fig = px.imshow(
                mat.values,
                color_continuous_scale="Reds",
                zmin=vmin,
                zmax=vmax,
                labels=dict(
                    x="Destination",
                    y="Origin",
                    color=("Value" if mode_kind == "value" else "Abs Error"),
                ),
            )

        fig.update_traces(
            text=text_arr,
            texttemplate="%{text}",
            textfont_size=11,
            hovertemplate="Origin=%{y}<br>Destination=%{x}<br>Value=%{z}<extra></extra>",
        )
        fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(len(x_labels))),
            ticktext=x_labels,
            side="top",
        )
        fig.update_yaxes(
            tickmode="array",
            tickvals=list(range(len(y_labels))),
            ticktext=y_labels,
            autorange="reversed",
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=40, b=10),
            height=640,
            coloraxis_colorbar=dict(len=0.75),
        )

        title_map = {
            "value": "Value",
            "err_signed": "Signed Error (Model − OBS)",
            "err_abs": "Absolute Error |Model − OBS|",
        }
        model_title = view_mode.split(":")[1].strip() if ":" in view_mode else view_mode

        st.markdown(
            f"**{title_map[mode_kind]} — {model_title}**  ·  "
            f"Day **{day_m}** · Period **{period_m}** · Unit **{stat_m}**"
        )
        st.plotly_chart(fig, use_container_width=True)

