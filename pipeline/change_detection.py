"""Detección de cambios entre dos escenas SAR para el visor web.

Basado en el tutorial SAR en Python de la Agencia Espacial Canadiense
(ver tutorial/ y tutorial/LICENSE-CSA): mismo flujo rasterio + matplotlib,
extendido a dos fechas, filtro de speckle y salida para un mapa web.

Pasos:
  1. Lee las dos escenas (GeoTIFF; ver nisar_gcov_to_tif.py para NISAR GCOV),
     opcionalmente recortadas a un bbox WGS84.
  2. Las lleva a una grilla común en Web Mercator (EPSG:3857), promediando en
     potencia lineal (multilook) para no superar --max-size píxeles.
  3. Filtra el speckle (boxcar o Lee) con la ventana indicada.
  4. Convierte a dB y calcula el cambio como cociente: 10·log10(después/antes).
  5. Exporta PNG + meta.json en web/layers/<sitio>/<polarización>/ y
     actualiza web/layers/index.json.

Regla de seguridad: si las dos escenas tienen colección o CRID distintos el
script se detiene, porque el cambio sería un artefacto del procesamiento.

Ejemplo:
  python pipeline/change_detection.py data/a_HHHH.tif data/b_HHHH.tif \
      --site cienaga --site-name "Ciénaga Grande de Santa Marta" --pol HHHH \
      --before-info PROVISIONAL,P05023,2026-06-20 \
      --after-info  PROVISIONAL,P05023,2026-09-12 \
      --filter boxcar --window 5
"""

from __future__ import annotations

import argparse
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.warp import calculate_default_transform, reproject, transform_bounds  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

WEB_CRS = "EPSG:3857"


# ---------------------------------------------------------------- lectura ---

def parse_info(text: str, flag: str) -> dict:
    parts = [t.strip() for t in text.split(",")]
    if len(parts) != 3 or not all(parts):
        raise SystemExit(f"{flag} debe ser COLECCION,CRID,FECHA (p. ej. PROVISIONAL,P05023,2026-06-20)")
    collection, crid, date = parts
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"{flag}: la fecha debe ser AAAA-MM-DD, recibido '{date}'")
    return {"collection": collection.upper(), "crid": crid.upper(), "date": date}


def read_linear(path: str, band: int, bbox: tuple | None, is_db: bool) -> tuple[np.ndarray, dict]:
    """Lee la banda (recortada) en potencia lineal, con NaN como nodata."""
    with rasterio.open(path) as src:
        window = None
        if bbox:
            b = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21)
            window = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
            window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        data = src.read(band, window=window, masked=True).astype("float64").filled(np.nan)
        transform = src.window_transform(window) if window else src.transform
        prof = {"crs": src.crs, "transform": transform, "height": data.shape[0], "width": data.shape[1]}
    if is_db:
        data = np.power(10.0, data / 10.0)
    data[~np.isfinite(data) | (data <= 0)] = np.nan
    return data, prof


def web_grid(prof: dict, max_size: int) -> dict:
    """Grilla EPSG:3857 que cubre la escena, con lado mayor <= max_size."""
    bounds = rasterio.transform.array_bounds(prof["height"], prof["width"], prof["transform"])
    tr, w, h = calculate_default_transform(prof["crs"], WEB_CRS, prof["width"], prof["height"], *bounds)
    scale = max(w, h) / max_size
    if scale > 1:
        tr, w, h = calculate_default_transform(
            prof["crs"], WEB_CRS, prof["width"], prof["height"], *bounds,
            dst_width=int(round(w / scale)), dst_height=int(round(h / scale)),
        )
    return {"crs": WEB_CRS, "transform": tr, "width": w, "height": h}


def to_grid(data: np.ndarray, prof: dict, grid: dict) -> np.ndarray:
    out = np.full((grid["height"], grid["width"]), np.nan)
    reproject(
        source=data, destination=out,
        src_transform=prof["transform"], src_crs=prof["crs"],
        dst_transform=grid["transform"], dst_crs=grid["crs"],
        src_nodata=np.nan, dst_nodata=np.nan,
        resampling=Resampling.average,  # promedio en lineal = multilook
    )
    return out


# ------------------------------------------------------------- speckle ------

def box_mean(a: np.ndarray, w: int) -> np.ndarray:
    """Media en ventana w×w ignorando NaN (sumas acumuladas, sin SciPy)."""
    r = w // 2
    valid = np.isfinite(a)

    def box_sum(x):
        c = np.pad(x, ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
        return c[w:, w:] - c[:-w, w:] - c[w:, :-w] + c[:-w, :-w]

    s = box_sum(np.where(valid, a, 0.0))
    n = box_sum(valid.astype("float64"))
    with np.errstate(invalid="ignore", divide="ignore"):
        m = s / n
    m[~valid] = np.nan
    return m


def speckle_filter(a: np.ndarray, kind: str, w: int, enl: float) -> np.ndarray:
    if kind == "none" or w <= 1:
        return a
    m = box_mean(a, w)
    if kind == "boxcar":
        return m
    # Lee (1980): x̂ = m + k (a − m),  k = var_x / var_y
    var_y = box_mean(a * a, w) - m * m
    cu2 = 1.0 / enl
    var_x = np.clip((var_y - m * m * cu2) / (1.0 + cu2), 0, None)
    with np.errstate(invalid="ignore", divide="ignore"):
        k = np.where(var_y > 0, var_x / var_y, 0.0)
    return m + k * (a - m)


# -------------------------------------------------------------- salida -----

def to_db(a: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return 10.0 * np.log10(a)


def save_gray(arr: np.ndarray, path: Path, lo: float, hi: float) -> None:
    norm = np.clip((arr - lo) / (hi - lo), 0, 1)
    rgba = plt.get_cmap("gray")(np.nan_to_num(norm))
    rgba[..., 3] = np.isfinite(arr)
    plt.imsave(path, rgba)


def save_change(change: np.ndarray, path: Path, lim: float) -> None:
    """Rojo = aumento, azul = disminución; la opacidad crece con |cambio|."""
    norm = np.clip((change + lim) / (2 * lim), 0, 1)
    rgba = plt.get_cmap("RdBu_r")(np.nan_to_num(norm, nan=0.5))
    alpha = np.clip(np.abs(change) / lim, 0, 1) ** 0.6
    rgba[..., 3] = np.where(np.isfinite(change), alpha, 0)
    plt.imsave(path, rgba)


def update_index(root: Path, site: str, site_name: str, pol: str, meta: dict) -> None:
    idx_path = root / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"sites": []}
    entry = next((s for s in idx["sites"] if s["id"] == site), None)
    if entry is None:
        entry = {"id": site, "name": site_name, "polarizations": []}
        idx["sites"].append(entry)
    entry["name"] = site_name or entry["name"]
    entry["bounds"] = meta["bounds_wgs84"]
    if pol not in entry["polarizations"]:
        entry["polarizations"].append(pol)
    idx["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    idx_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")
    if not s:
        raise SystemExit(f"Identificador inválido: '{text}'")
    return s


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en la consola de Windows
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before", help="Raster de la fecha 1 (potencia lineal, salvo --db)")
    p.add_argument("after", help="Raster de la fecha 2")
    p.add_argument("--site", required=True, help="Identificador corto del sitio, p. ej. cienaga")
    p.add_argument("--site-name", default="", help="Nombre visible del sitio")
    p.add_argument("--pol", required=True, help="Polarización, p. ej. HHHH o HVHV")
    p.add_argument("--before-info", required=True, help="COLECCION,CRID,FECHA de la fecha 1")
    p.add_argument("--after-info", required=True, help="COLECCION,CRID,FECHA de la fecha 2")
    p.add_argument("--bbox", help="Recorte oeste,sur,este,norte en grados WGS84")
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--db", action="store_true", help="Los rasters ya están en dB")
    p.add_argument("--filter", choices=["boxcar", "lee", "none"], default="boxcar")
    p.add_argument("--window", type=int, default=5, help="Ventana del filtro en píxeles (impar)")
    p.add_argument("--enl", type=float, default=4.0, help="Número equivalente de looks (solo Lee)")
    p.add_argument("--threshold", type=float, default=3.0, help="|cambio| en dB considerado significativo")
    p.add_argument("--max-size", type=int, default=2048, help="Lado mayor de las imágenes web, en píxeles")
    p.add_argument("--out-root", default="web/layers")
    args = p.parse_args()

    if args.window % 2 == 0:
        p.error("--window debe ser impar")
    b_info = parse_info(args.before_info, "--before-info")
    a_info = parse_info(args.after_info, "--after-info")
    if (b_info["collection"], b_info["crid"]) != (a_info["collection"], a_info["crid"]):
        raise SystemExit(
            f"Colecciones distintas ({b_info['collection']}/{b_info['crid']} vs "
            f"{a_info['collection']}/{a_info['crid']}): el cambio sería un artefacto. No se calcula."
        )
    if b_info["date"] >= a_info["date"]:
        raise SystemExit("La fecha 'before' debe ser anterior a la fecha 'after'.")

    bbox = tuple(float(v) for v in args.bbox.split(",")) if args.bbox else None
    site, pol = slug(args.site), args.pol.upper()

    b_lin, b_prof = read_linear(args.before, args.band, bbox, args.db)
    a_lin, a_prof = read_linear(args.after, args.band, bbox, args.db)
    grid = web_grid(b_prof, args.max_size)
    b_lin = to_grid(b_lin, b_prof, grid)
    a_lin = to_grid(a_lin, a_prof, grid)

    b_f = speckle_filter(b_lin, args.filter, args.window, args.enl)
    a_f = speckle_filter(a_lin, args.filter, args.window, args.enl)
    b_db, a_db = to_db(b_f), to_db(a_f)
    change = a_db - b_db  # = 10·log10(después/antes)

    both = np.concatenate([b_db[np.isfinite(b_db)], a_db[np.isfinite(a_db)]])
    valid = np.isfinite(change)
    if both.size == 0 or not valid.any():
        raise SystemExit("No hay píxeles válidos comunes a las dos escenas en el área pedida.")
    lo, hi = (float(v) for v in np.percentile(both, [2, 98]))
    lim = max(float(np.percentile(np.abs(change[valid]), 98)), args.threshold)

    out = Path(args.out_root) / site / pol
    out.mkdir(parents=True, exist_ok=True)
    save_gray(b_db, out / "before.png", lo, hi)
    save_gray(a_db, out / "after.png", lo, hi)
    save_change(change, out / "change.png", lim)

    west, south, east, north = transform_bounds(WEB_CRS, "EPSG:4326", *rasterio.transform.array_bounds(
        grid["height"], grid["width"], grid["transform"]))
    sig = valid & (np.abs(change) >= args.threshold)
    n_valid = int(valid.sum())
    pixel_m = abs(grid["transform"].a)
    meta = {
        "site": site,
        "polarization": pol,
        "before": {**b_info, "file": Path(args.before).name},
        "after": {**a_info, "file": Path(args.after).name},
        "bounds_wgs84": {"west": west, "south": south, "east": east, "north": north},
        "processing": {
            "speckle_filter": args.filter,
            "window_px": args.window if args.filter != "none" else None,
            "window_m": round(args.window * pixel_m) if args.filter != "none" else None,
            "enl": args.enl if args.filter == "lee" else None,
            "web_pixel_m": round(pixel_m, 1),
            "change_formula": "10*log10(after/before)",
        },
        "display": {"db_range": [lo, hi], "change_limit_db": lim},
        "stats": {
            "threshold_db": args.threshold,
            "valid_pixels": n_valid,
            "pct_increase": round(100 * int((sig & (change > 0)).sum()) / n_valid, 2),
            "pct_decrease": round(100 * int((sig & (change < 0)).sum()) / n_valid, 2),
            "median_change_db": round(float(np.median(change[valid])), 2),
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    update_index(Path(args.out_root), site, args.site_name or site, pol, meta)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
