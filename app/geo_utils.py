# -*- coding: utf-8 -*-
# geo_utils.py          
# 讀 GeoJSON、算 center/bounds/centroids

import json

def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def guess_center(geojson):
    try:
        from shapely.geometry import shape
        feats = geojson.get("features", [])
        if feats:
            c = shape(feats[0]["geometry"]).centroid
            return float(c.y), float(c.x)
    except Exception:
        pass
    # fallback: Times Square
    return 40.758, -73.985

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

