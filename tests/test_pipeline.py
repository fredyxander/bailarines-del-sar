"""Pruebas del pipeline con datos sintéticos (sin pytest: python tests/test_pipeline.py).

1. Crea dos HDF5 con la estructura de NISAR GCOV (UTM 18N, HHHH), donde una
   laguna se expande entre fechas.
2. nisar_gcov_to_tif.py --list y la extracción recortada a un bbox.
3. change_detection.py: salidas, metadatos y % de disminución esperado.
4. Reglas de seguridad: colecciones/CRID distintos y fechas invertidas fallan.
5. Máscara de agua HHHH: área conocida en la grilla UTM, nodata, CRS y HVHV.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.water_mask import (  # noqa: E402
    measure_water,
    otsu_threshold,
    pixel_area_m2,
    water_area_km2,
    water_mask,
)

PIPE = ROOT / "pipeline"
N, X0, Y0, DX = 600, 560000.0, 1225000.0, 20.0
WATER_KEYS = (
    "water_km2_before",
    "water_km2_after",
    "water_threshold_db_before",
    "water_threshold_db_after",
)


def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    if ok and p.returncode != 0:
        raise AssertionError(f"Falló: {' '.join(args)}\n{p.stdout}\n{p.stderr}")
    if not ok and p.returncode == 0:
        raise AssertionError(f"Debía fallar y no falló: {' '.join(args)}")
    return p


def circle(radius: float) -> np.ndarray:
    yy, xx = np.mgrid[0:N, 0:N]
    return (xx - 300) ** 2 + (yy - 300) ** 2 < radius ** 2


def km2_of(count: int) -> float:
    return count * DX * DX / 1_000_000.0


def test_water_library() -> None:
    """Área conocida, nodata y CRS, sin pasar por el visor web."""
    crs = CRS.from_epsg(32618)
    transform = from_origin(X0, Y0, DX, DX)
    db_water = 10.0 * np.log10(0.01)
    db_land = 10.0 * np.log10(0.08)

    for radius in (120.0, 200.0):
        wet = circle(radius)
        linear = np.where(wet, 0.01, 0.08)
        measured = measure_water(linear, transform, crs)
        expected = km2_of(int(wet.sum()))
        assert measured["pixels"] == int(wet.sum())
        assert abs(measured["km2"] - expected) < 1e-9, (radius, measured["km2"], expected)
        assert db_water < measured["threshold_db"] < db_land
        db = 10.0 * np.log10(linear)
        assert np.array_equal(water_mask(db, otsu_threshold(db)), wet)
    small = measure_water(np.where(circle(120), 0.01, 0.08), transform, crs)
    print(f"ok  área conocida r=120 px -> {small['km2']:.4f} km² ({small['pixels']} px)")

    wet = circle(80)
    hole = np.zeros_like(wet)
    hole[300:310, 300:310] = True
    assert int((hole & wet).sum()) == 100
    linear = np.where(wet, 0.01, 0.08).astype("float64")
    linear[hole] = np.nan
    measured = measure_water(linear, transform, crs)
    kept = int((wet & ~hole).sum())
    assert measured["pixels"] == kept
    assert abs(measured["km2"] - km2_of(kept)) < 1e-9
    print("ok  nodata excluido del área y del histograma")

    linear = np.full((32, 32), 0.08)
    linear[0, :] = 0.01
    linear[1, 0] = 0.0
    linear[1, 1] = -0.2
    assert measure_water(linear, transform, crs)["pixels"] == 32
    print("ok  ceros y negativos no cuentan como agua")

    constant = measure_water(np.full((16, 16), 0.05), transform, crs)
    assert constant["pixels"] == 0 and constant["km2"] == 0.0
    print("ok  escena constante -> 0 km²")

    try:
        measure_water(np.full((8, 8), np.nan), transform, crs)
        raise AssertionError("debía fallar sin valores finitos")
    except ValueError as exc:
        assert "finitos" in str(exc)
    print("ok  escena sin datos válidos -> error")

    try:
        pixel_area_m2(transform, CRS.from_epsg(4326))
        raise AssertionError("EPSG:4326 debía rechazarse")
    except ValueError as exc:
        assert "metros" in str(exc)
    print("ok  CRS geográfico rechazado")

    foot = CRS.from_wkt(
        'PROJCS["test-ft",GEOGCS["WGS 84",DATUM["WGS_84",'
        'SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
        'UNIT["degree",0.0174532925199433]],PROJECTION["Mercator_1SP"],'
        'PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],'
        'PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
        'UNIT["foot",0.3048],AXIS["Easting",EAST],AXIS["Northing",NORTH]]'
    )
    try:
        pixel_area_m2(transform, foot)
        raise AssertionError("CRS en pies debía rechazarse")
    except ValueError as exc:
        assert "metros" in str(exc)
    print("ok  CRS no métrico rechazado")

    rotated = Affine(20, 5, 0, 4, -20, 0)  # |det| = 420 m²
    one = water_area_km2(np.ones((1, 1), dtype=bool), rotated, crs)
    assert abs(one - 420 / 1_000_000) < 1e-12, one
    assert abs(pixel_area_m2(transform, crs) - DX * DX) < 1e-9
    print("ok  área del píxel = |det(afín nativo)| en m²")


def write_clean_tif(path: Path, radius: float, transform, crs) -> int:
    wet = circle(radius)
    data = np.where(wet, np.float32(0.01), np.float32(0.08))
    with rasterio.open(
        path, "w", driver="GTiff", width=N, height=N, count=1, dtype="float32",
        crs=crs, transform=transform, nodata=np.nan,
    ) as dst:
        dst.write(data, 1)
    return int(wet.sum())


def test_water_pipeline() -> None:
    """El km² del CLI sale de la grilla nativa y solo para HHHH."""
    crs = CRS.from_epsg(32618)
    transform = from_origin(X0, Y0, DX, DX)
    info_a, info_b = "PROVISIONAL,P05023,2026-06-20", "PROVISIONAL,P05023,2026-09-12"
    db_water = 10.0 * np.log10(0.01)
    db_land = 10.0 * np.log10(0.08)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        expect_before = km2_of(write_clean_tif(t / "a.tif", 120, transform, crs))
        expect_after = km2_of(write_clean_tif(t / "b.tif", 200, transform, crs))
        seen = {}
        for max_size in (64, 512):
            out = t / f"layers-{max_size}"
            run(
                str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
                "--site", "agua", "--pol", "HHHH", "--before-info", info_a, "--after-info", info_b,
                "--filter", "none", "--max-size", str(max_size), "--out-root", str(out),
            )
            stats = json.loads((out / "agua" / "HHHH" / "meta.json").read_text(encoding="utf-8"))["stats"]
            assert stats["threshold_db"] == 3.0
            for key in WATER_KEYS:
                assert key in stats, key
            assert abs(stats["water_km2_before"] - expect_before) < 5e-4, stats["water_km2_before"]
            assert abs(stats["water_km2_after"] - expect_after) < 5e-4, stats["water_km2_after"]
            assert db_water < stats["water_threshold_db_before"] < db_land
            assert db_water < stats["water_threshold_db_after"] < db_land
            seen[max_size] = (stats["water_km2_before"], stats["water_km2_after"])
        assert seen[64] == seen[512]
        print(
            f"ok  km² nativo {seen[64][0]} -> {seen[64][1]} "
            f"(igual con --max-size 64 y 512)"
        )

        out = t / "hvhv"
        run(
            str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "agua", "--pol", "HVHV", "--before-info", info_a, "--after-info", info_b,
            "--filter", "none", "--out-root", str(out),
        )
        stats = json.loads((out / "agua" / "HVHV" / "meta.json").read_text(encoding="utf-8"))["stats"]
        for key in WATER_KEYS:
            assert key not in stats, key
        print("ok  HVHV no escribe área de agua")


def make_h5(path: Path, radius: float, rng: np.random.Generator) -> None:
    yy, xx = np.mgrid[0:N, 0:N]
    water = (xx - 300) ** 2 + (yy - 300) ** 2 < radius ** 2
    hh = np.where(water, 0.01, 0.08) * rng.gamma(4, 0.25, (N, N))
    with h5py.File(path, "w") as f:
        g = f.create_group("science/LSAR/GCOV/grids/frequencyA")
        g["HHHH"] = hh.astype("f4")
        g["xCoordinates"] = X0 + DX * (np.arange(N) + 0.5)
        g["yCoordinates"] = Y0 - DX * (np.arange(N) + 0.5)
        proj = g.create_dataset("projection", data=np.uint32(32618))
        proj.attrs["epsg_code"] = 32618


def main() -> None:
    test_water_library()
    rng = np.random.default_rng(7)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        make_h5(t / "a.h5", 120, rng)
        make_h5(t / "b.h5", 200, rng)

        listing = run(str(PIPE / "nisar_gcov_to_tif.py"), str(t / "a.h5"), "--list").stdout
        assert "HHHH" in listing and "frequencyA" in listing, listing
        print("ok  --list muestra grilla y polarización")

        # bbox que cubre toda la escena sintética (≈ -74.45..-74.34, 10.97..11.08)
        bbox = "-74.5,10.9,-74.3,11.2"
        for name in ("a", "b"):
            run(str(PIPE / "nisar_gcov_to_tif.py"), str(t / f"{name}.h5"), "--pol", "HHHH",
                "--bbox", bbox, "--out", str(t / f"{name}.tif"))
        with rasterio.open(t / "a.tif") as src:
            assert src.crs.to_epsg() == 32618, src.crs
            assert src.shape == (N, N), src.shape
            assert abs(src.transform.a - DX) < 1e-6 and abs(src.transform.c - X0) < 1e-6
        print("ok  conversión GCOV -> GeoTIFF con georreferencia correcta")

        info_a, info_b = "PROVISIONAL,P05023,2026-06-20", "PROVISIONAL,P05023,2026-09-12"
        out = t / "layers"
        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "test", "--pol", "HHHH", "--before-info", info_a, "--after-info", info_b,
            "--out-root", str(out))
        d = out / "test" / "HHHH"
        for f in ("before.png", "after.png", "change.png", "meta.json"):
            assert (d / f).stat().st_size > 0, f
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        idx = json.loads((out / "index.json").read_text(encoding="utf-8"))
        assert idx["sites"][0]["polarizations"] == ["HHHH"]
        assert meta["before"]["crid"] == meta["after"]["crid"] == "P05023"
        expected = 100 * np.pi * (200 ** 2 - 120 ** 2) / N ** 2  # anillo inundado
        got = meta["stats"]["pct_decrease"]
        assert abs(got - expected) < 2.0, (got, expected)
        assert meta["stats"]["pct_increase"] < 0.5, meta["stats"]
        for key in WATER_KEYS:
            assert key in meta["stats"], key
        assert meta["stats"]["water_km2_after"] > meta["stats"]["water_km2_before"] > 0
        print(f"ok  cambio detectado {got:.1f} % vs {expected:.1f} % esperado")
        print(
            f"ok  agua con speckle {meta['stats']['water_km2_before']} -> "
            f"{meta['stats']['water_km2_after']} km²"
        )

        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "recorte", "--pol", "HHHH", "--before-info", info_a, "--after-info", info_b,
            "--bbox", "-74.42,10.99,-74.37,11.04", "--out-root", str(out))
        assert (out / "recorte" / "HHHH" / "change.png").exists()
        print("ok  --bbox con longitudes negativas (oeste) en change_detection")

        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "x", "--pol", "HHHH", "--before-info", "BETA,P05000,2026-01-10",
            "--after-info", info_b, "--out-root", str(out), ok=False)
        print("ok  colecciones/CRID distintos -> rechazado")

        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "x", "--pol", "HHHH", "--before-info", info_b,
            "--after-info", info_a, "--out-root", str(out), ok=False)
        print("ok  fechas invertidas -> rechazado")

    test_water_pipeline()
    print("\nTodas las pruebas del pipeline pasaron.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
