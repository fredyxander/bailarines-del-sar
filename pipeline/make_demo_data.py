"""Genera escenas SAR SINTÉTICAS para probar el visor (no son datos NISAR).

Generates SYNTHETIC SAR scenes to exercise the viewer. They are NOT NISAR
data and must never be presented as results. The viewer only shows them
with ?demo=1 and under a visible "synthetic demo" banner.

Modelo simple, en potencia lineal con speckle gamma (4 looks):
  - tierra: HH 0.08, HV 0.02;  agua: HH 0.010, HV 0.002
  - fecha 2: la laguna se expande (eco disminuye) y una franja de
    vegetación gana estructura (eco aumenta, más en HV)

Uso:
  python pipeline/make_demo_data.py            # escribe data/demo/*.tif
  # y luego, por polarización:
  python pipeline/change_detection.py data/demo/before_HHHH.tif data/demo/after_HHHH.tif \
      --site demo --site-name "Synthetic demo (not real data)" --pol HHHH \
      --before-info DEMO,SYNTHETIC,2026-06-20 --after-info DEMO,SYNTHETIC,2026-09-12 \
      --out-root web/demo --max-size 1200
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

# Grilla UTM 18N (EPSG:32618), 20 m, ~30 x 30 km cerca de la costa caribe colombiana.
EPSG, X0, Y0, DX, N = 32618, 555000.0, 1222000.0, 20.0, 1500


def scene(after: bool, pol: str, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:N, 0:N].astype("float32")
    lagoon = ((xx - 700) / 420) ** 2 + ((yy - 820) / 330) ** 2 < 1
    if after:
        lagoon |= ((xx - 700) / 560) ** 2 + ((yy - 820) / 450) ** 2 < 1
    land, water = (0.08, 0.010) if pol == "HHHH" else (0.02, 0.002)
    sigma = np.where(lagoon, water, land).astype("float32")
    # franja de vegetación en el noreste que gana estructura en la fecha 2
    band = (np.abs((xx - 1150) + 0.6 * (yy - 380)) < 90) & (yy < 650)
    if after:
        sigma = np.where(band & ~lagoon, sigma * (3.0 if pol == "HHHH" else 5.0), sigma)
    return (sigma * rng.gamma(4.0, 0.25, size=(N, N))).astype("float32")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data/demo")
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    transform = from_origin(X0, Y0, DX, DX)
    for pol in ("HHHH", "HVHV"):
        for when, after in (("before", False), ("after", True)):
            path = out / f"{when}_{pol}.tif"
            with rasterio.open(path, "w", driver="GTiff", width=N, height=N, count=1, dtype="float32",
                               crs=f"EPSG:{EPSG}", transform=transform, compress="deflate") as dst:
                dst.write(scene(after, pol, rng), 1)
                dst.update_tags(SYNTHETIC="true", note="Synthetic demo scene, not NISAR data")
            print(path)


if __name__ == "__main__":
    main()
