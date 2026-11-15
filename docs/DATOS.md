# Data used

Every scene comes from the **`NISAR_L2_GCOV_PROVISIONAL_V1`** collection
(NISAR L2 GCOV, provisional level), DOI [`10.5067/NIL2GCOV-P1`](https://doi.org/10.5067/NIL2GCOV-P1),
distributed by the Alaska Satellite Facility DAAC. Searched and downloaded through
[ASF Vertex](https://search.asf.alaska.edu) with an Earthdata Login account (free).
The `.h5` files are not committed to this repository.

- **Collection:** `NISAR_L2_GCOV_PROVISIONAL_V1` · version 1 · CRID `P05023` · DOI `10.5067/NIL2GCOV-P1`
- **Temporal coverage:** open-ended. The catalog states 2025-10-28 to Present.
  CMR query of 2026-11-15: 163,672 granules, from 2025-10-29 to 2026-10-21.
- **Instrument outage:** **no acquisitions between 28 July and 9 August 2026,
  both inclusive** — 13 days with zero granules in CMR. 27 July is partially
  covered (1,215 granules against roughly 1,350 on a normal day) and 10 August
  is back to normal. Any pair spanning that window loses two cycles.

## Scenes used

| Area | Role | Date (UTC) | Collection | CRID | Track / frame · cycle | Polarizations | Granule (ASF) |
|---|---|---|---|---|---|---|---|
| Ciénaga Grande de Santa Marta | before | 2026-06-22 10:31:54Z | PROVISIONAL | P05023 | 119 A · 007 · cycle 023 | DHDH: HHHH, HVHV | [`…_023_119_A_007_…_20260622T103154_…`](https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001/NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001.h5) |
| Ciénaga Grande de Santa Marta | after | 2026-10-20 10:31:48Z | PROVISIONAL | P05023 | 119 A · 007 · cycle 033 | DHDH: HHHH, HVHV | [`…_033_119_A_007_…_20261020T103148_…`](https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001/NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001.h5) |

Full granule names, verified against CMR on 2026-11-15:

- before: `NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001`
- after: `NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001`

Each granule is accompanied by a `…_QA_STATS.h5` sidecar at the same path, holding
the product quality statistics.

## Comparability

- Same track, same frame, same collection, same CRID, same polarization mode (DHDH).
  A different look angle would map the geometry and a different baseline would map
  the algorithm; neither maps the ground.
- 10 cycles of 12 days = **exactly 120 days** between acquisitions.
- Overpass times: **10:31:54Z** and **10:31:48Z**, **6 seconds apart**. Same
  illumination geometry.
- Neither date falls inside the 28 July – 9 August 2026 outage.
- The application refuses to compare scenes from different collections or CRIDs, and
  displays the date, collection and CRID of each scene.

## Full series available on this track and frame

CMR query of 2026-11-15, `*_119_A_007_*` in `NISAR_L2_GCOV_PROVISIONAL_V1`:
**9 granules**, all DHDH, overpass times between 10:31:47Z and 10:31:54Z.

| Cycle | Date | | Cycle | Date |
|---|---|---|---|---|
| 023 | 2026-06-22 ← **before** | | 029 | 2026-09-02 |
| 024 | 2026-07-04 | | 030 | 2026-09-14 |
| 025 | 2026-07-16 | | 031 | 2026-09-26 |
| ~~026~~ | ~~2026-07-28~~ no data | | 032 | 2026-10-08 |
| ~~027~~ | ~~2026-08-09~~ no data | | 033 | 2026-10-20 ← **after** |
| 028 | 2026-08-21 | | | |

Cycles 026 and 027 fall exactly inside the instrument outage. Our two scenes are the
first and the last element of the available series. This table is the basis of the
next step declared in the demo deck: a nine-date time series separates a step from a
seasonal cycle, and two dates cannot.

## Area and grids

- **Crop:** `-74.70, 10.75, -74.40, 10.95` (west, south, east, north; WGS84).
- **Product grid:** EPSG:32618 (UTM 18N), 10 m.
- **Published layers** in `web/layers/cienaga/`: EPSG:3857, pixel ≈ 16.3 m.

## Processing

- `pipeline/nisar_gcov_to_tif.py` — reads `/science/LSAR/GCOV/grids/frequencyA` from
  the HDF5 product, crops the area and writes one GeoTIFF per polarization.
  Validity test: `mask != 255`. Careful: in `mask` the value is the **subswath number**
  of each valid sample, `0` marks samples that are partially focused or invalid, and
  `255` is fill outside the acquisition extent. Filtering on `mask == 0` inverts the
  criterion and yields an all-NaN crop that silently reports 0% change.
- `pipeline/change_detection.py` — boxcar 5×5 px speckle filter on the published grid
  (≈ 82 m), change = `10·log10(after / before)`, threshold ±3 dB.
- Water mask: Otsu thresholding, −15.2 dB (before) and −13.7 dB (after).

Reproduction:

```bash
python pipeline/nisar_gcov_to_tif.py <scene>.h5 --pol HHHH \
    --bbox -74.70,10.75,-74.40,10.95 --out before_HHHH.tif
python pipeline/change_detection.py before_HHHH.tif after_HHHH.tif \
    --site cienaga --site-name "Ciénaga Grande de Santa Marta" --pol HHHH \
    --before-info "PROVISIONAL,P05023,2026-06-22" \
    --after-info  "PROVISIONAL,P05023,2026-10-20" \
    --out-root web/layers
```

## Complementary data

The submission form requires listing **every** external resource, free ones included.

| Resource | Use | Link |
|---|---|---|
| NASA POWER | Hourly 10 m wind at both acquisition times, used to test and reject the wind-roughening hypothesis. 2.97 m/s on 22 June against 0.87 m/s on 20 October. Resolution ~50 km: a regional average, not a local breeze. | https://power.larc.nasa.gov/ |
| Esri World Imagery | Application basemap | https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9 |
| OpenStreetMap | Alternate basemap and reference | https://www.openstreetmap.org/copyright |
| Ramsar RIS, Site 951 | Wetland context in the demo deck: Ramsar Site 951, designated 18 June 1998, 400,000 ha, also a UNESCO Biosphere Reserve | https://rsis.ramsar.org/ris/951 |

No coastline layer was used (no Natural Earth, no SCAR ADD, none). If one is added,
record it here with its link and licence.

## Responsibilities

Download and metadata log: Juan Sebastián Huertas (#10, #11).
Pipeline and layer publication: Fredy Chaparro.
Granule names, instrument outage and full series verified against CMR: 2026-11-15.
