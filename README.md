# Los Bailarines del SAR 🛰️💃

**NASA Space Apps Challenge 2026** — reto *"The Earth's surface dance"* con datos de radar **NISAR** (NASA-ISRO).

> 🇬🇧 English version below.

## ¿Qué es?

Una aplicación web interactiva que muestra **cómo cambia la superficie de la Tierra** entre dos fechas, a partir de imágenes de radar de apertura sintética (SAR) de la misión NISAR. El radar ve de día y de noche, a través de nubes y humo, y es sensible a la rugosidad y a la humedad de la superficie.

**Demo en vivo:** https://fredyxander.github.io/bailarines-del-sar/

- **Zonas de estudio:** _por definir (2 zonas)_
- **Pregunta:** _por definir (una frase)_

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

## Datos usados

Ver [`docs/DATOS.md`](docs/DATOS.md). Colección **NISAR PROVISIONAL** (17 jun – 23 oct 2026) desde [ASF Vertex](https://search.asf.alaska.edu). Hay un hueco del instrumento entre el 27 jul y el 10 ago 2026.

## Equipo

Tinjacá · Fredy · Santiago · Daira · Moneeb

## Use of AI tools

Parts of this repository were written with the assistance of AI coding tools. All method choices, polarization selections, thresholds and scientific interpretations were specified, reviewed and approved by the human team members named in this submission. AI-assisted components are limited to code drafting, documentation and workflow automation. No radar scene, measurement, result or figure in this project was generated, synthesised or altered by an AI tool.

## Créditos y licencia

- Código: [MIT](LICENSE). Avisos de terceros en [`NOTICE`](NOTICE).
- `tutorial/`: © Agencia Espacial Canadiense, licencia MIT propia ([`tutorial/LICENSE-CSA`](tutorial/LICENSE-CSA)). El uso de este material no implica respaldo de la CSA.
- Datos NISAR: NASA/JPL-Caltech e ISRO, distribuidos por ASF DAAC. NASA no respalda este proyecto.

---

## 🇬🇧 English

**Los Bailarines del SAR** ("The SAR Dancers") is an interactive web app for NASA Space Apps Challenge 2026. It shows **how Earth's surface changes** between two dates using NISAR synthetic aperture radar data. Live demo: https://fredyxander.github.io/bailarines-del-sar/

- `pipeline/nisar_gcov_to_tif.py` extracts one polarization of a NISAR GCOV (HDF5) product, cropped to an area of interest. `pipeline/change_detection.py` filters speckle (boxcar or Lee, stated window), computes change as `10·log10(after/before)` dB, refuses to compare scenes from different collections/CRIDs, and publishes map layers to `web/layers/`.
- `web/` is a Leaflet map with a before/after swipe, a change map, a polarization selector and the collection, CRID and date of every scene.
- Data provenance (collection, CRID, date of each scene) lives in [`docs/DATOS.md`](docs/DATOS.md).

Quick start: see the commands above. Code is MIT licensed; `tutorial/` keeps the Canadian Space Agency's own MIT license.
