# -*- coding: utf-8 -*-
# data_utils.py         
# 讀 CSV、聚合邏輯（period/hour/OD）

import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

from config import DATA, ZONE_ORDER, HOURS_PER_PERIOD


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    """讀取 processed 資料夾底下的 csv（有 cache）。"""
    return pd.read_csv(DATA / name)


def get_period_file(model: str, period: str) -> Path | None:
    """
    回傳各模型 period 等級的檔案路徑：
      - LSTM: lstm_<period>_canonical_period.csv（每小時平均）
      - ARIMA: arima_<period>_canonical.csv（時段合計）
      - TensorTS: tensor_<period>_canonical.csv（時段合計）
      - OBS:   obs_period_canonical.csv（時段合計）
    """
    m = model.lower()

    if m == "lstm":
        return {
            "morning":   DATA / "lstm_morning_canonical_period.csv",
            "afternoon": DATA / "lstm_afternoon_canonical_period.csv",
            "night":     DATA / "lstm_night_canonical_period.csv",
        }.get(period)

    if m == "arima":
        return {
            "morning":   DATA / "arima_morning_canonical.csv",
            "afternoon": DATA / "arima_afternoon_canonical.csv",
            "night":     DATA / "arima_night_canonical.csv",
        }.get(period)

    if m in ["tensor", "tensors", "tensorts"]:
        return {
            "morning":   DATA / "tensor_morning_canonical.csv",
            "afternoon": DATA / "tensor_afternoon_canonical.csv",
            "night":     DATA / "tensor_night_canonical.csv",
        }.get(period)

    if m == "obs":
        return DATA / "obs_period_canonical.csv"

    return None


def period_zone_values(
    model: str,
    day_abs: int,
    period: str,
    agg_mode: str,
    stat: str = "Sum"
) -> pd.Series | None:
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
        g = pd.concat([g1, g2], axis=1).fillna(0.0).sum(axis=1)
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


def hourly_zone_values(
    df_obs_hourly: pd.DataFrame,
    day_abs: int,
    hours: list[int],
    agg_mode: str,
    stat: str = "Sum"
) -> pd.Series | None:
    """
    將 OBS 小時資料依「任意小時清單」彙整到每區。
    """
    sub = df_obs_hourly[
        (df_obs_hourly["day_abs"] == day_abs)
        & (df_obs_hourly["hour_abs"].isin(hours))
    ]
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


def load_period_od(
    model: str,
    day_abs: int,
    period: str,
    stat: str = "Sum"
) -> pd.DataFrame | None:
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

    # 逐小時/逐 slot → 彙總成「同日×同 period×同 OD 一列」
    vals = (
        df.groupby(["origin_zone_id", "dest_zone_id"], dropna=False)[val_col]
          .sum()
          .reset_index()
          .rename(columns={val_col: "value"})
    )

    # 單位換算
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

    # 補齊 6×6 所有 OD（避免 pivot 時有 NaN）
    all_pairs = pd.MultiIndex.from_product(
        [ZONE_ORDER, ZONE_ORDER],
        names=["origin_zone_id", "dest_zone_id"]
    )
    vals = (
        vals.set_index(["origin_zone_id", "dest_zone_id"])
            .reindex(all_pairs)
            .fillna(0.0)
            .reset_index()
    )

    return vals


def od_heatmap_matrix(df_od: pd.DataFrame) -> pd.DataFrame:
    """
    把 OD 長表轉成 6×6 矩陣（依 ZONE_ORDER 排序）
    """
    mat = df_od.pivot(
        index="origin_zone_id",
        columns="dest_zone_id",
        values="value"
    )
    mat = mat.reindex(index=ZONE_ORDER, columns=ZONE_ORDER)
    return mat.fillna(0.0)

