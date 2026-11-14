"""Pruebas del pipeline con datos sintéticos (sin pytest: python tests/test_pipeline.py).

1. Crea dos HDF5 con la estructura de NISAR GCOV (UTM 18N, HHHH), donde una
   laguna se expande entre fechas.
2. nisar_gcov_to_tif.py --list y la extracción recortada a un bbox.
3. change_detection.py: salidas, metadatos y % de disminución esperado.
4. Reglas de seguridad: colecciones/CRID distintos y fechas invertidas fallan.
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

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "pipeline"
N, X0, Y0, DX = 600, 560000.0, 1225000.0, 20.0


def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    if ok and p.returncode != 0:
        raise AssertionError(f"Falló: {' '.join(args)}\n{p.stdout}\n{p.stderr}")
    if not ok and p.returncode == 0:
        raise AssertionError(f"Debía fallar y no falló: {' '.join(args)}")
    return p


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
        print(f"ok  cambio detectado {got:.1f} % vs {expected:.1f} % esperado")

        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "x", "--pol", "HHHH", "--before-info", "BETA,P05000,2026-01-10",
            "--after-info", info_b, "--out-root", str(out), ok=False)
        print("ok  colecciones/CRID distintos -> rechazado")

        run(str(PIPE / "change_detection.py"), str(t / "a.tif"), str(t / "b.tif"),
            "--site", "x", "--pol", "HHHH", "--before-info", info_b,
            "--after-info", info_a, "--out-root", str(out), ok=False)
        print("ok  fechas invertidas -> rechazado")

    print("\nTodas las pruebas del pipeline pasaron.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
