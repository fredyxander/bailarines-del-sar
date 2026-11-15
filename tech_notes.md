# Tech notes · Surface Dance

Shared notebook for decisions, findings and gotchas that **other tasks depend on**.
Every GitHub issue (#10–#27) says "read `tech_notes.md`" and "add to `tech_notes.md`": this is that file.

## How to use it

- **Read the sections that touch your task before you start.**
- **Add** what someone else will need: a decision, a real value, a path, a number, a problem and its fix.
- One entry = one bullet: `- YYYY-MM-DD · #issue · name — note`. Newest at the bottom of each section.
- Add notes in the same pull request as your work (or in a small PR of their own). Do not rewrite other people's entries; add a new one that corrects them.
- Keep it short. Long explanations go in the README, code comments or the PR.

---

## 1. Study area and question

- 2026-11-14 · — · team — Proposed primary area: **Ciénaga Grande de Santa Marta** (Colombia). Secondary (optional): Antarctic Peninsula, drop if not ready by Sun 15:00. Final decision: #10.
- 2026-11-15 · fredyxander/bailarines-del-sar#10 · Juan H. — **Final area: Ciénaga Grande de Santa Marta**, bbox `-74.70,10.75,-74.40,10.95`. Scenes: track 119 ascending, frame 007, PROVISIONAL / CRID P05023, 2026-06-22 and 2026-10-20, dual-pol DHDH, EPSG:32618 at 10 m.
- 2026-11-15 · fredyxander/bailarines-del-sar#10 · Juan H. — **Question (final):** where did the radar signal change, and does HH vs HV tell us whether the change was at the surface or in the vegetation above it? The original "did open water expand or retreat" is contradicted by the data: water extent barely moved.
- 2026-11-15 · fredyxander/bailarines-del-sar#10 · Juan H. — **Wind hypothesis tested and REJECTED.** NASA POWER WS10M at the acquisition hours: 2.97 m/s (53°) on 22 Jun, 0.87 m/s (170°) on 20 Oct. The date with higher HH had 3.4× less wind. Caveat: MERRA-2 half-degree cell, regional average, cannot resolve local breeze. Local DIMAR-CIOH wind requested.
- 2026-11-15 · fredyxander/bailarines-del-sar#10 · Juan H. — **Second panel (Antarctica) dropped.** NISAR is single-pol (SHSH) there and cannot support the polarization comparison.

## 2. NISAR data (scenes, collections, CRIDs)

- 2026-11-14 · — · team — Use **GCOV** (geocoded, terrain-corrected). Collections: **PROVISIONAL = CRID P05023** (17 Jun – 23 Oct 2026), **VALIDATED = CRID P05036** (from 21 Oct 2026), **BETA** (17 Oct 2025 – 20 Jan 2026, not fully calibrated: context only).
- 2026-11-14 · — · team — **Never compare across collections/CRIDs.** `change_detection.py` refuses to run if they differ.
- 2026-11-14 · — · team — **Permanent instrument gap 27 Jul – 10 Aug 2026** in PROVISIONAL. Do not pick dates that straddle it.
- 2026-11-14 · — · team — Scene log (date · collection · CRID · file) lives in `docs/DATOS.md`.
- 2026-11-15 · #11 · Juan H. (download), Fredy (record) — **Scenes in use:** before `NISAR_L2_PR_GCOV_023_119_A_007_4005_DHDH_A_20260622T103154_20260622T103231_P05023_N_F_J_001`, after `NISAR_L2_PR_GCOV_033_119_A_007_4005_DHDH_A_20261020T103148_20261020T103229_P05023_N_F_J_001`. Both GCOV PROVISIONAL P05023, ascending track 119, frame 007, cycles 023 → 033 (120 days), dual-pol DHDH (HHHH + HVHV). Download URLs in `docs/DATOS.md` (Earthdata Login required). Never commit the `.h5` files.
- 2026-11-15 · #12 · Fredy — Granule names and URLs found with the public ASF search API (`dataset=NISAR`, bbox + date); exactly one GCOV per date over the area. Overpass 10:31:54Z vs 10:31:48Z. CRID P05023 is part of the granule name.

## 3. HDF5 / GCOV structure

- 2026-11-14 · — · Fredy — **Unverified on real data.** `nisar_gcov_to_tif.py` assumes: grid group `/science/LSAR/GCOV/grids/frequencyA`, datasets `xCoordinates` / `yCoordinates` (pixel centres), `projection` with attribute `epsg_code`, covariance terms named like `HHHH`, `HVHV`, values in **linear power**. Confirm with `--list` on a real scene (#13) and record the real paths here.

- 2026-11-15 · #13 · Fredy — **Converter verified on the real files** (via the GeoTIFFs Juan H. produced with `nisar_gcov_to_tif.py`): grid `/science/LSAR/GCOV/grids/frequencyA` read correctly, HHHH and HVHV present, EPSG:32618, 10 × 10 m, both dates on the same 3282 × 2217 grid (pixel-aligned), values float32 **linear power**, no nodata. HH median −15 dB, HV median −21 dB.

## 4. Method decisions

- 2026-11-14 · — · Fredy — Current defaults (to approve in #15): speckle filter **boxcar 5×5 px**, change = **10·log10(after/before)** dB, significance threshold **3 dB**, web images reprojected to EPSG:3857 and averaged in linear power up to **2048 px**. Lee filter available (`--filter lee --enl 4`).
- 2026-11-14 · — · Fredy — `--bbox` takes `west,south,east,north` in WGS84 degrees. Negative longitudes work in both scripts (argparse before Python 3.14 needed a fix).
- 2026-11-15 · #15 · Santiago — Speckle filter: boxcar, 5×5 px (approves Fredy's default). Reason: lagoon-scale features should survive the ~100–130 m smoothing; Lee not yet tested on real NISAR data. Small channels may blur; to be checked on the first real map.
- 2026-11-15 · #15 · Santiago — Change threshold: 3 dB, about a doubling or halving of the echo (approves Fredy's default). Reason: a commonly used rule of thumb, not yet checked against NISAR data; to be revisited after the first real map.
- 2026-11-15 · #14 · Santiago — Sources: NASA Earthdata (n.d.), What is SAR?; Jensen et al. (2018), Remote Sensing 10(9):1431; NASA JPL NISAR mission page.

## 5. AI layer

- 2026-11-14 · — · team — Rules: real data first (Sun 10:00), AI second; if not ready by **Sun 15:00** we ship without it. AI explains and groups, **never predicts** floods or damage. Every AI output is labelled in the UI.
- 2026-11-14 · — · Fredy — **Area in km² must be computed on the native UTM grid** (before the Web Mercator reprojection), otherwise areas are inflated by the projection.
- 2026-11-14 · — · Fredy — No API keys in the repository or in the browser. Language-model calls run offline in the pipeline; keys come from environment variables.

- 2026-11-15 · #23 · Fredy — **Water threshold check** (5×5 boxcar, dB, native UTM grid, histograms in `docs/figures/water_histograms_hh_hv.png`). HH Otsu: **−15.2 dB** (22 Jun) and **−13.8 dB** (20 Oct) → Juan H.'s −15 dB is validated for HH in June. **Do not use −15 dB on HV**: HV Otsu is −20.2 / −19.8 dB (−15 dB would flag ~80% as water).
- 2026-11-15 · #23 · Fredy — Water area (HH, per-date Otsu): **329.2 km² → 343.7 km²** (+14.5 km², +4.4%); with a fixed −15 dB: 330.7 → 333.0 km². HV Otsu: 349.8 → 356.5 km². Water extent is essentially stable.
- 2026-11-15 · #14 · Fredy — For the drivers text: the HH **water mode shifted from ≈ −22 to ≈ −19 dB (+3 dB)** while the land mode did not move; in HV the water mode moved only ≈ +0.5 dB. The change is at the water surface, not new vegetation above it.

## 6. App and deployment

- 2026-11-14 · — · Fredy — Every merge to `main` publishes `web/` to GitHub Pages (`gh-pages` branch). Each PR gets a preview at `…/pr-preview/pr-<n>/` and must pass the `checks` job (`tests/test_pipeline.py`, `tests/smoke_test.py`).
- 2026-11-14 · — · Fredy — Layers are read from `web/layers/index.json` and `web/layers/<site>/<pol>/meta.json`. `?demo=1` reads `web/demo/` (synthetic, yellow banner).

## 7. Submission and rules

- 2026-11-14 · — · team — Deadline **Sun 15 Nov 2026, 23:59 Bogotá**; target submit **22:00**. Fields and checklist: `base reference/OLEA_NISAR_SpaceApps2026_Submission_Pack_v2.pdf`.
- 2026-11-14 · — · team — The README "Use of AI tools" statement currently says no result or figure was generated by AI. **It must be updated** if we ship the AI layer or keep the synthetic demo (#26).
- 2026-11-14 · — · team — Concept mockups in the team presentation are illustrative: **do not use them in the submission as results.** AI-generated images need a visible watermark; no NASA logos.
- 2026-11-15 · #26 · Juan H. — **AI statement finalised, version A**, identical wording in the README and in form field 6. Declares AI coding assistance, AI execution of our own pipeline to produce `web/layers/`, and the synthetic demo scenes. Form SI options must match what actually ships: unselect "Building SI/ML Into the Project" if #22 misses the 15:00 gate.

## 8. Open questions and decisions

- Project name (OLEA or a new name) and keep/remove demo mode — #20.
- 2026-11-15 · fredyxander/bailarines-del-sar#20 · Juan H. — **Project name: Los Bailarines del SAR**, unchanged. Matches the challenge and what the team is registered under; no build, README or deck change needed.
- 2026-11-15 · fredyxander/bailarines-del-sar#20 · Juan H. — **Demo mode kept.** Labelled synthetic on every screen, and it is the fallback if the real layers fail tonight. Condition: the yellow banner stays as it is. Requires the AI statement in fredyxander/bailarines-del-sar#26 to declare the synthetic scenes.
