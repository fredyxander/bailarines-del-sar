"""Convierte una polarización de un producto NISAR GCOV (HDF5) a GeoTIFF.

Convert one polarization of a NISAR GCOV (HDF5) product to a GeoTIFF that
`change_detection.py` can read. Only the requested area is read from disk.

1) Inspeccionar el archivo (rutas, polarizaciones, metadatos de identificación):
     python pipeline/nisar_gcov_to_tif.py data/escena.h5 --list

2) Extraer una polarización recortada a un bbox WGS84 (oeste,sur,este,norte):
     python pipeline/nisar_gcov_to_tif.py data/escena.h5 --pol HHHH \
         --bbox -74.65,10.65,-74.25,11.05 --out data/escena_HHHH.tif

Supuestos (verificar con --list en una escena real):
  - grilla en /science/LSAR/GCOV/grids/frequencyA (o frequencyB)
  - xCoordinates / yCoordinates: centros de píxel, 1D, en la proyección de la grilla
  - dataset `projection` con atributo `epsg_code` (o el EPSG como valor)
  - valores de retrodispersión en potencia lineal
Si alguna ruta difiere, use --grid para indicar el grupo correcto.
"""

from __future__ import annotations

import argparse
import re
import sys

import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

POL_RE = re.compile(r"^(HH|HV|VH|VV|RH|RV)(HH|HV|VH|VV|RH|RV)?$")


def list_file(f: h5py.File) -> None:
    print("== Datasets (ruta, forma, tipo) ==")

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            print(f"  /{name}  {obj.shape}  {obj.dtype}")

    f.visititems(visit)
    print("\n== Identificación (valores escalares) ==")
    for path in ("science/LSAR/identification", "science/SSAR/identification"):
        if path in f:
            for k, v in f[path].items():
                if isinstance(v, h5py.Dataset) and v.shape in ((), (1,)):
                    val = v[()]
                    if isinstance(val, bytes):
                        val = val.decode(errors="replace")
                    print(f"  {k}: {val}")
    print("\n== Grillas y polarizaciones encontradas ==")
    for g in find_grids(f):
        pols = [k for k in f[g] if POL_RE.match(k)]
        print(f"  /{g}: {pols}")


def find_grids(f: h5py.File) -> list[str]:
    grids = []

    def visit(name, obj):
        if isinstance(obj, h5py.Group) and "xCoordinates" in obj and "yCoordinates" in obj:
            grids.append(name)

    f.visititems(visit)
    return sorted(grids)


def read_epsg(grid: h5py.Group) -> int:
    if "projection" not in grid:
        raise SystemExit("No se encontró el dataset 'projection' en la grilla; revise con --list.")
    proj = grid["projection"]
    for key in ("epsg_code", "epsg"):
        if key in proj.attrs:
            return int(np.asarray(proj.attrs[key]).ravel()[0])
    return int(np.asarray(proj[()]).ravel()[0])


def index_range(coords: np.ndarray, lo: float, hi: float) -> tuple[int, int]:
    """Índices [i0, i1) de las coordenadas dentro de [lo, hi], sea cual sea el orden."""
    inside = np.nonzero((coords >= lo) & (coords <= hi))[0]
    if inside.size == 0:
        raise SystemExit("El bbox no intersecta la escena.")
    return int(inside.min()), int(inside.max()) + 1


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en la consola de Windows
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("h5", help="Archivo NISAR GCOV (.h5)")
    p.add_argument("--list", action="store_true", help="Mostrar estructura y salir")
    p.add_argument("--pol", help="Término de covarianza, p. ej. HHHH, HVHV, VVVV")
    p.add_argument("--grid", help="Grupo de la grilla (por defecto: el primero con esa polarización)")
    p.add_argument("--bbox", help="oeste,sur,este,norte en grados WGS84")
    p.add_argument("--out", help="GeoTIFF de salida")
    args = p.parse_args()

    with h5py.File(args.h5, "r") as f:
        if args.list:
            list_file(f)
            return
        if not (args.pol and args.out):
            p.error("--pol y --out son obligatorios (o use --list)")

        grids = [args.grid.strip("/")] if args.grid else [g for g in find_grids(f) if args.pol in f[g]]
        if not grids:
            sys.exit(f"Polarización {args.pol} no encontrada. Use --list para ver las disponibles.")
        grid = f[grids[0]]
        x = grid["xCoordinates"][()]
        y = grid["yCoordinates"][()]
        epsg = read_epsg(grid)
        crs = CRS.from_epsg(epsg)

        if args.bbox:
            w, s, e, n = (float(v) for v in args.bbox.split(","))
            xmin, ymin, xmax, ymax = transform_bounds("EPSG:4326", crs, w, s, e, n, densify_pts=21)
            c0, c1 = index_range(x, xmin, xmax)
            r0, r1 = index_range(y, ymin, ymax)
        else:
            c0, c1, r0, r1 = 0, x.size, 0, y.size

        data = grid[args.pol][r0:r1, c0:c1].astype("float32")
        xs, ys = x[c0:c1], y[r0:r1]
        dx = float(xs[1] - xs[0]) if xs.size > 1 else 1.0
        dy = float(ys[1] - ys[0]) if ys.size > 1 else -1.0
        if dy > 0:  # norte hacia abajo -> voltear para que la fila 0 sea el norte
            data, ys, dy = data[::-1], ys[::-1], -dy
        # Coordenadas = centros de píxel; el origen del GeoTIFF es la esquina superior izquierda.
        transform = from_origin(float(xs[0]) - dx / 2, float(ys[0]) - dy / 2, dx, -dy)

        data[~np.isfinite(data)] = np.nan
        with rasterio.open(
            args.out, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
            dtype="float32", crs=crs, transform=transform, nodata=np.nan, compress="deflate",
        ) as dst:
            dst.write(data, 1)
            dst.update_tags(source=args.h5.replace("\\", "/").split("/")[-1], grid="/" + grids[0], polarization=args.pol)

    print(f"{args.out}: {data.shape[1]}x{data.shape[0]} px, EPSG:{epsg}, {abs(dx):g} m")


if __name__ == "__main__":
    main()
