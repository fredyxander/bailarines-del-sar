# Datos usados / Data used

Escenas NISAR descargadas de [ASF Vertex](https://search.asf.alaska.edu) (requiere cuenta Earthdata Login).

- Colección: **PROVISIONAL** (17 jun – 23 oct 2026)
- ⚠️ No usar fechas entre el **27 jul y el 10 ago 2026** (hueco permanente del instrumento)

| Zona | Rol | Fecha | Colección | CRID | Track / frame · ciclo | Polarizaciones | Granule (ASF) |
|---|---|---|---|---|---|---|---|
| Ciénaga Grande de Santa Marta | antes | 2026-06-22 10:31:54Z | PROVISIONAL | P05023 | 119 A · 007 · ciclo 023 | DHDH: HHHH, HVHV | [`…_023_119_A_007_…_20260622T103154_…`](https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001/NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001.h5) |
| Ciénaga Grande de Santa Marta | después | 2026-10-20 10:31:48Z | PROVISIONAL | P05023 | 119 A · 007 · ciclo 033 | DHDH: HHHH, HVHV | [`…_033_119_A_007_…_20261020T103148_…`](https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001/NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001.h5) |

- Granules completos (colección ASF `NISAR_L2_GCOV_PROVISIONAL_V1`):
  - antes: `NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001`
  - después: `NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001`
- Para descargarlos se necesita una cuenta Earthdata Login (gratuita). Los `.h5` no se suben al repositorio.
- Zona: `-74.70,10.75,-74.40,10.95` (oeste, sur, este, norte; WGS84). Grilla del producto: EPSG:32618 (UTM 18N), 10 m.
- Mismo track y frame, 10 ciclos de 12 días (120 días); horas de paso a menos de 6 s de diferencia: misma geometría de iluminación.
- Ninguna fecha cruza el hueco del 27 jul – 10 ago 2026.
- Descarga y procesamiento: Juan Sebastián Huertas (ver #10 y #11). Capas publicadas en `web/layers/cienaga/` con `pipeline/change_detection.py` (boxcar 5×5, umbral 3 dB).

## Datos complementarios

| Fuente | Uso | Enlace |
|---|---|---|
| NASA POWER (viento a 10 m, WS10M) | Probar la hipótesis de rugosidad por viento en las fechas de paso (ver #10) | https://power.larc.nasa.gov/ |
