# Los Bailarines del SAR 🛰️💃

**NASA Space Apps Challenge 2026** — reto *"The Earth's surface dance"* con datos de radar **NISAR** (NASA-ISRO).

> 🇬🇧 English version below.

## ¿Qué es?

Una aplicación web interactiva que muestra **cómo cambia la superficie de la Tierra** entre dos fechas, a partir de imágenes de radar de apertura sintética (SAR) de la misión NISAR. El radar ve de día y de noche, a través de nubes y humo, y es sensible a la rugosidad y a la humedad de la superficie.

**Demo en vivo:** https://fredyxander.github.io/bailarines-del-sar/

- **Zonas de estudio:** Ciénaga Grande de Santa Marta, Magdalena, Colombia (`-74.70,10.75,-74.40,10.95`, WGS84). Segundo panel (Península Antártica): descartado.
- **Pregunta:** **ES:** Entre el 22 de junio y el 20 de octubre de 2026, ¿dónde cambió la señal de radar sobre la Ciénaga Grande, y permite la comparación de HH con HV saber si el cambio ocurrió en la superficie o en la vegetación sobre ella? **EN:** Between 22 June and 20 October 2026, where did the radar signal over the Ciénaga Grande change — and does comparing HH with HV tell us whether the change happened at the surface or in the vegetation above it?

## Resultado principal

**Cambió la superficie del agua; la ciénaga no creció.** Entre el 22 de junio y el 20 de octubre de 2026, el agua abierta pasó de 329 a 344 km² (+4 %). Sobre el agua, el eco HH subió cerca de +3 dB mientras HV subió solo +0,5 dB, y el viento fue más débil en la fecha más brillante. Eso apunta a un cambio en la superficie del agua y no a vegetación nueva. Las causas que siguen abiertas (brisa local, lluvia al momento del paso, agua muy somera) son hipótesis por comprobar. Texto completo, en inglés y español, en la sección *Why it changed* de la app (`web/layers/cienaga/why.json`).

## Presentación del equipo

Resumen de lo construido, lo que falta, tareas por integrante, flujo de trabajo y enlaces:
**https://fredyxander.github.io/bailarines-del-sar/presentation/** (inglés / español con el selector EN · ES; PDF: [inglés](docs/team-briefing.pdf) · [español](docs/team-briefing-es.pdf)). Documentos de referencia del equipo en [`base reference/`](base%20reference/).

## Tareas y notas técnicas

- Tareas del equipo: [issues #10–#27](https://github.com/fredyxander/bailarines-del-sar/issues?q=is%3Aissue+milestone%3A%22Space+Apps+submission%22), con responsable, checklist y dependencias.
- Decisiones y hallazgos compartidos: [`tech_notes.md`](tech_notes.md). Léelo antes de empezar un issue y agrega ahí lo que otros necesiten saber.

## Estructura

| Carpeta | Contenido |
|---|---|
| `pipeline/nisar_gcov_to_tif.py` | Extrae una polarización de un NISAR GCOV (.h5), recortada a la zona, como GeoTIFF |
| `pipeline/change_detection.py` | Filtra speckle, calcula el cambio entre dos fechas y publica capas en `web/layers/` |
| `web/` | Visor Leaflet: barra antes/después, mapa de cambio, polarización y metadatos de cada escena |
| `tutorial/` | Tutorial SAR en Python de la Agencia Espacial Canadiense, punto de partida |
| `docs/` | Datos usados, metodología y notas del equipo |
| `data/` | Escenas descargadas (no se suben al repo) |

## Flujo de trabajo

```bash
pip install -r requirements.txt

# 1. Ver qué trae cada escena (rutas, polarizaciones, metadatos)
python pipeline/nisar_gcov_to_tif.py data/escena1.h5 --list

# 2. Extraer cada polarización, recortada a la zona (oeste,sur,este,norte en grados)
python pipeline/nisar_gcov_to_tif.py data/escena1.h5 --pol HHHH --bbox -74.65,10.65,-74.25,11.05 --out data/f1_HHHH.tif
python pipeline/nisar_gcov_to_tif.py data/escena2.h5 --pol HHHH --bbox -74.65,10.65,-74.25,11.05 --out data/f2_HHHH.tif

# 3. Calcular el cambio y publicar la capa (repetir por polarización)
python pipeline/change_detection.py data/f1_HHHH.tif data/f2_HHHH.tif \
    --site cienaga --site-name "Ciénaga Grande de Santa Marta" --pol HHHH \
    --before-info PROVISIONAL,P05023,2026-06-20 --after-info PROVISIONAL,P05023,2026-09-12 \
    --filter boxcar --window 5

# 4. Ver el resultado
python -m http.server -d web     # http://localhost:8000
```

Decisiones del método (las define el equipo, valores por defecto entre paréntesis):

- **Filtro de speckle:** `--filter boxcar|lee|none` (boxcar) y `--window` en píxeles (5). Para Lee, `--enl` (4).
- **Cambio:** `10·log10(después/antes)` en dB, es decir, un cociente, porque la retrodispersión es multiplicativa.
- **Umbral para las estadísticas:** `--threshold` en dB (3).
- **Colecciones:** si la colección o el CRID de las dos escenas no coinciden, el script se detiene y no calcula nada.
- **Resolución web:** las imágenes se reproyectan a Web Mercator y se promedian en potencia lineal hasta `--max-size` píxeles (2048).

Las rutas internas del HDF5 de NISAR GCOV (`/science/LSAR/GCOV/grids/frequencyA/...`) están basadas en la especificación del producto y **deben confirmarse con `--list` en una escena real**.

Después de hacer merge a `main`, las capas que estén en `web/layers/` se publican automáticamente.

## Cómo se revisan los cambios

`main` está protegida: todo entra por pull request y **solo se fusiona cuando las pruebas pasan**.

1. **Vista previa:** cada PR publica una copia del sitio en `https://fredyxander.github.io/bailarines-del-sar/pr-preview/pr-<número>/` y deja el link como comentario en el PR. Se borra al cerrarlo.
2. **Pruebas automáticas (CI):** el pipeline con datos sintéticos tipo NISAR, la sintaxis del JavaScript y el visor abierto en un navegador (barra, vistas, polarizaciones). Si algo falla, el PR no se puede fusionar.
3. **Al fusionar a `main`** se publica el sitio principal.

Para correr las mismas pruebas en local:

```bash
pip install -r requirements.txt playwright && python -m playwright install chromium
python tests/test_pipeline.py
python tests/smoke_test.py
```

## Datos usados

Ver [`docs/DATOS.md`](docs/DATOS.md). Colección **NISAR PROVISIONAL** (17 jun – 23 oct 2026) desde [ASF Vertex](https://search.asf.alaska.edu). Hay un hueco del instrumento entre el 27 jul y el 10 ago 2026.

## Equipo

Tinjacá · Fredy · Santiago · Daira · Moneeb

## Demo sintético / Synthetic demo

Para probar el visor sin datos reales: https://fredyxander.github.io/bailarines-del-sar/?demo=1

Las escenas de `web/demo/` las genera `pipeline/make_demo_data.py`: son **sintéticas, no son datos NISAR y no muestran ningún cambio real**. El visor solo las carga con `?demo=1` y bajo una franja visible de aviso. No forman parte de los resultados del proyecto.

*The scenes in `web/demo/` are synthetic test data produced by `pipeline/make_demo_data.py`. They are not NISAR data, show no real change, are only loaded with `?demo=1` under a visible banner, and are not part of the project's results.*

## Use of AI tools

Parts of this repository were written with the assistance of AI coding tools, an AI assistant executed the project's own processing pipeline on the NISAR granules to generate the published layers, and the synthetic demonstration scenes available under ?demo=1 were generated programmatically to test the interface. The demo is labelled as invented data on every screen and contains no NISAR observation. All method choices, polarization selections, masking rules, thresholds and scientific interpretations were specified, reviewed and approved by the human team members named in this submission. No NISAR scene, measurement, result or figure presented as an observation was generated, synthesised or altered by an AI tool.

Two components of the application are machine-generated and labelled as such in the interface:

Change types are produced by unsupervised k-means clustering over the HH and HV change values. The clustering groups pixels by similarity and assigns no physical meaning; the class names are written by the team from visible rules.
"Read the dance", the plain-language summary, is written by a language model (Claude Opus 5.5) from numbers the pipeline already computed, recorded in web/layers/cienaga/summary.json under generated_with. It restates computed values in English and Spanish and introduces no new figure.

Neither component predicts flooding, damage or any future state.

The text of the 7-slide demo deck was also drafted with AI assistance. No image in the application or in the deck was generated by AI; every figure is pipeline output, a screenshot of the application, or the unaltered NASA Space Apps Challenge logo.

## Créditos y licencia

- Código: [MIT](LICENSE). Avisos de terceros en [`NOTICE`](NOTICE).
- `tutorial/`: © Agencia Espacial Canadiense, licencia MIT propia ([`tutorial/LICENSE-CSA`](tutorial/LICENSE-CSA)). El uso de este material no implica respaldo de la CSA.
- Datos NISAR: NASA/JPL-Caltech e ISRO, distribuidos por ASF DAAC. NASA no respalda este proyecto.

---

## 🇬🇧 English

**Los Bailarines del SAR** ("The SAR Dancers") is an interactive web app for NASA Space Apps Challenge 2026. It shows **how Earth's surface changes** between two dates using NISAR synthetic aperture radar data. Live demo: https://fredyxander.github.io/bailarines-del-sar/

**Main result:** the water surface changed — the lagoon did not grow. Open water went from 329 to 344 km² (+4%) between 22 June and 20 October 2026; over water HH rose about +3 dB while HV rose only +0.5 dB, and wind was weaker on the brighter date. Open causes (local breeze, rain at overpass, very shallow water) are hypotheses to test. Full text in the app's *Why it changed* section.

- `pipeline/nisar_gcov_to_tif.py` extracts one polarization of a NISAR GCOV (HDF5) product, cropped to an area of interest. `pipeline/change_detection.py` filters speckle (boxcar or Lee, stated window), computes change as `10·log10(after/before)` dB, refuses to compare scenes from different collections/CRIDs, and publishes map layers to `web/layers/`.
- `web/` is a Leaflet map with a before/after swipe, a change map, a polarization selector and the collection, CRID and date of every scene.
- Data provenance (collection, CRID, date of each scene) lives in [`docs/DATOS.md`](docs/DATOS.md).

Quick start: see the commands above. Code is MIT licensed; `tutorial/` keeps the Canadian Space Agency's own MIT license.
