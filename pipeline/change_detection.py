"""Detección de cambios entre dos escenas SAR (NISAR u otra misión).

Basado en el tutorial SAR en Python de la Agencia Espacial Canadiense
(ver tutorial/ y tutorial/LICENSE-CSA): mismo flujo rasterio + matplotlib,
extendido a dos fechas.

Entrada: dos rasters legibles por GDAL. Puede ser un GeoTIFF o un subdataset
HDF5, p. ej.  'HDF5:"archivo.h5"://ruta/al/dataset'  (la ruta exacta del
dataset depende del producto NISAR: confirmarla con `gdalinfo archivo.h5`).

Salida (en --out):
  before.png, after.png  -> retrodispersión en dB, escala de grises común
  change.png             -> diferencia en dB (después - antes), azul/rojo
  meta.json              -> fechas, límites en WGS84 y estadísticas

Uso:
  python pipeline/change_detection.py antes.tif despues.tif --out web/layers \
      --label-before 2026-06-20 --label-after 2026-09-15
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject, transform_bounds  # noqa: E402

EPS = 1e-10


def read_band(path: str, band: int) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        data = src.read(band, masked=True).astype("float64")
        profile = {
            "crs": src.crs,
            "transform": src.transform,
            "width": src.width,
            "height": src.height,
            "bounds": src.bounds,
        }
    return data.filled(np.nan), profile


def align_to(data: np.ndarray, src_prof: dict, dst_prof: dict) -> np.ndarray:
    """Remuestrea `data` a la grilla de `dst_prof` si las grillas no coinciden."""
    same = (
        src_prof["crs"] == dst_prof["crs"]
        and src_prof["transform"] == dst_prof["transform"]
        and src_prof["width"] == dst_prof["width"]
        and src_prof["height"] == dst_prof["height"]
    )
    if same:
        return data
    out = np.full((dst_prof["height"], dst_prof["width"]), np.nan)
    reproject(
        source=data,
        destination=out,
        src_transform=src_prof["transform"],
        src_crs=src_prof["crs"],
        dst_transform=dst_prof["transform"],
        dst_crs=dst_prof["crs"],
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return out


def to_db(data: np.ndarray, already_db: bool) -> np.ndarray:
    if already_db:
        return data
    with np.errstate(invalid="ignore", divide="ignore"):
        return 10.0 * np.log10(np.where(data > 0, data, np.nan) + EPS)


def save_png(arr: np.ndarray, path: Path, cmap: str, vmin: float, vmax: float) -> None:
    plt.imsave(path, np.ma.masked_invalid(arr), cmap=cmap, vmin=vmin, vmax=vmax)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before", help="Raster de la fecha 1")
    p.add_argument("after", help="Raster de la fecha 2")
    p.add_argument("--out", default="web/layers", help="Carpeta de salida")
    p.add_argument("--band", type=int, default=1, help="Banda a leer (default 1)")
    p.add_argument("--db", action="store_true", help="Los datos ya están en dB (no convertir)")
    p.add_argument("--threshold", type=float, default=3.0, help="|cambio| en dB considerado significativo")
    p.add_argument("--label-before", default="Fecha 1")
    p.add_argument("--label-after", default="Fecha 2")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    b_raw, b_prof = read_band(args.before, args.band)
    a_raw, a_prof = read_band(args.after, args.band)
    a_raw = align_to(a_raw, a_prof, b_prof)

    b_db = to_db(b_raw, args.db)
    a_db = to_db(a_raw, args.db)
    change = a_db - b_db

    # Escala de grises común para que antes/después sean comparables.
    both = np.concatenate([b_db[np.isfinite(b_db)], a_db[np.isfinite(a_db)]])
    if both.size == 0:
        raise SystemExit("No hay píxeles válidos en las escenas.")
    lo, hi = np.percentile(both, [2, 98])
    lim = float(np.nanpercentile(np.abs(change), 98)) or 1.0

    save_png(b_db, out / "before.png", "gray", lo, hi)
    save_png(a_db, out / "after.png", "gray", lo, hi)
    save_png(change, out / "change.png", "RdBu_r", -lim, lim)

    valid = np.isfinite(change)
    sig = valid & (np.abs(change) >= args.threshold)
    west, south, east, north = transform_bounds(b_prof["crs"], "EPSG:4326", *b_prof["bounds"])
    meta = {
        "before": {"label": args.label_before, "source": Path(args.before).name},
        "after": {"label": args.label_after, "source": Path(args.after).name},
        "bounds_wgs84": {"west": west, "south": south, "east": east, "north": north},
        "db_range_display": [float(lo), float(hi)],
        "change_range_display": [-lim, lim],
        "threshold_db": args.threshold,
        "pct_increase": float(100 * np.sum(sig & (change > 0)) / max(valid.sum(), 1)),
        "pct_decrease": float(100 * np.sum(sig & (change < 0)) / max(valid.sum(), 1)),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
