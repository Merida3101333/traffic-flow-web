# -*- coding: utf-8 -*-
# map_utils.py         
# 地圖繪圖 & 標籤格式

from decimal import Decimal, ROUND_HALF_UP
import folium
from branca.colormap import linear

from config import ZONE_NAME

def format_label_half_up(val: float, digits: int) -> str:
    """
    half-up 四捨五入的字串格式化：
    - digits=0 → 整數
    - digits=1 → 一位小數
    - 皆含千分位
    """
    q = Decimal(str(val)).quantize(
        Decimal("1") if digits == 0 else Decimal(f"1.{'0'*digits}"),
        rounding=ROUND_HALF_UP
    )
    return f"{q:,.{digits}f}"

def zid_label(zid: int) -> str:
    # 兩行顯示：ID + 簡名
    name = ZONE_NAME.get(zid, str(zid))
    return f"{zid}\n{(name if len(name)<=22 else name[:22]+'…')}"

def make_map_with_values(
    title,
    gj,
    values,
    center,
    zoom,
    zone_centers,
    show_labels=True,
    label_digits=0,
    vmin=None,
    vmax=None
):
    # 色階範圍
    if values is not None and len(values) > 0:
        vmin = float(values.min()) if vmin is None else float(vmin)
        vmax = float(values.max()) if vmax is None else float(vmax)
        if vmax == vmin: vmax = vmin + 1.0
    else:
        vmin, vmax = 0.0, 1.0

    m = folium.Map(location=list(center), zoom_start=zoom, tiles="CartoDB positron")

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

    folium.GeoJson(
        gj,
        name=title,
        style_function=style_fn,
        highlight_function=lambda x: highlight,
        tooltip=tooltip
    ).add_to(m)

    # 中心值標籤（四捨五入）
    if show_labels and values is not None and len(values) > 0:
        for zid, val in values.items():
            if zid in zone_centers:
                lat, lng = zone_centers[zid]
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
