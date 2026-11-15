"""Tipos de cambio: agrupación sin etiquetas (k-means) del cambio HH + HV.

Change types: groups every pixel by how HH and HV changed together, then
names each group with **visible rules on its centroid** — no labelled data,
no prediction. The labels are interpretations of a backscatter change, not
ground truth, and the app says so.

Features per pixel (5x5-filtered, dB, native UTM grid):
    ΔHH = HH_after − HH_before,  ΔHV = HV_after − HV_before,  HH_before
Standardised, MiniBatchKMeans (k=6, fixed seed) fitted on a random sample.

Rules applied to each centroid (T = change threshold in dB, W = Otsu water
threshold of HH_before):
    ΔHH ≤ −T and ΔHV ≤ −T          → faded_both     (smoother or less vegetation, e.g. new open water)
    ΔHV ≥ T                         → grew_hv        (more structure, e.g. vegetation)
    ΔHH ≥ T and HH_before < W       → water_surface  (open water brighter in HH, HV flat)
    ΔHH ≥ T                         → land_rougher   (rougher or wetter ground)
    |ΔHH| < T and |ΔHV| < T         → stable         (no significant change)
    otherwise                       → ambiguous

    python pipeline/change_types.py data/before_HHHH.tif data/after_HHHH.tif \\
        data/before_HVHV.tif data/after_HVHV.tif --site cienaga

Writes web/layers/<site>/types.png (aligned with the other layers) and
web/layers/<site>/types.json, and marks the site with "types": true.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from change_detection import read_linear, speckle_filter, to_db, web_grid  # noqa: E402
from water_mask import otsu_threshold  # noqa: E402

# id: (colour, short EN, short ES, full EN, full ES). Wording matches why.json: an HH rise over
# water is read as "rougher or shallower surface", never as a proven cause.
CLASSES = {
    "water_surface": ("#ff5a4f", "Water surface brighter", "Agua más brillante",
                      "Open water brighter in HH, HV almost flat: a change at the water surface (rougher or shallower)",
                      "Agua abierta más brillante en HH, HV casi igual: cambio en la superficie del agua (más rugosa o más somera)"),
    "grew_hv": ("#3be3a0", "More structure", "Más estructura",
                "HV up (and HH): more structure, e.g. vegetation",
                "Sube HV (y HH): más estructura, p. ej. vegetación"),
    "faded_both": ("#4c9bff", "Both darker", "Ambos más oscuros",
                   "HH and HV down: smoother surface or less vegetation, e.g. new open water",
                   "Bajan HH y HV: superficie más lisa o menos vegetación, p. ej. agua nueva"),
    "land_rougher": ("#ffc23d", "Land brighter", "Suelo más brillante",
                     "HH up over land: rougher or wetter ground",
                     "Sube HH sobre tierra: suelo más rugoso o más húmedo"),
    "ambiguous": ("#b07cff", "Ambiguous", "Ambiguo", "Ambiguous change", "Cambio ambiguo"),
    "stable": (None, "No significant change", "Sin cambio", "No significant change", "Sin cambio significativo"),
}
ORDER = ["water_surface", "grew_hv", "faded_both", "land_rougher", "ambiguous", "stable"]


def name_centroid(d_hh: float, d_hv: float, hh_before: float, t: float, water_db: float) -> str:
    if d_hh <= -t and d_hv <= -t:
        return "faded_both"
    if d_hv >= t:
        return "grew_hv"
    if d_hh >= t and hh_before < water_db:
        return "water_surface"
    if d_hh >= t:
        return "land_rougher"
    if abs(d_hh) < t and abs(d_hv) < t:
        return "stable"
    return "ambiguous"


def cluster(d_hh, d_hv, hh_b, k: int, seed: int, sample: int, t: float, water_db: float):
    from sklearn.cluster import MiniBatchKMeans

    ok = np.isfinite(d_hh) & np.isfinite(d_hv) & np.isfinite(hh_b)
    x = np.stack([d_hh[ok], d_hv[ok], hh_b[ok]], axis=1)
    mu, sd = x.mean(0), x.std(0)
    sd[sd == 0] = 1.0
    xs = (x - mu) / sd
    rng = np.random.default_rng(seed)
    fit = xs[rng.choice(len(xs), min(sample, len(xs)), replace=False)]
    km = MiniBatchKMeans(n_clusters=k, random_state=seed, n_init=5, batch_size=8192).fit(fit)
    lab = km.predict(xs)
    cents = km.cluster_centers_ * sd + mu
    names = [name_centroid(c[0], c[1], c[2], t, water_db) for c in cents]
    cls = np.full(d_hh.shape, -1, dtype=np.int16)
    cls[ok] = np.array([ORDER.index(n) for n in names], dtype=np.int16)[lab]
    clusters = [{"cluster": int(i), "class": names[i], "pct": round(100 * float(np.mean(lab == i)), 2),
                 "centroid": {"d_hh_db": round(float(c[0]), 2), "d_hv_db": round(float(c[1]), 2),
                              "hh_before_db": round(float(c[2]), 2)}}
                for i, c in enumerate(cents)]
    return cls, clusters


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hh_before"); p.add_argument("hh_after"); p.add_argument("hv_before"); p.add_argument("hv_after")
    p.add_argument("--site", required=True)
    p.add_argument("--out-root", default="web/layers")
    p.add_argument("--filter", choices=["boxcar", "lee", "none"], default="boxcar")
    p.add_argument("--window", type=int, default=5)
    p.add_argument("--enl", type=float, default=4.0)
    p.add_argument("--threshold", type=float, default=3.0, help="Significant change in dB (approved in #15)")
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--sample", type=int, default=200_000)
    p.add_argument("--max-size", type=int, default=2048)
    args = p.parse_args()

    def filtered_db(path):
        lin, prof = read_linear(path, 1, None, False)
        return to_db(speckle_filter(lin, args.filter, args.window, args.enl)), prof

    hh_b, prof = filtered_db(args.hh_before)
    hh_a, prof_a = filtered_db(args.hh_after)
    hv_b, prof_vb = filtered_db(args.hv_before)
    hv_a, prof_va = filtered_db(args.hv_after)
    for other in (prof_a, prof_vb, prof_va):
        if other["transform"] != prof["transform"] or (other["height"], other["width"]) != (prof["height"], prof["width"]):
            raise SystemExit("Las cuatro escenas deben estar en la misma grilla nativa (mismo recorte).")

    water_db = otsu_threshold(hh_b)
    cls, clusters = cluster(hh_a - hh_b, hv_a - hv_b, hh_b, args.k, args.seed, args.sample, args.threshold, water_db)

    # Class raster → the same Web Mercator grid as the published layers (nearest neighbour).
    import matplotlib.pyplot as plt
    from rasterio.enums import Resampling
    from rasterio.transform import array_bounds
    from rasterio.warp import reproject, transform_bounds

    grid = web_grid(prof, args.max_size)
    web = np.full((grid["height"], grid["width"]), -1, dtype=np.int16)
    reproject(source=cls, destination=web, src_transform=prof["transform"], src_crs=prof["crs"],
              dst_transform=grid["transform"], dst_crs=grid["crs"], src_nodata=-1, dst_nodata=-1,
              resampling=Resampling.nearest)
    rgba = np.zeros(web.shape + (4,), dtype=np.float32)
    for i, key in enumerate(ORDER):
        color = CLASSES[key][0]
        if color:
            rgba[web == i, :3] = [int(color[j:j + 2], 16) / 255 for j in (1, 3, 5)]
            rgba[web == i, 3] = 0.85
    out = Path(args.out_root) / args.site
    out.mkdir(parents=True, exist_ok=True)
    plt.imsave(out / "types.png", rgba)

    valid = cls >= 0
    classes = []
    for i, key in enumerate(ORDER):
        pct = round(100 * float(np.sum(cls == i)) / max(int(valid.sum()), 1), 2)
        if pct > 0:
            color, short_en, short_es, en, es = CLASSES[key]
            classes.append({"id": key, "color": color, "short_en": short_en, "short_es": short_es,
                            "label_en": en, "label_es": es, "pct": pct})
    w, s, e, n = transform_bounds(grid["crs"], "EPSG:4326", *array_bounds(grid["height"], grid["width"], grid["transform"]))
    meta = {
        "method": "k-means (MiniBatchKMeans) on standardised [ΔHH, ΔHV, HH_before], 5x5 filtered dB, native UTM grid; "
                  "clusters named by rules on their centroids",
        "k": args.k, "seed": args.seed, "sample": args.sample,
        "threshold_db": args.threshold, "water_threshold_db": round(float(water_db), 2),
        "rules": ["ΔHH ≤ −T and ΔHV ≤ −T → faded_both", "ΔHV ≥ T → grew_hv",
                  "ΔHH ≥ T and HH_before < W → water_surface", "ΔHH ≥ T → land_rougher",
                  "|ΔHH| < T and |ΔHV| < T → stable", "otherwise → ambiguous"],
        "classes": classes, "clusters": clusters,
        "bounds_wgs84": {"west": w, "south": s, "east": e, "north": n},
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reviewed_by": None,
    }
    (out / "types.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    idx_path = Path(args.out_root) / "index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        for site in idx["sites"]:
            if site["id"] == args.site:
                site["types"] = True
        idx_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"water_threshold_db": meta["water_threshold_db"], "classes": classes}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
